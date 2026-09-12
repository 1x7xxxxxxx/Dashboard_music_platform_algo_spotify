"""Is this tenant's setup finished? One definition, read by everything that asks.

Type: Utility
Uses: PostgresHandler (one query), PLATFORM_IDENTITIES, upload_csv._PLATFORMS
Triggers: home._section_onboarding, app._first_run_landing, views/onboarding
Depends on: artist_credentials, saas_artists, csv_upload_log, s4a_song_timeline,
    track_platform_link, s4a_song_playlist_adds, usage_events, etl_run_log,
    saas_users.show_setup_on_login (migration 082)
Persists in: saas_users.show_setup_on_login (the opt-out only)

Why this module exists
----------------------
The steps were written inside `home._section_onboarding`, and the landing router
(`app._first_run_landing`) asked a DIFFERENT question — "has this artist declared
nothing at all?" (`all(status == 'todo')`). So a tenant who connected one platform and
came back the next day was declared "past onboarding" by the router while the home page
still showed 1/4. Reported from a real second login on 2026-09-04: « je ne suis plus sur
étapes 1 2 3 » and « impossible de revenir aux différentes étapes de config ».

Two surfaces answering the same question differently is the class this repo keeps
paying for. The rule lives here, once; both surfaces read it.

Everything below the query is pure, so the completion logic is testable without a
database and without Streamlit.

Les cinq étapes, et pourquoi elles ont changé le 2026-09-12
-----------------------------------------------------------
Il y en avait trois, dont DEUX lignes « importer un CSV » que rien ne distinguait sauf
la table interrogée, et aucune ne disait QUELLE plateforme manquait. Demandé le même
jour : le détail par plateforme sur la ligne des API, la fusion des deux lignes CSV
avec le listing exhaustif des imports possibles, et trois étapes de plus qui
conditionnent la qualité des prédictions (mapping, playlists S4A) ou sont le premier
livrable visible (le PDF).

  1. 🔑 API           — les 5 plateformes de `PLATFORM_IDENTITIES`, une par une
  2. 📂 Fichiers      — les 8 types de `upload_csv._PLATFORMS`, un par un
  3. 🔗 Mapping       — `track_platform_link` confirmé
  4. 📝 Playlists S4A — `s4a_song_playlist_adds` non vide
  5. 📄 Premier PDF   — `usage_events` porte déjà `pdf_generate` (export_pdf.py:315)

Une étape se coche sur l'ACTION, jamais sur la visite : c'est ce que la légende de
l'accueil promet depuis le 2026-09-04, et le PDF est le cas où la tentation était la
plus forte — il n'a pas de table à lui, seulement une trace d'usage.

Le DÉTAIL n'est pas la CONDITION. Une étape est faite dès qu'une ligne du détail est
vraie ; le détail dit ce qu'il reste à gagner, il ne bloque pas. Exiger les 8 imports
laisserait la ligne rouge à vie pour un artiste sans SACEM ni DistroKid — la même
erreur que l'ancienne étape Apple obligatoire, qui bloquait l'autostart.

L'AUTOSTART N'A PAS BOUGÉ. `should_autostart` exige toujours les identifiants ET un CSV
Spotify, jamais « un import quelconque » : lancer la collecte sur un relevé SACEM ne
collecterait rien. La fusion change ce que l'étape AFFICHE, pas ce qui déclenche — d'où
`spotify_csv`, gardé dans l'état à côté de `collected` pour la même raison.
"""
from __future__ import annotations

from typing import Callable, NamedTuple, Optional


# Session flag: this arrival is a FIRST RUN, so the app shows the setup assistant and
# nothing else — no section menu, no collect button. Not a preference and not derived
# from the database: it is "how this session arrived", set by the landing router and
# cleared the moment the artist is on any other page. Named here rather than in
# `setup_focus.py`, whose `FOCUS_KEY` is a different thing entirely (the platforms the
# artist picked to set up first).
FIRST_RUN_FOCUS = "_first_run_focus"


