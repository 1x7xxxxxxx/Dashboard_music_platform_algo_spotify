"""Un test qui ÉCRIT dans la base partagée doit dire avec qui il se sérialise.

Type: Utility
Uses: ast
Triggers: pytest
Persists in: nothing

Error class `a-shared-database-read-while-another-test-writes-it`.

Mesuré le 2026-09-16 : **deux rouges de cette forme dans la même soirée**, dans deux
fichiers sans rapport, chacun VERT quand on le relance seul.

  * `test_the_hypeddit_ratio_is_the_ratio_of_sums` — une fixture insère une campagne
    rivale sur l'artiste 1 pendant que trois tests du même fichier le lisent ;
  * `test_the_signup_links_become_credentials` — il cherche « un autre locataire qui
    déclare une identité Spotify » et vérifie qu'un doublon est refusé, pendant que
    `test_tenant_identity_mirrors` écrit une identité sonde et la restaure dans un
    `finally`. Entre les deux instants, la valeur a bougé.

Un test vert en isolation et rouge en parallèle est le pire des deux mondes : il ne
décrit plus le code, il décrit l'ordonnancement, et il apprend à relancer plutôt qu'à
lire. `--dist loadgroup` — que le `Makefile` passe déjà — existe exactement pour ça :
un `xdist_group` commun sérialise les fichiers qui se marchent dessus, et ne coûte que
cette sérialisation.

Ce que ce garde NE fait pas
----------------------------
Il n'exige pas un groupe de tout test qui touche la base. Un test qui crée SON locataire
et ne lit que lui n'a rien à craindre de personne — `test_hypeddit_write_path` fabrique
son propre `artist_id` et le supprime, il est isolé par construction. Exiger un groupe
partout produirait une suite sérialisée, c'est-à-dire la perte des `-n auto` que ce
dépôt a mesurés à 2,74×.

La question posée est plus étroite : **écrire sur un locataire que ce fichier n'a pas
créé**. C'est le seul cas où un autre fichier peut lire au mauvais moment.

Mutation record — 2026-09-16, vue rouge : `xdist_group` retiré de
`tests/test_tenant_identity_mirrors.py` → ce garde nomme le fichier et échoue ; remis,
vert. Seconde mutation : un fichier synthétique écrivant sur `artist_id = 1` sans
groupe → rouge lui aussi, donc le prédicat ne tient pas qu'à la liste.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"

# Les tables dont une ligne appartient à un locataire QUE LE TEST N'A PAS CRÉÉ.
_SHARED_WRITES = (
    "INSERT INTO artist_credentials",
    "UPDATE saas_artists SET spotify_artist_id",
    "INSERT INTO hypeddit_campaigns",
    "INSERT INTO track_platform_link",
    # Ajoutées le 2026-09-17, après un rouge intermittent que ce garde ne voyait pas.
    # `test_nothing_overwritten_is_lost` mute une ligne à clé LITTÉRALE de
    # `s4a_song_timeline` et purge `data_revisions` pour le même artiste, à l'entrée
    # ET à la sortie de sa fixture — cinq tests sur la même ligne. Aucune des deux
    # tables n'était listée ici : le garde regardait ailleurs.
    "INSERT INTO s4a_song_timeline",
    "DELETE FROM data_revisions",
)
# Écrire par le chemin partagé compte autant qu'un INSERT littéral.
_SHARED_WRITERS = {"write_platform_identity"}


def _creates_its_own_tenant(tree: ast.AST) -> bool:
    """Fabrique-t-il son propre locataire ? Alors personne d'autre ne le lit.

    ⚠️ Terme ajouté après que la première version ait dénoncé TROIS fichiers à tort —
    `test_freshness_and_readiness_db`, `test_identity_conflict_names_no_other_tenant`,
    `test_saving_a_tab_never_destroys_a_secret`. Ils écrivent bien `artist_credentials`,
    mais sur un locataire qu'ils viennent de créer par
    `INSERT INTO saas_artists … RETURNING id` et qu'ils suppriment ensuite : isolés par
    construction. La docstring de ce fichier promettait déjà cette exemption ; elle
    n'était pas implémentée. C'est exactement le reproche qu'on fait aux gardes ici —
    une promesse écrite et non tenue se lit comme une couverture.

    ⚠️ Resserré le 2026-09-17 : il exemptait sur la seule présence de la chaîne
    `INSERT INTO saas_artists`, ce que la docstring ci-dessus ne promettait PAS — elle
    parle d'un locataire créé « par `INSERT INTO saas_artists … RETURNING id` et
    supprimé ensuite ». La différence est toute la sûreté : un id MINTÉ par test
    n'est visé par personne d'autre, un id LITTÉRAL l'est par tout le monde.
    `test_nothing_overwritten_is_lost` écrit `INSERT INTO saas_artists (id, …) VALUES
    (999471, …) ON CONFLICT (id) DO NOTHING` — la chaîne y est, l'isolation non. Il a
    été exempté pendant tout ce temps, et il a fini par rougir en parallèle.

    Le prédicat exige donc les DEUX marques dans le même fichier : l'insertion et le
    `RETURNING id` qui prouve que l'identifiant est frappé, pas choisi.
    """
    src = ast.walk(tree)
    consts = [n.value for n in src
              if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    inserts = any("INSERT INTO saas_artists" in c for c in consts)
    minted = any("RETURNING id" in c for c in consts)
    return inserts and minted


def _writes_a_shared_tenant(tree: ast.AST) -> bool:
    """Écrit-il sur un locataire préexistant — donc lisible par un autre fichier ?

    On lit l'AST, pas le texte : une chaîne SQL est une `ast.Constant`, un commentaire
    n'en est pas une. Un garde textuel se déclencherait sur sa propre documentation —
    quatre pris verts sur leur propre défaut en une soirée, dans ce dépôt.

    ⚠️ Et il se déclenchait quand même sur LUI-MÊME : les aiguilles de `_SHARED_WRITES`
    sont des `ast.Constant` de ce module. Une aiguille NUE n'est pas une requête — pas
    de colonnes, pas de `VALUES` — donc l'égalité exacte la distingue de son usage.
    C'est `a-kill-pattern-that-matches-its-own-shell`, troisième instance de la journée.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in _SHARED_WRITES:
                continue          # l'aiguille elle-même, pas une requête
            if any(needle in node.value for needle in _SHARED_WRITES):
                return True
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in _SHARED_WRITERS:
                return True
    return False


