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


def _grinch_steps():
    """The 2026-08-24 shape: step 2 red, and the step that mattered comes AFTER it."""
    return [("central apps", lambda: True),
            ("tenant identity", lambda: False),
            ("connection tests", lambda: True)]


def test_the_gate_still_stops_by_default(capsys):
    """La porte reste une porte : `--diagnose` est une option, jamais le défaut."""
    from tools.artist_preflight import run_steps

    rc, ran, failed = run_steps(_grinch_steps())
    assert rc == 1 and failed == ["tenant identity"], "un préflight rouge sort non-zéro"
    assert ran == ["central apps", "tenant identity"], (
        f"le mode par défaut a joué {ran} : il ne s'arrête plus au premier rouge, "
        "donc la porte a disparu")
    assert "--diagnose" in capsys.readouterr().out, "l'arrêt ne nomme plus la sortie"


def test_diagnose_mode_still_returns_a_red_verdict():
    """Tout mesurer ne veut pas dire tout excuser."""
    from tools.artist_preflight import run_steps

    rc, ran, failed = run_steps(_grinch_steps(), diagnose=True)
    assert ran == [label for label, _ in _grinch_steps()], (
        f"`--diagnose` n'a joué que {ran} : le test de connexion de GRiNCH ne tourne "
        "toujours pas")
    assert rc == 1 and failed == ["tenant identity"], (
        "le mode diagnostic rend un vert sur un locataire cassé")


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity: the green path returns 0 in both modes — the two tests above are
    red because of the red step, not because `run_steps` always returns 1."""
    from tools.artist_preflight import run_steps

    green = [("a", lambda: True), ("b", lambda: True)]
    assert run_steps(green)[:2] == (0, ["a", "b"])
    assert run_steps(green, diagnose=True)[:2] == (0, ["a", "b"])
