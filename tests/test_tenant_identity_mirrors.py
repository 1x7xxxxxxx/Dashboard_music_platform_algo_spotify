"""A tenant identity stored in two tables must be written by ONE code path.

Measured 2026-08-21: `saas_artists.spotify_artist_id` is what `spotify_api_daily`
reads to decide whose catalogue to collect; `artist_credentials.extra_config` is
what every screen and every readiness check reads. The credentials form wrote both.
`tools/create_canary.py` wrote only the second.

The canary then reported "Connecte -- artiste << Daft Punk >>" on every surface,
passed its connection test, and its DAG succeeded in half a second having collected
nothing. The tenant whose entire purpose is to catch a false green WAS the false green.

Error class: identity-mirrored-but-written-once (.claude/dev-docs/error-classes.md).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ⚠️ GROUPE XDIST — ajouté le 2026-09-16 sur un rouge observé, pas par précaution.
#
# Ce fichier lit ou écrit l'identité plateforme d'un locataire dans la base PARTAGÉE.
# Plusieurs fichiers le font, et sous `-n auto` rien ne les tenait sur le même worker :
# l'un écrit une identité sonde et la restaure dans un `finally`, l'autre cherche « un
# autre locataire qui déclare une identité Spotify » et vérifie qu'un doublon est refusé.
# Entre les deux instants, la valeur a bougé.
#
# Deux rouges de cette forme le même soir, dans deux fichiers sans rapport
# (`test_the_hypeddit_ratio_is_the_ratio_of_sums`, puis celui-ci) : ce n'est pas un
# aléa, c'est une CLASSE — `a-shared-database-read-while-another-test-writes-it`.
# `--dist loadgroup` existe pour ça ; il ne coûte que de la sérialisation.
pytestmark = pytest.mark.xdist_group("shared_db_tenant_identity")


ROOT = Path(__file__).resolve().parent.parent

# Everything that persists a tenant's own platform identity.
IDENTITY_WRITERS = [
    "tools/create_canary.py",
    "src/dashboard/views/credentials/_render.py",
]


def test_the_mirror_list_is_not_empty() -> None:
    """A vacuous mirror list would make every assertion below pass on nothing."""
    from src.utils.tenant_identity import IDENTITY_MIRRORS

    assert IDENTITY_MIRRORS, "no mirror declared — this guard would check nothing"
    assert IDENTITY_MIRRORS.get("spotify") == "spotify_artist_id"


def _calls(path: Path, func: str) -> bool:
    """Does this module CALL `func`? Importing it is not using it.

    The first version of this guard tested `func in text`, which the import line
    satisfied on its own: deleting the call left the test green. A guard that a
    mutation cannot turn red is decoration.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) == func
             or getattr(n.func, "attr", None) == func)
        for n in ast.walk(tree)
    )


@pytest.mark.parametrize("rel", IDENTITY_WRITERS)
def test_every_identity_writer_goes_through_the_shared_path(rel: str) -> None:
    assert _calls(ROOT / rel, "write_platform_identity"), (
        f"{rel} persists a tenant identity without CALLING the shared writer. It will "
        "miss the saas_artists mirror, exactly as create_canary.py did."
    )


@pytest.mark.parametrize("rel", IDENTITY_WRITERS)
def test_no_writer_inserts_into_credentials_behind_the_shared_path(rel: str) -> None:
    """The other half of the drift: a raw INSERT that bypasses the mirror entirely."""
    from tests.code_text import code_of

    text = code_of(ROOT / rel)
    assert "INSERT INTO artist_credentials" not in text, (
        f"{rel} writes artist_credentials directly. Every identity write goes through "
        "src.utils.tenant_identity.write_platform_identity, which also writes the "
        "saas_artists mirror."
    )


@pytest.mark.parametrize("rel", IDENTITY_WRITERS)
def test_no_writer_hand_rolls_the_mirror_update(rel: str) -> None:
    """The shape that drifted: a bare UPDATE of the mirror column, off on its own.

    ⚠️ Lit le CODE, pas le texte brut, depuis le 2026-09-18. Les deux gardes de cette
    forme sont partis au ROUGE ce jour-là sur un COMMENTAIRE de `_render.py` qui
    expliquait précisément pourquoi la colonne ne doit pas être mise à NULL. Un garde
    qui interdit d'écrire SUR le défaut rend la documentation du défaut impossible, et
    ce dépôt a payé trois commandes bloquées d'affilée pour cette forme le 2026-09-12.
    """
    from tests.code_text import code_of

    text = code_of(ROOT / rel)
    hand_rolled = "UPDATE saas_artists SET spotify_artist_id"
    assert hand_rolled not in text, (
        f"{rel} writes the mirror by hand. Route it through "
        "src.utils.tenant_identity.write_platform_identity so a third writer cannot "
        "get it half right."
    )