def _declares_a_group(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "xdist_group":
            return True
    return False


def _offenders() -> list[str]:
    bad = []
    for path in sorted(TESTS.rglob("test_*.py")):
        if "__pycache__" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        if (_writes_a_shared_tenant(tree) and not _creates_its_own_tenant(tree)
                and not _declares_a_group(tree)):
            bad.append(str(path.relative_to(REPO)))
    return bad


def test_the_predicate_still_sees_the_files_it_was_written_for() -> None:
    """Non-vacuité : ces cinq-là DOIVENT rester détectés comme écrivains partagés."""
    # ⚠️ `test_the_signup_links_become_credentials` n'est PAS dans cette liste, et c'est
    # le point : il ne fait que LIRE une identité déclarée par un autre locataire. Ce
    # garde n'enforce que le côté ÉCRIVAIN — un lecteur rejoint le groupe à la main,
    # parce qu'aucune lecture ne se distingue structurellement d'une lecture inoffensive.
    # Le dire ici plutôt que de gonfler la liste : une non-vacuité qui ment sur ce
    # qu'elle couvre est pire qu'une non-vacuité étroite.
    known = [
        "test_tenant_identity_mirrors.py",
        "test_identity_uniqueness.py",
        "test_the_hypeddit_ratio_is_the_ratio_of_sums.py",
    ]
    for name in known:
        tree = ast.parse((TESTS / name).read_text(encoding="utf-8"))
        assert _writes_a_shared_tenant(tree), (
            f"{name} n'est plus vu comme écrivant sur un locataire partagé — le "
            "prédicat est devenu aveugle, et ce garde ne garde plus rien")


def test_every_shared_writer_declares_an_xdist_group() -> None:
    offenders = _offenders()
    assert not offenders, (
        "ces tests écrivent sur un locataire qu'ils n'ont pas créé, sans déclarer de "
        "`pytest.mark.xdist_group` :\n  " + "\n  ".join(offenders)
        + "\n\nSous `-n auto` rien ne les tient sur le même worker qu'un test qui LIT "
          "le même locataire : le lecteur mesure alors entre l'écriture et sa remise "
          "en état. Deux rouges de cette forme le 2026-09-16, chacun vert en "
          "isolation. Ajouter le groupe, ou fabriquer son propre locataire.")