class Step(NamedTuple):
    """One setup step: is it done, what to call it, and where the button goes.

    `detail` est la liste `(libellé, fait)` que la ligne déplie — les plateformes
    d'API, les types de fichiers. Vide pour les étapes qui n'ont rien à énumérer.
    """
    key: str
    done: bool
    page: str
    detail: tuple[tuple[str, bool], ...] = ()


class SetupState(NamedTuple):
    steps: list[Step]
    show_on_login: bool
    # A-t-on déjà une collecte réussie ? Ce n'est PLUS une étape affichée — l'artiste
    # n'a rien à lancer, la collecte part toute seule dès que les identifiants sont
    # là (`autostart_if_journey_complete`) et repart chaque matin par cron. Lui
    # montrer une case à cocher qu'il ne coche pas lui-même était une consigne
    # adressée à personne.
    #
    # L'information reste dans l'ÉTAT parce qu'une chose la lit encore, et doit
    # continuer : `should_autostart` refuse de relancer quand une collecte a déjà
    # réussi. Retirer l'étape sans garder le fait aurait relancé une collecte à
    # chaque enregistrement.
    collected: bool = False
    # Le CSV **Spotify** précisément, et non « un import quelconque ». L'étape
    # affichée a fusionné les huit types le 2026-09-12 ; l'autostart, lui, ne peut
    # pas : déclencher la collecte sur un relevé SACEM ne collecterait rien. Même
    # raison que `collected` — l'affichage change, le fait reste lisible.
    spotify_csv: bool = False

    @property
    def done_count(self) -> int:
        return sum(1 for s in self.steps if s.done)

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def complete(self) -> bool:
        """100 % — every step done. An empty step list is NOT complete.

        `all([])` is True, and an empty list is what a failed read produces. Reading
        "I could not tell" as "finished" would send a tenant who configured nothing
        straight past the setup page, which is the exact bug this module closes.
        """
        return bool(self.steps) and all(s.done for s in self.steps)


class _Declared(NamedTuple):
    """Une étape, déclarée UNE fois : sa clé, sa page, son libellé.

    Elle vivait sur trois tables parallèles — `_STEP_PAGES`, `STEP_LABELS`, et une
    requête en dur — qu'il fallait modifier ensemble. Deux d'entre elles ont divergé
    au moins une fois. Une seule déclaration, trois lectures dérivées.
    """
    key: str
    page: str
    label: Callable[[], str]


def _t(key: str, default: str) -> str:
    from src.dashboard.utils.i18n import t
    return t(key, default)


# Labels are callables: `t()` must run at RENDER time, not at import time, or the
# whole app would freeze on whichever language was active when the module loaded.
#
# `run` pointait vers `trigger_algo` — la page ML, réservée au plan Premium : un
# artiste Free qui cliquait « Lancer votre première collecte » atterrissait sur le
# paywall. L'étape a disparu ; la leçon reste, chaque page nommée ici doit être
# ouverte au plan gratuit.
_STEPS: tuple[_Declared, ...] = (
    _Declared("creds", "credentials",
              lambda: _t("home.onboarding_creds", "🔑 Configurer les API")),
    _Declared("csv", "upload_csv",
              lambda: _t("home.onboarding_csv", "📂 Importer mes fichiers")),
    _Declared("mapping", "meta_mapping",
              lambda: _t("home.onboarding_mapping",
                         "🔗 Valider le mapping cross-plateforme")),
    _Declared("playlists", "saisie_s4a",
              lambda: _t("home.onboarding_playlists",
                         "📝 Saisir mes ajouts en playlist (S4A)")),
    _Declared("pdf", "export_pdf",
              lambda: _t("home.onboarding_pdf", "📄 Générer mon premier rapport PDF")),
)

# Conservé sous son ancien nom : `home._section_onboarding` le lit.
STEP_LABELS = {d.key: d.label for d in _STEPS}
_STEP_PAGES = tuple((d.key, d.page) for d in _STEPS)


