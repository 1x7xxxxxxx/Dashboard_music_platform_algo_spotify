"""
Guard — un artiste sans profil SoundCloud, mais avec des titres déclarés, est collecté.

Type: Sub
Uses: ast, pytest
Triggers: pytest
Depends on: src/collectors/soundcloud_api_collector.py, airflow/dags/soundcloud_daily.py
Persists in: nothing

Error class: the-feature-exists-and-the-path-never-reaches-it.

Mesuré le 2026-08-23 sur le cas GRiNCH. La fonctionnalité « Mes titres hébergés sur
d'autres comptes » existait, complète et testée : widget, résolution d'URL, stockage dans
`track_platform_link`, unicité garantie par `migrations/074`, consommation par
`fetch_claimed_tracks`. Et elle n'était **jamais atteinte** pour l'artiste qui en avait le
plus besoin.

Deux verrous, aux deux bouts :

* `soundcloud_daily.py` sautait le locataire dès que `user_id` était vide — **avant**
  d'avoir lu ses déclarations ;
* le constructeur du collecteur levait sur le même critère.

Pour un artiste signé sur un label, le profil personnel n'existe pas et n'existera jamais.
L'unité collectable est le TITRE : `GET /tracks/{id}` rend ses écoutes quel que soit le
compte qui l'héberge. Exiger un profil, c'était exiger la seule chose qu'il ne peut pas
fournir.

Le trou était invisible parce que **rien n'échouait** : le DAG passait au vert, le
locataire était proprement journalisé comme « sauté », et la raison inscrite —
« no SoundCloud user_id declared » — était exacte.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_COLLECTOR = _ROOT / "src" / "collectors" / "soundcloud_api_collector.py"
_DAG = _ROOT / "airflow" / "dags" / "soundcloud_daily.py"
_CLAIMS = _ROOT / "src" / "utils" / "claimed_tracks.py"


def test_the_shared_reader_exists():
    """Deux appelants, une seule lecture — sinon elle diverge."""
    tree = ast.parse(_CLAIMS.read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "has_claimed_tracks" in names, (
        "`has_claimed_tracks` a disparu de claimed_tracks.py : le DAG et le collecteur "
        "reporteraient chacun leur propre lecture."
    )


def test_the_collector_does_not_raise_when_tracks_are_declared():
    """Le constructeur ne doit plus lever sur le seul critère du `user_id`."""
    src = _COLLECTOR.read_text(encoding="utf-8")
    tree = ast.parse(src)
    init = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    raises = [n for n in ast.walk(init) if isinstance(n, ast.Raise)]
    assert raises, "le constructeur ne lève plus du tout — l'absence totale d'identité doit rester une erreur"
    # La condition du raise doit mentionner les titres déclarés.
    guarded = [n for n in ast.walk(init) if isinstance(n, ast.If)
               and "_has_claimed_tracks" in ast.dump(n.test)]
    assert guarded, (
        "le `raise` du constructeur ne consulte pas les titres déclarés : un artiste "
        "signé sur un label reste refusé alors que ses titres sont collectables."
    )


def test_the_collector_skips_the_profile_call_without_a_user_id():
    """Sans profil, il n'y a pas d'URL de profil à appeler — seulement les déclarations."""
    src = _COLLECTOR.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "fetch_tracks")
    # Le prédicat vise l'affectation de `url`, pas « un ternaire quelque part » : la
    # première version cherchait n'importe quel `IfExp` de la fonction et était donc
    # VERTE avant le correctif — il en existait déjà un, sans rapport. Huitième fois
    # que le prédicat d'un garde vise le voisinage au lieu de la question.
    conditional_url = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "url" for t in n.targets)
        and isinstance(n.value, ast.IfExp)
        and "user_id" in ast.dump(n.value.test)
    ]
    assert conditional_url, (
        "`fetch_tracks` construit l'URL du profil sans condition sur `user_id` : sans "
        "profil elle vaudrait `/users//tracks` et l'appel partirait quand même."
    )


def skips_without_claims(source: str) -> "list[str] | None":
    """Every branch that SKIPS a tenant on `user_id` (an `if` on it holding a
    `continue`) and does not call `has_claimed_tracks` inside it. None when no such
    branch exists — the DAG changed shape and this guard is blind. Pure.

    ALL of them, not "at least one": with `any`, this guard stayed green when the
    COLLECTION lost its call because the PREFLIGHT carried one (2026-09-18).
    """
    tree = ast.parse(source)
    branches = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                and "user_id" in ast.unparse(n.test)
                and any(isinstance(x, ast.Continue) for x in ast.walk(n))]
    if not branches:
        return None
    return [ast.unparse(b.test) + f" (ligne {b.lineno})" for b in branches
            if not any(isinstance(c, ast.Call)
                       and getattr(c.func, "id", "") == "has_claimed_tracks"
                       for c in ast.walk(b))]


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity, class `the-feature-exists-and-the-path-never-reaches-it`: the
    2026-09-18 shape — the preflight reads the claims, the collection skips on
    `user_id` alone — names the collection branch; both reading the claims pass;
    a DAG with no skipping branch is reported blind, not clean."""
    dag = ("def preflight(tenants):\n"
           "    for t in tenants:\n"
           "        if not t.user_id and not has_claimed_tracks(t):\n"
           "            continue\n"
           "def collect(tenants):\n"
           "    for t in tenants:\n"
           "        if t.user_id:\n"                      # decides nothing: no skip
           "            log.info(t.user_id)\n"
           "        if not t.user_id:\n"
           "            log.info('no user_id')\n"         # a call, but not the claims
           "            continue\n")
    assert skips_without_claims(dag) == ["not t.user_id (ligne 9)"]
    fixed = dag.replace("        if not t.user_id:\n",
                        "        if not t.user_id and not has_claimed_tracks(t):\n")
    assert skips_without_claims(fixed) == []
    assert skips_without_claims("def collect(t):\n    return t\n") is None


