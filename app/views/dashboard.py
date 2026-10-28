"""Page du tableau de bord."""

from app.assets import DASH_CSS, DASH_JS, THEME_JS
from app.devices import ACTIVITY_CATS
from app.icons import icon
from app.templating import render
from app.utils import js_json
from app.views.layout import doc_close, doc_open, lock_script, locked_page, topbar


def dashboard_page(unlocked):
    if not unlocked:
        return locked_page("Le tableau de bord", "dash", None, "Tableau de bord — Ma bibliothèque", DASH_CSS, True)
    cfg = {"monitor": icon("monitor", 22), "ban": icon("ban", 22),
           "cats": [{"id": i, "label": label, "color": color} for i, label, color in ACTIVITY_CATS]}
    return (doc_open("Tableau de bord — Ma bibliothèque", "", DASH_CSS) + topbar(False, True)
            + render("dashboard/body")
            + doc_close(f"window.DCFG = {js_json(cfg)}; {THEME_JS}{DASH_JS}", after=lock_script("dash")))
