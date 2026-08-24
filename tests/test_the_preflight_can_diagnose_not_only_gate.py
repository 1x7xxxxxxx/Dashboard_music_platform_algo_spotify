"""Une porte qui s'arrête au premier rouge ne peut pas servir de lampe.

Classe `a-fail-fast-gate-cannot-diagnose`.

`tools/artist_preflight.py` s'arrête à la première étape rouge, et c'est **voulu** :
deux sessions de test artiste ont brûlé une heure chacune à découvrir en direct que
les apps partagées étaient mal configurées, et tout ce qui suit un rouge est non
prouvé. Le dire est le travail de l'outil.

Mais le runbook fait lancer cette même commande pour **diagnostiquer** un artiste
déjà inscrit. Mesuré le 2026-08-24 sur GRiNCH (artist_id=13), dont l'alerte nocturne
dit « 🔴 NE COLLECTE PAS : GRiNCH (☁️ SoundCloud) » : quatre identités absentes →
arrêt à l'étape 2 → **le test de connexion SoundCloud, la seule plateforme qu'il a
déclarée et justement celle qui ne collecte pas, n'a jamais été lancé**. L'outil de
diagnostic refusait de regarder la chose à diagnostiquer.

On ne relâche pas la porte : on ajoute la lampe (`--diagnose`), et le message d'arrêt
la nomme — un opérateur qui tombe sur le STOP doit apprendre là qu'une autre commande
existe, pas six mois plus tard.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "tools" / "artist_preflight.py"


def _source() -> str:
    return PREFLIGHT.read_text(encoding="utf-8")


def test_the_diagnose_flag_exists():
    tree = ast.parse(_source())
    flags = {
        arg.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        for arg in node.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    }
    assert "--diagnose" in flags, (
        "le préflight n'expose plus `--diagnose` : il redevient une porte incapable "
        "de diagnostiquer un artiste déjà inscrit et à moitié configuré."
    )


def test_the_stop_message_names_the_way_out():
    """Un opérateur bloqué doit apprendre la sortie AU MOMENT où il est bloqué."""
    src = _source()
    stop_idx = src.find("STOP —")
    assert stop_idx != -1, "le message d'arrêt a disparu — la porte ne dit plus rien"
    following = src[stop_idx:stop_idx + 700]
    assert "--diagnose" in following, (
        "le message d'arrêt ne nomme pas `--diagnose`. Une option que personne ne "
        "découvre au moment utile n'existe pas."
    )


def test_the_gate_still_stops_by_default():
    """La porte reste une porte : `--diagnose` est une option, jamais le défaut."""
    src = _source()
    assert "if not args.diagnose:" in src, (
        "l'arrêt au premier rouge n'est plus conditionné à l'ABSENCE de "
        "`--diagnose` : soit la porte a disparu, soit le diagnostic est devenu le "
        "comportement par défaut. Les deux sont des régressions."
    )
    assert "return 1" in src, "un préflight rouge doit sortir non-zéro"


def test_diagnose_mode_still_returns_a_red_verdict():
    """Tout mesurer ne veut pas dire tout excuser."""
    src = _source()
    assert "failed_steps" in src and "Diagnostic terminé" in src, (
        "le mode diagnostic ne récapitule plus les étapes rouges — il rendrait un "
        "vert sur un locataire cassé."
    )
