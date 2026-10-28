"""Authentification : mot de passe (anti force brute), tickets d'envoi, sessions déverrouillées."""

import hmac
import secrets
import threading
import time

from app import config

MAX_FAILS = 5          # essais de mot de passe avant verrouillage
LOCK_SECONDS = 60
_auth_lock = threading.Lock()
_auth_fails = {}       # ip -> (essais, verrouillé jusqu'à)


def check_password(ip, given, expected=None):
    """Vérifie un mot de passe (par défaut celui de suppression), avec verrouillage par adresse IP.
    -> (ok, message)"""
    expected = config.PASSWORD if expected is None else expected
    candidates = [e for e in ([expected] if isinstance(expected, str) else expected) if e]
    now = time.monotonic()
    with _auth_lock:
        count, until = _auth_fails.get(ip, (0, 0.0))
        if until > now:
            return False, f"Trop d'essais, réessaie dans {int(until - now) + 1} s."
        if until:                       # verrou expiré : on repart de zéro
            count = 0
        count += 1                      # l'essai est compté avant la vérification (essais parallèles)
        _auth_fails[ip] = (count, now + LOCK_SECONDS if count >= MAX_FAILS else 0.0)
    ok = any([hmac.compare_digest(given.encode("utf-8", "replace"), e.encode("utf-8", "replace")) for e in candidates])
    if ok:
        with _auth_lock:
            _auth_fails.pop(ip, None)
        return True, ""
    time.sleep(0.5)                     # ralentit les essais successifs
    return False, "Mot de passe incorrect."


TICKET_TTL = 15 * 60       # durée de validité d'un jeton d'envoi (fenêtre glissante)
_tickets = {}              # jeton d'envoi -> expiration (monotonic)
_tickets_lock = threading.Lock()


def issue_ticket():
    """Jeton d'envoi à usage limité (obtenu avec le mot de passe, valable pour /upload uniquement)."""
    now = time.monotonic()
    with _tickets_lock:
        for t in [t for t, exp in _tickets.items() if exp < now]:
            del _tickets[t]
        while len(_tickets) >= 50:
            del _tickets[min(_tickets, key=_tickets.get)]
        ticket = secrets.token_urlsafe(24)
        _tickets[ticket] = now + TICKET_TTL
    return ticket


def use_ticket(ticket):
    """Vrai si le jeton est valide ; sa validité est alors prolongée."""
    now = time.monotonic()
    with _tickets_lock:
        exp = _tickets.get(ticket)
        if exp is None or exp < now:
            _tickets.pop(ticket, None)
            return False
        _tickets[ticket] = now + TICKET_TTL
    return True


_unlock_lock = threading.Lock()
_unlocked = {}                     # identifiant de session -> {"files", "dash"} ; en mémoire : tout est verrouillé au redémarrage


def unlock_scopes(sid):
    """Parties déverrouillées de cette session : "files" (suppression, envoi) et/ou "dash" (tableau de bord)."""
    if not sid:
        return set()
    with _unlock_lock:
        return set(_unlocked.get(sid, ()))


def grant_unlock(sid, scopes):
    with _unlock_lock:
        if sid not in _unlocked:
            while len(_unlocked) >= 50:
                del _unlocked[next(iter(_unlocked))]
            sid = secrets.token_urlsafe(24)
            _unlocked[sid] = set()
        _unlocked[sid] |= set(scopes)
    return sid


def use_dash_session(sid, touch=True):
    return "dash" in unlock_scopes(sid)


def drop_dash_session(sid):
    with _unlock_lock:
        _unlocked.pop(sid, None)