def test_every_mirrored_column_exists_on_the_dag_read_path() -> None:
    """The mirror is only useful if the DAG really reads it — pin that it does."""
    from src.utils.tenant_identity import IDENTITY_MIRRORS

    dag = (ROOT / "airflow/dags/spotify_api_daily.py").read_text(encoding="utf-8")
    for column in IDENTITY_MIRRORS.values():
        assert f"SELECT {column} FROM saas_artists" in dag, (
            f"nothing reads saas_artists.{column} in spotify_api_daily any more — "
            "either the mirror is dead (drop it) or the DAG changed source."
        )


def test_write_platform_identity_refuses_an_unknown_platform() -> None:
    from src.utils.tenant_identity import write_platform_identity

    with pytest.raises(ValueError, match="unknown platform"):
        write_platform_identity(None, 1, "spotfy", {})


def test_the_shared_writer_is_syntactically_the_only_mirror_writer() -> None:
    """Sweep the whole tree, not just the two known writers."""
    from tests.code_text import code_of

    offenders = []
    for path in list(ROOT.glob("src/**/*.py")) + list(ROOT.glob("tools/**/*.py")):
        if path.name == "tenant_identity.py":
            continue
        try:
            text = code_of(path)          # le CODE, jamais la prose qui le décrit
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        if "UPDATE saas_artists SET spotify_artist_id" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"mirror written outside the shared path: {offenders}"


def test_the_module_parses_and_exposes_its_contract() -> None:
    src = (ROOT / "src/utils/tenant_identity.py").read_text(encoding="utf-8")
    names = {n.name for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.FunctionDef)}
    assert {"write_platform_identity", "mirrored_columns"} <= names


def test_the_shared_writer_really_writes_BOTH_places() -> None:
    """The effect, not the artefact. Every other test here checks that a call exists.

    A call that exists and writes one table is exactly the defect this file is about,
    so at least one test has to look at the database.
    """
    from tests.db_gate import db_ready

    if not db_ready():
        pytest.skip("needs the live schema")

    from src.database.postgres_handler import PostgresHandler
    from src.utils.env_files import load_project_env
    from src.utils.tenant_identity import write_platform_identity

    load_project_env()
    db = PostgresHandler.from_env_or_config()
    probe = "test-identity-probe-3f9a"
    try:
        rows = db.fetch_query(
            "SELECT id, spotify_artist_id FROM saas_artists WHERE is_canary = TRUE "
            "AND active = TRUE ORDER BY id LIMIT 1")
        if not rows:
            pytest.skip("no canary tenant here — run: make canary NAME=… SPOTIFY=…")
        artist_id, original = rows[0]

        write_platform_identity(db, artist_id, "spotify", {"spotify_artist_id": probe})

        mirror = db.fetch_query(
            "SELECT spotify_artist_id FROM saas_artists WHERE id = %s", (artist_id,))[0][0]
        creds = db.fetch_query(
            "SELECT extra_config->>'spotify_artist_id' FROM artist_credentials "
            "WHERE artist_id = %s AND platform = 'spotify'", (artist_id,))[0][0]

        assert creds == probe, "the credentials row was not written"
        assert mirror == probe, (
            "saas_artists.spotify_artist_id was NOT updated — the mirror the Spotify "
            "DAG reads. This is the exact shape that made a tenant look connected "
            "everywhere and collect nothing."
        )
    finally:
        # Put the tenant back exactly as it was, mirror included.
        try:
            write_platform_identity(
                db, artist_id, "spotify", {"spotify_artist_id": original or ""})
        except Exception:  # noqa: BLE001 - cleanup must not mask the assertion above
            pass
        db.close()


