"""Root cause detection for DAG failures and data quality issues.

Maps error patterns to human-readable causes and actionable fixes.
Used by alert_monitor DAG and email_alerts.
"""

# (pattern_in_exception, root_cause_label, action)
ROOT_CAUSE_RULES = [
    ('401',                    'Credentials expirés ou invalides (HTTP 401)',        'Dashboard → Credentials → renouveler le token'),
    ('403',                    'Accès refusé (HTTP 403) — permissions insuffisantes', 'Vérifier les scopes OAuth de l\'app sur le portail développeur'),
    ('429',                    'Rate limit API dépassé (HTTP 429)',                  'Réduire la fréquence de collecte ou attendre 1h avant de relancer'),
    ('token',                  'Token invalide ou absent',                           'Dashboard → Credentials → saisir un nouveau token'),
    ('expired',                'Token ou session expiré(e)',                         'Dashboard → Credentials → renouveler le token'),
    ('invalid_token',          'Token invalide',                                     'Dashboard → Credentials → renouveler le token'),
    ('connection refused',     'Service inaccessible — Docker ou réseau down',       'Lancer : docker-compose up -d'),
    ('could not connect',      'PostgreSQL inaccessible',                            'Vérifier : docker-compose ps → postgres doit être Healthy'),
    ('relation does not exist','Table manquante en base de données',                 'Appliquer les migrations manquantes dans migrations/'),
    ('no module named',        'Dépendance Python manquante dans le container',      'Lancer : docker-compose build && docker-compose up -d'),
    ('fernet',                 'FERNET_KEY non configurée ou invalide',              'Ajouter FERNET_KEY dans .env et redémarrer les services'),
    ('ssl',                    'Erreur SSL/TLS',                                     'Vérifier les certificats ou contacter le support de la plateforme'),
    ('timeout',                'Timeout réseau ou API',                              'Vérifier la connexion réseau et relancer le DAG'),
    ('no credentials',         'Credentials absents en base',                        'Dashboard → Credentials → saisir les tokens pour cet artiste'),
    ('credential',             'Problème de credentials',                            'Dashboard → Credentials → vérifier et renouveler les tokens'),
    ('insufficient_scope',     'Scopes OAuth insuffisants',                          'Recréer le token avec les bons scopes sur le portail développeur'),
    ('not found',              'Ressource introuvable (ID erroné ou supprimé)',       'Vérifier les IDs artiste/compte dans la configuration'),
]

# Platform-specific override actions (takes priority over generic rules)
PLATFORM_ACTIONS = {
    'soundcloud': (
        'SoundCloud API fermée depuis 2021 — credentials non officiels',
        'DevTools → Network → filtrer client_id → copier depuis une requête SoundCloud'
    ),
    'instagram': (
        'Meta Long-lived token expiré (validité 60 jours)',
        'developers.facebook.com → Graph API Explorer → renouveler le Long-lived token (scopes: instagram_basic, instagram_manage_insights)'
    ),
    'meta': (
        'Meta access_token expiré (validité 60 jours)',
        'developers.facebook.com → Graph API Explorer → renouveler le Long-lived token'
    ),
    'youtube': (
        'Refresh Token YouTube invalide',
        'console.cloud.google.com → OAuth → renouveler le Refresh Token YouTube Data API v3'
    ),
    'spotify': (
        'Refresh Token Spotify invalide',
        'Lancer : python src/collectors/spotify_auth.py pour renouveler le Refresh Token'
    ),
}


def detect_root_cause(exception_str: str, dag_id: str = '') -> tuple[str, str]:
    """Return (cause, action) for a given exception string and optional dag_id.

    Checks platform-specific overrides first, then generic pattern matching.
    Falls back to ('Erreur inconnue', 'Consulter les logs Airflow') if no match.
    """
    exc_lower = (exception_str or '').lower()

    # Platform override — only applies when credentials are missing
    platform = _dag_to_platform(dag_id)
    if platform and platform in PLATFORM_ACTIONS and (
        '401' in exc_lower or 'token' in exc_lower or 'expired' in exc_lower
        or 'credential' in exc_lower or 'no credentials' in exc_lower
    ):
        cause, action = PLATFORM_ACTIONS[platform]
        return cause, action

    # Generic pattern matching
    for pattern, cause, action in ROOT_CAUSE_RULES:
        if pattern in exc_lower:
            return cause, action

    return 'Erreur inconnue', f'Consulter les logs Airflow → http://localhost:8080/dags/{dag_id}/grid'


def _dag_to_platform(dag_id: str) -> str:
    mapping = {
        'soundcloud_daily': 'soundcloud',
        'instagram_daily': 'instagram',
        'meta_insights_dag': 'meta',
        'meta_config_dag': 'meta',
        'youtube_daily': 'youtube',
        'spotify_api_daily': 'spotify',
    }
    return mapping.get(dag_id, '')