def _api_detail(declared: set) -> tuple[tuple[str, bool], ...]:
    """Une ligne par plateforme d'API, dans l'ordre du registre d'identités.

    Le registre est la seule liste ; l'écrire ici en ferait une sixième copie, et ce
    dépôt a déjà payé les cinq premières (Instagram absent de deux d'entre elles,
    donc deux locataires pouvaient revendiquer le même compte en silence).
    """
    from src.utils.tenant_identity import PLATFORM_IDENTITIES
    return tuple((logical, logical in declared) for logical in PLATFORM_IDENTITIES)


def _csv_detail(imported: set) -> tuple[tuple[str, bool], ...]:
    """Une ligne par type de fichier importable, avec le libellé de l'importateur.

    Le registre vit dans `utils/csv_platforms.py`, et il y a DÉMÉNAGÉ pour cette
    lecture-ci. La première version importait `views/upload_csv` : **1 073 ms au
    premier rendu de l'accueil**, mesuré — le module tire pandas, les
    transformateurs et Streamlit, pour huit chaînes, alors que le budget d'une page
    complète est de 287 ms. Un registre de données n'a pas à traîner son
    importateur. Recopier les huit libellés ici aurait été la seconde copie que ce
    dépôt paie à chaque fois.
    """
    from src.dashboard.utils.csv_platforms import _PLATFORMS
    return tuple((spec.get("label", key), key in imported)
                 for key, spec in _PLATFORMS.items())


def steps_from_facts(*, declared: set, imported: set, has_mapping: bool,
                     has_playlists: bool, has_pdf: bool, has_runs: bool = False,
                     spotify_csv: bool = False,
                     show_on_login: bool = True) -> SetupState:
    """Pure : les faits bruts → l'état que chaque surface rend.

    Aucune base, aucun Streamlit. `declared` est l'ensemble des plateformes d'API dont
    l'identité est saisie, `imported` l'ensemble des types de fichiers déjà importés
    avec succès.
    """
    done = {
        "creds": bool(declared),
        "csv": bool(imported),
        "mapping": bool(has_mapping),
        "playlists": bool(has_playlists),
        "pdf": bool(has_pdf),
    }
    detail = {"creds": _api_detail(declared), "csv": _csv_detail(imported)}
    return SetupState(
        steps=[Step(d.key, done[d.key], d.page, detail.get(d.key, ()))
               for d in _STEPS],
        show_on_login=bool(show_on_login),
        collected=bool(has_runs),
        spotify_csv=bool(spotify_csv),
    )