def test_writing_instagram_never_creates_an_instagram_row() -> None:
    """The namespace split, proven at the only place it can go wrong.

    Instagram is a logical platform everywhere — readiness, the alert monitor, the
    connection tests, the canary — but its identity lives INSIDE the `meta`
    credentials row, because the artist types it in the Meta tab and
    `instagram_daily` selects tenants on `creds['meta']['ig_user_id']`.

    A `platform='instagram'` row would be an orphan: written, never read, and the
    tenant would look connected while collecting nothing. That is exactly the shape
    of `identity-mirrored-but-written-once`, which cost the canary its credibility.

    No DB needed — the writer is handed a recorder and asked what it would run.
    """
    from src.utils.tenant_identity import write_platform_identity

    class _Recorder:
        def __init__(self):
            self.calls = []

        def execute_query(self, sql, params=None):
            self.calls.append((" ".join(sql.split()), params))

    db = _Recorder()
    write_platform_identity(db, 42, "instagram", {"ig_user_id": "17841400000000000"})

    inserts = [(sql, prm) for sql, prm in db.calls if "INSERT INTO artist_credentials" in sql]
    assert inserts, "nothing was written at all"
    platforms = {prm[1] for _, prm in inserts}
    assert platforms == {"meta"}, (
        f"the Instagram identity was written under platform(s) {platforms} — "
        f"a 'instagram' row is an orphan no collector reads"
    )
    assert not any("saas_artists" in sql for sql, _ in db.calls), (
        "Instagram declares no mirror; nothing should touch saas_artists"
    )


def test_writing_instagram_does_not_clobber_the_ad_account() -> None:
    """The meta row carries two identities; the jsonb merge must compose, not replace."""
    from src.utils.tenant_identity import write_platform_identity

    seen = []

    class _Recorder:
        def execute_query(self, sql, params=None):
            seen.append(" ".join(sql.split()))

    write_platform_identity(_Recorder(), 42, "instagram", {"ig_user_id": "1784140"})
    merge = [s for s in seen if "INSERT INTO artist_credentials" in s]
    assert merge and "|| EXCLUDED.extra_config" in merge[0], (
        "the upsert no longer merges — saving Instagram would erase account_id"
    )


# ════════════════════════════════════════════════════════════════════════════
#  L'ensemble des écrivains se DÉRIVE de la table, il ne se liste plus
# ════════════════════════════════════════════════════════════════════════════
#
# `IDENTITY_WRITERS` ci-dessus est une liste tenue à la main de DEUX entrées, et
# c'est ce qui a coûté un P1 le 2026-09-18 : un TROISIÈME écrivain,
# `src/dashboard/views/credentials/_from_signup.py:145`, né le 2026-09-05, appelait
# `_save_credentials` sans jamais `write_platform_identity`. Le miroir
# `saas_artists.spotify_artist_id` restait NULL, le locataire s'affichait « connecté »
# sur tous les écrans, et `spotify_api_daily` ne le sélectionnait jamais — le scénario
# EXACT du canari du 2026-08-21, rejoué par un chemin né après lui.
#
# Un écrivain n'entre pas tout seul dans une liste. Les tests ci-dessous dérivent
# l'ensemble depuis la TABLE — pas depuis un nom de fonction d'aide, parce qu'un
# prédicat sur `_save_credentials` perdrait `tools/create_canary.py`, qui est
# précisément l'écrivain dont l'omission a causé l'incident d'origine, et
# `meta_extra_accounts.py`, qui n'appelle ni l'un ni l'autre.

_ARBRES = ("src/**/*.py", "tools/**/*.py", "airflow/**/*.py", ".claude/scripts/**/*.py")

# Les deux modules qui DÉFINISSENT les chemins partagés : ils nomment la table et les
# fonctions par construction, ce n'est pas de l'écriture par un appelant.
_DEFINITIONS = {
    "src/utils/tenant_identity.py",
    "src/dashboard/views/credentials/_core.py",
}


