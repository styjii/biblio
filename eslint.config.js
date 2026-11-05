// Règles de style du JavaScript du projet : syntaxe moderne uniquement.
// Utilisation (rien à installer pour faire tourner l'application) :  npx eslint
// Les dossiers de fragments (browse, listen, watch…) sont des morceaux d'un même script : ils ne sont pas valides isolément,
// leur syntaxe et leur style sont contrôlés par tests/test_frontend_js.py sur les scripts tels qu'ils sont servis.
export default [
  {
    files: ['frontend/js/*.js', 'tests/js/*.js'],
    languageOptions: {ecmaVersion: 2022, sourceType: 'script'},
    rules: {
      'no-var': 'error',
      'prefer-const': 'error',
      'prefer-arrow-callback': 'error',
      'prefer-template': 'error',
      'object-shorthand': 'error',
      'prefer-object-spread': 'error',
      'no-useless-concat': 'error',
    },
  },
];
