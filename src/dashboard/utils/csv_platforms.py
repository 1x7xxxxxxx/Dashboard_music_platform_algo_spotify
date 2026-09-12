"""Le registre des types de fichiers importables — une donnée, pas une vue.

Type: Sub
Uses: rien
Depends on: rien
Persists in: nothing

Pourquoi ce module existe
-------------------------
Ce dictionnaire vivait dans `views/upload_csv.py`, et c'était logique tant qu'un
seul lecteur en avait besoin. Le 2026-09-12, la mise en route a eu besoin de ses
huit LIBELLÉS pour afficher « OK / NOK » par type de fichier — et importer la vue
depuis `setup_completion` a coûté **1 073 ms au premier rendu de l'accueil**,
mesuré : le module tire pandas, les transformateurs et Streamlit pour huit
chaînes. Le budget de rendu d'une page complète est de 287 ms.

Le registre est de la DONNÉE pure : des noms de tables, des colonnes de conflit,
des libellés. Rien à importer pour le lire. Il vit donc ici, et `upload_csv` le
ré-exporte sous son ancien nom pour que ses propres lecteurs ne bougent pas.

⚠️ Les `conflict_columns` doivent correspondre à un index unique RÉEL : c'est la
classe `on-conflict-target-without-index`, prouvée en production le 2026-09-11 par
un INSERT qui lève. `tests/test_an_upsert_targets_an_index_that_exists.py` le
vérifie contre le catalogue Postgres.
"""
from __future__ import annotations

_PLATFORMS = {
    's4a': {
        'label': 'S4A — Timeline par titre',
        'table': 's4a_song_timeline',
        'conflict_columns': ['artist_id', 'song', 'date'],
        'update_columns': ['streams', 'collected_at'],
    },
    's4a_songs_global': {
        'label': 'S4A — Résumé titres',
        'table': 's4a_songs_global',
        'conflict_columns': ['artist_id', 'song', 'time_window'],
        'update_columns': ['listeners', 'streams', 'saves', 'release_date', 'collected_at'],
    },
    's4a_audience': {
        'label': 'S4A — Audience',
        'table': 's4a_audience',
        'conflict_columns': ['artist_id', 'date'],
        'update_columns': ['listeners', 'streams', 'followers', 'playlist_adds', 'saves', 'collected_at'],
    },
    'apple': {
        'label': 'Apple Music',
        'table': 'apple_songs_performance',
        # La DATE entre dans la clé (migration 093) : deux dépôts à deux dates font
        # deux relevés, et Apple a enfin une série. Deux dépôts le MÊME jour restent
        # un seul relevé — re-déposer le même export ne crée pas un point de plus.
        'conflict_columns': ['artist_id', 'song_name', 'snapshot_date',
                             'period_start', 'period_end'],
        'update_columns': ['plays', 'listeners', 'shazam_count', 'collected_at'],
    },
    'imusician_summary': {
        'label': 'iMusician — Résumé par sortie',
        'table': 'imusician_release_summary',
        'conflict_columns': ['artist_id', 'barcode', 'year', 'month'],
        'update_columns': [
            'release_title', 'track_downloads', 'track_streams', 'release_downloads',
            'track_downloads_revenue', 'track_streams_revenue',
            'release_downloads_revenue', 'total_revenue', 'collected_at',
        ],
    },
    'imusician_sales': {
        'label': 'iMusician — Rapport de vente',
        'table': 'imusician_sales_detail',
        'conflict_columns': [
            'artist_id', 'isrc', 'sales_year', 'sales_month',
            'statement_year', 'statement_month', 'shop', 'country', 'transaction_type',
        ],
        'update_columns': ['quantity', 'revenue_eur', 'collected_at'],
    },
    'distrokid_sales': {
        'label': 'DistroKid — Bank details (TSV/CSV)',
        'table': 'distrokid_sales_detail',
        'conflict_columns': [
            'artist_id', 'isrc', 'title', 'sale_year', 'sale_month',
            'reporting_date', 'store', 'country', 'source_type',
        ],
        'update_columns': [
            'quantity', 'earnings_usd', 'songwriter_royalties_usd',
            'recoup_usd', 'team_percentage', 'upc', 'artist_name', 'collected_at',
        ],
    },
    'sacem': {
        'label': 'SACEM — Relevé de compte (xlsx)',
        'table': 'sacem_statement',
        'conflict_columns': ['artist_id', 'line_date', 'libelle', 'mouvement_eur', 'solde_eur'],
        'update_columns': ['line_type', 'source'],
    },
}