def _ecrivains_de_credentials() -> dict:
    """{chemin relatif: raisons} pour tout module qui ÉCRIT `artist_credentials`.

    Trois portes, réunies — la table d'abord, les fonctions ensuite :
      (a) une requête nommant `INSERT INTO artist_credentials` / `UPDATE artist_credentials`
      (b) un appel à `_save_credentials`
      (c) un appel à `write_platform_identity`

    On lit le CODE, jamais le texte brut : `tests/code_text.code_of` retire
    commentaires et docstrings. Sans ça, ce fichier-ci — qui explique le défaut —
    se déclarerait lui-même écrivain, et ce dépôt a mesuré six fois en une séance
    qu'une assertion de présence se satisfait de la prose du fichier qu'elle inspecte
    (`guard-satisfied-by-its-own-comment`).
    """
    from tests.code_text import code_of

    trouves = {}
    for motif in _ARBRES:
        for path in ROOT.glob(motif):
            rel = str(path.relative_to(ROOT))
            if rel in _DEFINITIONS or rel.startswith("tests/"):
                continue
            try:
                code = code_of(path)
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            raisons = []
            if "INSERT INTO artist_credentials" in code or "UPDATE artist_credentials" in code:
                raisons.append("SQL sur la table")
            if _calls(path, "_save_credentials"):
                raisons.append("_save_credentials")
            if _calls(path, "write_platform_identity"):
                raisons.append("write_platform_identity")
            if raisons:
                trouves[rel] = raisons
    return trouves


def test_the_derived_writer_set_is_not_vacuous() -> None:
    """Un prédicat cassé rend l'ensemble VIDE, et tous les tests suivants passent sur rien.

    Les trois écrivains ci-dessous sont connus et vérifiés à la main le 2026-09-18.
    Si l'un disparaît de l'ensemble dérivé, c'est le PRÉDICAT qu'il faut lire, pas la
    liste qu'il faut ajuster.
    """
    trouves = _ecrivains_de_credentials()
    assert trouves, "aucun écrivain dérivé — le prédicat ne trouve plus rien"
    connus = {
        "tools/create_canary.py",                                # (c) seule
        "src/dashboard/views/credentials/_render.py",            # (b) + (c)
        "src/dashboard/views/credentials/_from_signup.py",       # (c)
    }
    manquants = sorted(connus - set(trouves))
    assert not manquants, (
        f"le prédicat a perdu des écrivains connus : {manquants}. Un prédicat qui ne "
        "voit que `_save_credentials` perd `create_canary.py` — l'écrivain dont "
        "l'omission a causé l'incident du 2026-08-21."
    )


def test_every_derived_writer_of_a_mirrored_identity_writes_the_mirror() -> None:
    """Le garde que `IDENTITY_WRITERS` ne pouvait pas être.

    Un module qui écrit `artist_credentials` ET nomme un champ d'identité MIROITÉ doit
    passer par `write_platform_identity` — sinon la colonne de `saas_artists` reste
    NULL et le DAG ne sélectionne jamais ce locataire.
    """
    from src.utils.tenant_identity import PLATFORM_IDENTITIES

    from tests.code_text import code_of

    champs_miroites = {spec.field for spec in PLATFORM_IDENTITIES.values() if spec.mirror}
    assert champs_miroites, "aucune plateforme miroitée — ce test vérifierait le vide"

    fautifs = []
    for rel in sorted(_ecrivains_de_credentials()):
        code = code_of(ROOT / rel)
        if not any(champ in code for champ in champs_miroites):
            continue                       # n'écrit aucune identité miroitée
        if not _calls(ROOT / rel, "write_platform_identity"):
            fautifs.append(rel)
    assert not fautifs, (
        "ces modules écrivent une identité MIROITÉE sans appeler "
        f"`write_platform_identity` : {fautifs}. La colonne de `saas_artists` restera "
        "NULL : le locataire s'affichera « connecté » partout et le DAG ne le "
        "sélectionnera jamais. C'est le canari du 2026-08-21, et le 2026-09-18 la "
        "même forme est revenue par `_from_signup.py` parce que `IDENTITY_WRITERS` "
        "était une liste de deux entrées."
    )


def test_the_hand_written_list_is_a_subset_of_what_is_derived() -> None:
    """La liste manuelle survit comme documentation, jamais comme périmètre.

    Si elle nomme un fichier que la dérivation ne voit pas, c'est l'un des deux qui a
    tort — et il faut le savoir, au lieu de laisser les deux diverger en silence.
    """
    derives = set(_ecrivains_de_credentials())
    orphelins = sorted(set(IDENTITY_WRITERS) - derives)
    assert not orphelins, (
        f"`IDENTITY_WRITERS` nomme des fichiers que la dérivation ne voit pas : "
        f"{orphelins}. Soit le fichier a changé, soit le prédicat est trop étroit."
    )
