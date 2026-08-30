"""Un compteur de locataires ne compte pas les machines qu'on a créées soi-même.

Classe `counter-includes-our-own-robots`. Le canari est un locataire que NOUS
créons pour prouver la collecte ; il porte `is_canary = TRUE` depuis la migration
064, et `credential_loader.load_all_artists(exclude_canaries=True)` fait déjà la
distinction. Les compteurs, eux, comptaient « tout ce qui est actif » — dont le
signal de confiance PUBLIC affiché sous « {n} artistes utilisent streaMLytics »
sur la page d'inscription, à un visiteur qui n'a aucun moyen de recouper.

Garde structurel : on inspecte le SQL réellement exécuté, pas un commentaire.
"""
import ast
import importlib
import pathlib

import pytest

_SURFACES = [
    ("src/dashboard/utils/live_pulse.py", "compteur public + pulse admin"),
    ("src/dashboard/views/admin.py", "KPI admin « artistes actifs »"),
]


def _tenant_count_queries(path: pathlib.Path) -> list:
    """Les littéraux SQL qui COMPTENT des lignes de `saas_artists`.

    Reconstitue les f-strings, **en résolvant les constantes de module qu'elles
    interpolent**. Le prédicat d'exclusion vit justement dans une constante
    (`_HUMAN_TENANTS`) : une version de ce test qui ne concaténait que les parties
    littérales le déclarait absent alors qu'il était là — le garde était rouge sur
    du code correct, ce qui l'aurait fait supprimer plutôt que croire.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    consts = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            consts[node.targets[0].id] = node.value.value

    # …et les constantes IMPORTÉES. Le prédicat a quitté ces deux fichiers le
    # 2026-08-31 pour `src/utils/tenant_kind.py`, précisément parce qu'il y était
    # recopié en trois exemplaires. Ce test est alors redevenu rouge sur du code
    # correct — la sœur exacte du cas que son docstring raconte déjà. Un nom peut
    # venir d'un `import` autant que d'une affectation ; ne résoudre qu'une des deux
    # formes, c'est mesurer où la constante était hier.
    # `ast.walk`, pas `tree.body` : admin.py importe DANS la fonction.
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        try:
            mod = importlib.import_module(node.module)
        except Exception:                   # noqa: BLE001 — un import qui échoue n'est
            continue                        # pas une constante à résoudre
        for alias in node.names:
            value = getattr(mod, alias.name, None)
            if isinstance(value, str):
                consts[alias.asname or alias.name] = value

    def _render(node) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                elif (isinstance(v, ast.FormattedValue)
                      and isinstance(v.value, ast.Name)):
                    parts.append(consts.get(v.value.id, ""))
            return "".join(parts)
        return ""

    # Les morceaux littéraux D'UNE f-string sont eux-mêmes des `ast.Constant`, et
    # `ast.walk` les visite séparément. Sans cette exclusion, le fragment
    # « … FROM saas_artists WHERE » d'avant l'interpolation compte comme une
    # requête à part entière — sans le prédicat, donc toujours en faute.
    inner = {id(v) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr)
             for v in node.values}

    out = []
    for node in ast.walk(tree):
        if id(node) in inner:
            continue
        text = _render(node)
        if not text:
            continue
        upper = text.upper()
        if "COUNT(*)" in upper and "SAAS_ARTISTS" in upper:
            out.append((node.lineno, text))
    return out


@pytest.mark.parametrize("relpath,label", _SURFACES, ids=[s[0] for s in _SURFACES])
def test_tenant_counts_exclude_canaries(relpath, label):
    path = pathlib.Path(relpath)
    queries = _tenant_count_queries(path)
    assert queries, f"aucun COUNT sur saas_artists trouvé dans {relpath} — test périmé ?"
    for lineno, text in queries:
        assert "is_canary" in text.lower(), (
            f"{relpath}:{lineno} ({label}) compte les canaris parmi les artistes. "
            "Un signal de confiance gonflé par nos propres robots est un chiffre faux."
        )


def test_the_public_page_shows_no_real_artist_name_as_an_example():
    """Le nom d'artiste du propriétaire était l'exemple de CHAQUE inscription."""
    for relpath in ("src/dashboard/views/register.py",
                    "src/dashboard/utils/i18n_catalog/register.py"):
        text = pathlib.Path(relpath).read_text(encoding="utf-8")
        assert "1x7xxxxxxx" not in text, (
            f"{relpath} montre le nom d'artiste du propriétaire de la plateforme "
            "comme valeur d'exemple sur la page d'inscription publique."
        )