def read_setup_state(db, artist_id: int, user_id: Optional[int] = None) -> SetupState:
    """Tous les faits + la préférence de connexion, en UN aller-retour.

    Une seule requête, délibérément : ce code tourne dans le chemin de la barre
    latérale, et les vues y sont plafonnées à une connexion
    (`tests/test_view_connection_budget.py`). L'appelant possède la connexion.

    Les identités ne se comptent PAS en lignes : `COUNT(*)` cochait l'étape pour un
    onglet ouvert et enregistré vide. On rapatrie les `extra_config` et le verdict est
    rendu par `declared_identities`, le lecteur unique — une identité a DEUX domiciles
    (la ligne de credentials et son miroir sur `saas_artists`), et trois surfaces ont
    déjà répondu différemment à la même question pour l'avoir oublié.

    Sur toute lecture en échec, elle rend AUCUNE étape, que `complete` lit comme
    « pas terminé ». Un locataire n'est jamais poussé au-delà de sa configuration
    parce qu'on n'a pas su la lire.
    """
    from src.utils.tenant_identity import IDENTITY_MIRRORS, declared_identities

    if db is None or artist_id is None:
        return SetupState(steps=[], show_on_login=True)

    # Les colonnes miroir viennent d'une constante de module, jamais d'un appelant :
    # la f-string interpole des identifiants de liste blanche (règle transverse #8).
    # Aucune VALEUR n'y entre — elles passent toutes en %s.
    mirror_cols = sorted(set(IDENTITY_MIRRORS.values()))
    assert all(c.replace("_", "").isalnum() for c in mirror_cols)
    mirror_select = ", ".join(
        f"(SELECT {c} FROM saas_artists WHERE id = %s)" for c in mirror_cols)

    rows = db.fetch_query(
        f"""
        SELECT
            (SELECT jsonb_object_agg(platform, COALESCE(extra_config, '{{}}'::jsonb))
               FROM artist_credentials WHERE artist_id = %s)                AS creds,
            (SELECT array_agg(DISTINCT platform) FROM csv_upload_log
               WHERE artist_id = %s AND status = 'success')                 AS imported,
            -- `EXISTS` et non `COUNT(*)` : la question est « déjà fait ? », et
            -- Postgres s'arrête à la première ligne au lieu de balayer la table.
            -- `s4a_song_timeline` compte des centaines de milliers de lignes pour
            -- un locataire actif, et cette requête tourne dans le chemin de la
            -- barre latérale, à chaque page. Un `LIMIT 1` collé à un `COUNT(*)`
            -- ne change rien : il limite les LIGNES DE RÉSULTAT, pas le balayage.
            EXISTS (SELECT 1 FROM s4a_song_timeline
                     WHERE artist_id = %s AND song NOT ILIKE '%%1x7xxxxxxx%%') AS has_s4a,
            EXISTS (SELECT 1 FROM track_platform_link
                     WHERE artist_id = %s AND status = 'confirmed')          AS has_mapping,
            EXISTS (SELECT 1 FROM s4a_song_playlist_adds
                     WHERE artist_id = %s)                                   AS has_playlists,
            EXISTS (SELECT 1 FROM usage_events
                     WHERE artist_id = %s AND event = 'pdf_generate')        AS has_pdf,
            EXISTS (SELECT 1 FROM etl_run_log
                     WHERE artist_id = %s AND status = 'success')            AS has_runs,
            COALESCE((SELECT show_setup_on_login FROM saas_users WHERE id = %s), TRUE),
            {mirror_select}
        """,  # noqa: S608 — seuls des identifiants de liste blanche sont interpolés
        (artist_id, artist_id, artist_id, artist_id, artist_id, artist_id,
         artist_id, user_id, *([artist_id] * len(mirror_cols))),
    )
    if not rows:
        return SetupState(steps=[], show_on_login=True)
    (creds, imported, has_s4a, has_mapping, has_playlists,
     has_pdf, has_runs, show, *mirror_values) = rows[0]

    by_col = dict(zip(mirror_cols, mirror_values))
    mirrors = {logical: by_col.get(col)
               for logical, col in IDENTITY_MIRRORS.items() if by_col.get(col)}
    declared = declared_identities(creds or {}, mirrors)

    # L'import S4A se prouve par la TABLE et non par le journal : `csv_upload_log` ne
    # remonte qu'à la migration 025, et un artiste importé avant elle a bien ses
    # données sans avoir de ligne de journal. Le journal sert au détail par type ; la
    # table sert au fait.
    files = set(imported or ())
    if has_s4a:
        files.add("s4a")
    return steps_from_facts(
        declared=set(declared), imported=files,
        has_mapping=bool(has_mapping), has_playlists=bool(has_playlists),
        has_pdf=bool(has_pdf), has_runs=bool(has_runs),
        spotify_csv=bool(has_s4a), show_on_login=show,
    )


def set_show_on_login(db, user_id: int, value: bool) -> bool:
    """Persist the artist's answer. Returns whether it was written."""
    if db is None or user_id is None:
        return False
    db.fetch_query(
        "UPDATE saas_users SET show_setup_on_login = %s WHERE id = %s RETURNING id",
        (bool(value), user_id),
    )
    return True
