"""Le dépôt d'abord, la notice ensuite — et une consigne à un seul endroit.

Demandé le 2026-09-06, en regardant la page :

  * le mode d'emploi du relevé SACEM doit vivre dans l'onglet 🎼 Royalties SACEM,
    pas dans l'import de fichiers ;
  * Spotify for Artists à gauche, Apple Music à droite ;
  * les captures d'écran APRÈS la zone de dépôt.

Ce que ce fichier garde, et pourquoi chaque point est vérifiable :

1. **Une consigne, un endroit.** Le mode d'emploi SACEM existait mot pour mot dans
   `upload_csv.render_uploader` ET dans `views/sacem.py`. Deux copies d'un même
   texte, c'est une copie qui se périmera sans que personne ne le voie — la classe
   `one-guide-three-sources` de ce dépôt.

2. **L'ordre est mesurable.** « Après la zone de dépôt » se lit dans la position de
   l'appel : `render_csv_guides()` doit venir après `st.file_uploader`, et avant le
   `return` qui coupe la fonction quand rien n'est déposé — sinon la notice
   n'apparaîtrait qu'une fois le fichier choisi, c'est-à-dire trop tard.

3. **Les deux plateformes nommées sont côte à côte**, dans cet ordre.
"""
import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_UPLOAD = _ROOT / "src/dashboard/views/upload_csv.py"
_GUIDES_ST = _ROOT / "src/dashboard/content/csv_guides_st.py"


def _fn(path: pathlib.Path, name: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(n, ast.FunctionDef) and n.name == name)


def test_the_sacem_howto_lives_in_exactly_one_view():
    """Lu en AST sur les clés de traduction, pas sur le texte français.

    Un `grep` du mode d'emploi serait satisfait par le commentaire qui explique
    justement son retrait — trois gardes de ce dépôt ont déjà été pris au vert sur
    leur propre explication.
    """
    holders = []
    for path in (_ROOT / "src/dashboard/views").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "t"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and str(node.args[0].value).endswith(("howto_header", "howto_body"))
                    and "sacem" in str(node.args[0].value).lower()):
                holders.append(f"{path.name}:{node.args[0].value}")

    views = {h.split(":")[0] for h in holders}
    assert views == {"sacem.py"}, (
        f"le mode d'emploi du relevé SACEM est rendu par {sorted(views)}. Il "
        "appartient à la vue où l'on se trouve quand on cherche un relevé SACEM ; "
        "ailleurs, c'est une copie qui se périmera en silence.")