def test_the_dag_reads_the_claims_before_skipping():
    src = _DAG.read_text(encoding="utf-8")
    assert "has_claimed_tracks" in src, (
        "le DAG saute encore le locataire sur le seul `user_id`, sans lire ses "
        "déclarations. C'est le verrou d'entrée : le collecteur peut bien accepter, "
        "il ne sera jamais construit."
    )
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and (getattr(n.func, "id", "") == "has_claimed_tracks")]
    assert calls, "`has_claimed_tracks` est mentionné mais jamais appelé"

    # ⚠️ « appelé quelque part dans le fichier » NE SUFFIT PAS, et ce n'est pas
    # théorique : le 2026-09-18, aligner le PRÉCONTRÔLE sur la collecte a ajouté un
    # second appel — et ce test est alors resté VERT quand on a retiré celui de la
    # COLLECTE. Un garde de présence devient aveugle dès qu'un second site fournit
    # la présence. On exige donc l'appel DANS la branche qui décide de sauter :
    # celle qui teste `user_id` et porte un `continue`.
    nues = skips_without_claims(src)
    assert nues is not None, (
        "aucune branche ne teste `user_id` pour décider de sauter — la forme du DAG "
        "a changé, et ce test ne sait plus où regarder.")
    assert not nues, (
        f"{nues} sautent sur un `user_id` vide SANS lire les déclarations. Un appel "
        "ailleurs dans le fichier ne protège pas cette branche-là : chaque endroit "
        "qui saute refuse un artiste signé sur un label pour la seule chose qu'il "
        "ne peut pas fournir.")


def test_the_skip_reason_says_both_conditions():
    """La raison journalisée doit nommer ce qui manque VRAIMENT, sinon elle égare."""
    src = _DAG.read_text(encoding="utf-8")
    assert "no claimed track" in src, (
        "la raison inscrite dans etl_run_log dit encore « no SoundCloud user_id "
        "declared » seul — exact hier, incomplet aujourd'hui : il manque les deux."
    )