def test_the_guides_come_after_the_drop_zone_and_after_the_result():
    """Les guides sont rendus APRÈS la zone de dépôt, et APRÈS ce qu'on a déposé.

    RÉANCRÉ le 2026-09-06. Ce test exigeait qu'ils soient rendus AVANT le retour
    anticipé — donc entre la zone de dépôt et la détection. Demandé le même jour :
    « déplace les onglets à dérouler de process pour télécharger EN DESSOUS de la
    détection ».

    La question gardée ne change pas : la page s'ouvre sur le GESTE, jamais sur sa
    notice. Ce qui change est ce qu'on considère comme « après » — après le dépôt ne
    suffisait pas, il faut après le RÉSULTAT du dépôt. Quelqu'un qui vient de voir
    quinze fichiers refusés a besoin de relire comment les exporter, et c'est là
    qu'il est.

    Les guides sont donc rendus DEUX fois dans la fonction, et c'est voulu : une fois
    dans la branche « rien de déposé » — le seul moment où l'on ne sait pas encore
    quoi télécharger — et une fois tout en bas, sous les résultats.
    """
    fn = _fn(_UPLOAD, "render_uploader")

    def _lines(pred) -> list[int]:
        return sorted(n.lineno for n in ast.walk(fn) if pred(n))

    uploader = _lines(lambda n: isinstance(n, ast.Call)
                      and getattr(n.func, "attr", "") == "file_uploader")
    guides = _lines(lambda n: isinstance(n, ast.Call)
                    and getattr(n.func, "id", "") == "render_csv_guides")
    tables = _lines(lambda n: isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") == "dataframe")
    assert uploader and guides, "la zone de dépôt ou les guides ont disparu"
    assert min(guides) > min(uploader), (
        "les guides sont rendus AVANT la zone de dépôt : la page s'ouvre sur la "
        "notice au lieu du geste")

    assert tables, "le tableau de détection a disparu"
    assert max(guides) > max(tables), (
        "les guides restent au-dessus du dernier tableau : ils repoussent le "
        "résultat de l'import, qui est ce qu'on vient lire après avoir déposé")

    # Et ils restent joignables quand RIEN n'est déposé : sinon la page d'accueil de
    # l'import n'explique plus où trouver les fichiers.
    early = next((n.lineno for n in ast.walk(fn)
                  if isinstance(n, ast.Return) and n.value is None
                  and n.lineno > min(uploader)), None)
    assert early is not None, "le retour anticipé a disparu — vérifier ce test"
    assert min(guides) < early, (
        "aucun guide n'est rendu avant le retour anticipé : un artiste qui arrive "
        "les mains vides ne voit plus comment exporter ses fichiers")



def _paired_keys() -> tuple[str, ...]:
    """Les guides rendus côte à côte, en haut — lus dans la DONNÉE.

    RÉANCRÉ le 2026-09-06. Ces trois tests lisaient `csv_guides_st._SIDE_BY_SIDE`,
    une constante du RENDU qui énumérait ("s4a", "apple") et laissait tout le reste
    tomber dans un groupe par défaut. Ce groupe porte désormais un intitulé
    (« 💿 Mon distributeur »), ce qui rendait la constante dangereuse : un guide de
    plateforme ajouté demain aurait hérité d'un titre faux, en silence — la classe
    `layout-keyed-by-a-hand-written-list`.

    La question gardée ne change pas : Spotify for Artists à gauche, Apple à droite,
    côte à côte, avec leurs captures. Seule la source de vérité change — la famille
    déclarée sur chaque guide, plus une liste tapée dans le rendu.
    """
    from src.dashboard.content.csv_guides import CSV_GUIDES, FAMILY_PLATFORM
    return tuple(g.key for g in CSV_GUIDES if g.family == FAMILY_PLATFORM)


def test_spotify_is_left_and_apple_is_right():
    from src.dashboard.content.csv_guides import CSV_GUIDES

    assert _paired_keys() == ("s4a", "apple"), (
        "l'ordre gauche/droite a changé : Spotify for Artists à gauche, Apple à "
        f"droite (demandé le 2026-09-06). Lu : {_paired_keys()}")
    keys = {g.key for g in CSV_GUIDES}
    assert set(_paired_keys()) <= keys, (
        f"{sorted(set(_paired_keys()) - keys)} n'est plus un guide : la paire "
        "mise en avant pointe dans le vide et la page perdrait une colonne")


def test_the_paired_guides_carry_screenshots_that_exist():
    """« Avec quelques screens » — un fichier absent se dégrade en silence."""
    from src.dashboard.content.csv_guides import CSV_GUIDES, screenshot_path

    for guide in (g for g in CSV_GUIDES if g.key in _paired_keys()):
        shots = [s.screenshot for s in guide.steps if s.screenshot]
        assert shots, f"{guide.key} n'a plus aucune capture"
        missing = [s for s in shots if not screenshot_path(s).exists()]
        assert not missing, (
            f"{guide.key} : captures déclarées et absentes du disque {missing} — "
            "le rendu les saute sans rien dire")


def test_both_columns_are_rendered_side_by_side():
    """La boucle qui rend LA PAIRE doit itérer sur des colonnes.

    Premier jet : « il existe un `st.columns` dans la fonction » — vert sur son
    propre mutant, parce que la rangée des distributeurs en porte un second. On
    vise donc la boucle sur `paired`, et on regarde ce qu'elle parcourt.
    """
    # La boucle vit maintenant dans le helper `_render_in_columns`, appelé une fois
    # pour les plateformes et une fois pour les distributeurs. Viser ce helper plutôt
    # que `render_csv_guides` est ce qui garde la question au bon endroit : c'est LUI
    # qui décide si les guides tiennent sur une ligne.
    fn = _fn(_GUIDES_ST, "_render_in_columns")

    paired_loops = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.For) and "st.columns" in ast.unparse(n.iter)
    ]
    assert paired_loops, (
        "plus aucune boucle ne rend les guides en colonnes")
    for loop in paired_loops:
        assert any(isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "columns"
                   for c in ast.walk(loop.iter)), (
            f"la paire est rendue par `{ast.unparse(loop.iter)}` : Spotify et Apple "
            "sont de nouveau empilés au lieu d'être côte à côte")


def test_a_fully_recognised_batch_imports_without_a_second_click():
    """« ✅ Prêt » et « ✅ Importer » portaient la même coche verte.

    Mesuré le 2026-09-06 : l'artiste a déposé quinze fichiers, lu « Prêt », et le
    journal de production ne portait aucune ligne du jour. Le tableau ne mentait
    pas — il nommait un état intermédiaire comme un état final.

    Ajouté après avoir muté le correctif et vu ce fichier rester VERT : rien n'y
    interrogeait le déclenchement automatique.
    """
    fn = _fn(_UPLOAD, "render_uploader")
    src = ast.unparse(fn)

    # Le bouton doit être une ALTERNATIVE au démarrage automatique, pas la seule
    # porte : `if _auto or st.button(...)`.
    guarded = [n for n in ast.walk(fn)
               if isinstance(n, ast.If)
               and isinstance(n.test, ast.BoolOp)
               and any(isinstance(v, ast.Call)
                       and getattr(v.func, "attr", "") == "button"
                       for v in n.test.values)]
    assert guarded, (
        "l'import ne part QUE sur un clic : un lot entièrement reconnu n'offre "
        "aucun arbitrage, donc le bouton y est une étape de plus, pas une décision. "
        "Attendu `if <auto> or st.button(...)`.")

    assert "session_state" in src, (
        "le démarrage automatique n'est borné par rien : Streamlit ré-exécute le "
        "script à chaque interaction, donc le même dépôt se réimporterait à chaque "
        "clic ailleurs sur la page. Il faut une signature du lot en session.")
