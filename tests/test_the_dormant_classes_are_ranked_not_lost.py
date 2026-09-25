"""Les classes dormantes sont RANGÉES à la fin, jamais retirées.

Type: Test
Uses: json, re
Depends on: .claude/dev-docs/error-classes.md, error-class-health.json
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
Le catalogue portait 402 classes sur 8 400 lignes, dont **206 (51 %)** remplissaient
toutes les conditions du sommeil : jamais récidivé, un balayage a eu lieu et n'a trouvé
aucun autre site, statut `guarded`/`resolved`/`fixed`, et un garde automatique dont le
fichier `tests/…` existe. Un humain qui ouvrait le document rencontrait les 402 dans
l'ordre de leur écriture.

**Pourquoi un titre de section et PAS un second fichier.** C'était le plan, et la
mesure l'a écarté :

* le gain en temps d'une scission est **≈ 0 s** — les 13 s que le catalogue coûte à la
  suite sont dominées par les 8,46 s du cliquet de santé, qui viennent du rejeu de
  l'historique **git** ; scinder le fichier d'aujourd'hui ne change rien aux révisions
  d'hier ;
* le rayon de souffle est de **47 sites lecteurs** (33 en Python, 14 ailleurs), chacun
  devant décider « le fichier actif seul, ou les deux ? ».

Un second fichier qu'un lecteur oublie est la dérive que ce dépôt paie le plus souvent.
Un titre de section coûte une ligne et ne peut être oublié par personne : les trois
parseurs du dépôt l'ignorent déjà, parce qu'aucun n'accepte un titre qui ne soit pas en
kebab-case.

Ce que ce fichier tient
-----------------------
1. **Aucun identifiant n'est perdu** dans le rangement — la vraie peur d'un déplacement
   de 206 blocs.
2. La section existe et **décrit ce qu'elle contient**, en nombre.
3. Le critère reste MÉCANIQUE : une classe rangée là remplit encore les conditions.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
_CAT = ROOT / ".claude" / "dev-docs" / "error-classes.md"
_SANTE = ROOT / ".claude" / "dev-docs" / "error-class-health.json"
_HEAD = re.compile(r"^## ([a-z0-9][a-z0-9-]+)\s*$")
_SEP = "## 💤 Classes DORMANTES"


def _blocs() -> list[tuple[str, str]]:
    out = []
    for b in re.split(r"(?m)^(?=## )", _CAT.read_text(encoding="utf-8"))[1:]:
        m = _HEAD.match(b.split("\n", 1)[0])
        if m:
            out.append((m.group(1), b))
    return out


def _dormante(c: dict) -> bool:
    if c.get("history_additions", 0) != 0:
        return False
    if c.get("siblings_sites") != 0:
        return False
    if c.get("status") not in ("guarded", "resolved", "fixed"):
        return False
    if not c.get("guard_automatic"):
        return False
    g = c.get("guard_ref") or ""
    return g.startswith("tests/") and (ROOT / g.split("::")[0]).exists()


def test_no_identifier_was_lost_in_the_move() -> None:
    """La peur d'un déplacement de 206 blocs, et la seule qui compte."""
    du_catalogue = {cid for cid, _ in _blocs()}
    de_la_sante = set(json.loads(_SANTE.read_text(encoding="utf-8"))["classes"])
    perdues = de_la_sante - du_catalogue
    assert not perdues, (
        f"{len(perdues)} classe(s) présentes dans l'instantané de santé et ABSENTES du "
        f"catalogue : {sorted(perdues)[:5]}. Un rangement qui perd un bloc améliore "
        "tous les taux sans rien livrer — c'est exactement ce que les planchers de "
        "population interdisent.")
    assert len(du_catalogue) == len(_blocs()), (
        "deux blocs portent le même identifiant : le déplacement en a dupliqué un.")


def test_the_dormant_section_exists_and_says_how_many() -> None:
    """Une section qui ne dit pas ce qu'elle contient se lit comme une décharge."""
    texte = _CAT.read_text(encoding="utf-8")
    assert _SEP in texte, (
        "la section des classes dormantes a disparu : les 402 classes sont de nouveau "
        "mêlées, et un lecteur rencontre d'abord celles qui dorment depuis des mois.")
    entete = texte[texte.index(_SEP):texte.index(_SEP) + 1400]
    assert re.search(r"Les \d+ classes qui suivent", entete), (
        "l'en-tête de la section ne dit plus COMBIEN de classes elle contient. Un "
        "nombre écrit est un nombre qu'on peut contredire ; son absence, non.")


def test_every_class_after_the_separator_still_meets_the_criterion() -> None:
    """Le critère reste MÉCANIQUE — il ne devient pas un tiroir où l'on range à la main.

    C'est le risque réel d'une section « dormantes » : qu'on y pousse une classe gênante
    plutôt qu'une classe endormie. Le verdict vient de `error-class-health.json`, que
    personne ne rédige.
    """
    texte = _CAT.read_text(encoding="utf-8")
    apres = texte[texte.index(_SEP):]
    sante = json.loads(_SANTE.read_text(encoding="utf-8"))["classes"]
    rangees = [m.group(1) for b in re.split(r"(?m)^(?=## )", apres)[1:]
               for m in [_HEAD.match(b.split("\n", 1)[0])] if m]
    assert rangees, "la section dormante est vide"
    reveillees = [c for c in rangees if c in sante and not _dormante(sante[c])]
    assert not reveillees, (
        f"{len(reveillees)} classe(s) rangée(s) parmi les dormantes ne remplissent plus "
        f"le critère : {reveillees[:5]}. Leur garde a rougi, ou un balayage a trouvé un "
        "site — elles doivent remonter. Le rangement est mécanique, pas un tiroir.")


def test_the_live_half_is_not_empty_and_is_the_smaller_one() -> None:
    """Anti-vacuité : sans elle, tout ranger en dormant passerait ce fichier au vert."""
    texte = _CAT.read_text(encoding="utf-8")
    avant = texte[:texte.index(_SEP)]
    vivantes = [m.group(1) for b in re.split(r"(?m)^(?=## )", avant)[1:]
                for m in [_HEAD.match(b.split("\n", 1)[0])] if m]
    assert len(vivantes) >= 50, (
        f"seulement {len(vivantes)} classe(s) avant le séparateur. Soit le critère "
        "s'est élargi au point de tout endormir, soit la lecture est cassée — dans les "
        "deux cas le classement ne dit plus rien.")


# ── Le rangement est FAIT par l'outil, et vérifié dans les deux sens (2026-09-25) ──
#
# Jusqu'ici ce fichier était le SEUL endroit où vivait le critère : aucun producteur ne
# le lisait, et chaque classe réveillée a été remontée À LA MAIN après que ce test a
# rougi (DEVLOG 2026-09-20, f30d724, 1be1c8b). Le sens inverse — une classe qui
# s'ENDORT au-dessus du séparateur — n'était vérifié par rien : mesuré ce jour-là,
# **31 classes** y remplissaient le critère, et l'en-tête annonçait 206 / 196 pour
# 203 / 211 réels. Désormais `tools/dev/error_class_health.py::rank_catalogue` range, et
# `make error-health-check` échoue sur un catalogue non rangé.
#
# ⚠️ `_dormante` ci-dessus reste l'oracle, RECOPIÉ et non importé de l'outil : un
# prédicat importé resterait vert sous une mutation de celui qu'il garde.

_GEN = ROOT / "tools" / "dev" / "error_class_health.py"
_GARDE = "tests/test_the_dormant_classes_are_ranked_not_lost.py"


def _outil():
    spec = importlib.util.spec_from_file_location("error_class_health_rank", _GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ids(texte: str) -> list[str]:
    return [m.group(1) for b in re.split(r"(?m)^(?=## )", texte)[1:]
            for m in [_HEAD.match(b.split("\n", 1)[0])] if m]


def _rec(**kw) -> dict:
    base = {"history_additions": 0, "siblings_sites": 0, "status": "guarded",
            "guard_automatic": True, "guard_ref": _GARDE}
    base.update(kw)
    return base


def _bloc(cid: str) -> str:
    return f"## {cid}\n- status: guarded\n- History:\n  - 2026-09-01: {cid} est née\n\n"


_AVANT = ("vivante-a", "endormie-b", "vivante-c")
_APRES = ("reveillee-d", "dormante-e", "jamais-notee-f")
_RECS = {
    "vivante-a": _rec(status="open"),
    "endormie-b": _rec(),                        # remplit tout, AU-DESSUS : doit descendre
    "vivante-c": _rec(siblings_sites=None),      # balayage muet : vivante
    "reveillee-d": _rec(history_additions=1),    # a récidivé, EN DESSOUS : doit remonter
    "dormante-e": _rec(),
    # `jamais-notee-f` n'a AUCUN enregistrement : écrite dans la séance, pas encore notée.
}


def _catalogue_jouet() -> str:
    return ("# Catalogue\n\n## Contract\nprose d'en-tête\n\n"
            + "".join(_bloc(c) for c in _AVANT)
            + "## 💤 Classes DORMANTES — gardées, jamais récidivées, balayage à zéro site\n\n"
            + "> Les 206 classes qui suivent — un nombre périmé.\n\n"
            + "".join(_bloc(c) for c in _APRES))


def _attendu_par_l_oracle(ordre: list[str]) -> tuple[list[str], list[str]]:
    dort = [c for c in ordre if c in _RECS and _dormante(_RECS[c])]
    return [c for c in ordre if c not in dort], dort


def test_the_tool_ranks_both_directions_as_the_oracle_says() -> None:
    """(a) Une classe réveillée remonte, une classe endormie descend — et rien ne se perd."""
    texte = _catalogue_jouet()
    range_ = _outil().rank_catalogue(texte, _RECS)
    vivantes, dormantes = _attendu_par_l_oracle(list(_AVANT + _APRES))
    sep = range_.index(_SEP)
    assert _ids(range_[:sep]) == vivantes and _ids(range_[sep:]) == dormantes, (
        f"rangement de l'outil : {_ids(range_[:sep])} | {_ids(range_[sep:])} ; l'oracle "
        f"de ce test attend {vivantes} | {dormantes}. Une classe réveillée doit remonter "
        "EN FIN de moitié vivante, une classe endormie descendre, chaque moitié gardant "
        "son ordre.")
    for c in _AVANT + _APRES:
        # La fin du fichier est normalisée à UN saut de ligne (end-of-file-fixer).
        assert range_.count(_bloc(c).rstrip("\n") + "\n") == 1, (
            f"le bloc `{c}` n'a pas été déplacé octet pour octet")
    assert "jamais-notee-f" in _ids(range_[:sep]), (
        "une classe SANS enregistrement de santé a été rangée parmi les dormantes : une "
        "classe neuve, jamais auditée, disparaîtrait sous le séparateur à sa première "
        "régénération.")
    assert "Les 2 classes qui suivent" in range_ and "les 4 classes encore vivantes" in range_, (
        "l'en-tête régénéré ne porte pas les nombres mesurés (2 dormantes, 4 vivantes)")


def test_the_ranking_is_a_fixed_point() -> None:
    """(b) Une seconde passe ne déplace rien — sinon chaque régénération réécrit le fichier."""
    outil = _outil()
    une = outil.rank_catalogue(_catalogue_jouet(), _RECS)
    assert outil.rank_catalogue(une, _RECS) == une
    reel = _CAT.read_text(encoding="utf-8")
    sante = json.loads(_SANTE.read_text(encoding="utf-8"))["classes"]
    assert outil.rank_catalogue(reel, sante) == reel, (
        "le catalogue versionné n'est pas rangé selon l'instantané versionné. "
        "Remède : make error-health.")


def test_main_writes_the_ranking_and_a_second_run_changes_nothing(tmp_path, monkeypatch) -> None:
    """(b) Le chemin d'ÉCRITURE : `main()` range le catalogue, deux passes sont identiques."""
    outil = _outil()
    cat, data, doc = tmp_path / "cat.md", tmp_path / "h.json", tmp_path / "h.md"
    cat.write_text(_catalogue_jouet(), encoding="utf-8")
    js = json.dumps({"classes": _RECS})
    monkeypatch.setattr(outil, "CATALOGUE", cat)
    monkeypatch.setattr(outil, "DATA", data)
    monkeypatch.setattr(outil, "DOC", doc)
    monkeypatch.setattr(outil, "ROOT", tmp_path)   # affichage seul ; is_dormant lit le vrai
    monkeypatch.setattr(outil, "build", lambda: (js, "doc\n"))
    monkeypatch.setattr(outil, "_catalogue_differs_from_head", lambda: False)
    monkeypatch.setattr(outil.sys, "argv", ["error_class_health.py"])
    assert outil.main() == 0
    premiere = cat.read_bytes()
    assert premiere != _catalogue_jouet().encode(), "main() n'a pas écrit le rangement"
    assert outil.main() == 0
    assert cat.read_bytes() == premiere, "deux passes de main() ne rendent pas les mêmes octets"
    monkeypatch.setattr(outil.sys, "argv", ["error_class_health.py", "--check"])
    assert outil.main() == 0
    cat.write_text(_catalogue_jouet(), encoding="utf-8")
    assert outil.main() == 1, "--check reste vert sur un catalogue NON rangé"


def test_the_header_counts_are_the_measured_counts() -> None:
    """(c) L'en-tête dit COMBIEN — et le nombre est le bon, pas seulement un nombre."""
    texte = _CAT.read_text(encoding="utf-8")
    i = texte.index(_SEP)
    entete = texte[i:i + 2500]
    dit_dormantes = re.search(r"Les (\d+) classes qui suivent", entete)
    dit_vivantes = re.search(r"les (\d+) classes encore vivantes", entete)
    assert dit_dormantes and dit_vivantes, "l'en-tête ne porte plus ses deux nombres"
    mesure = (len(_ids(texte[:i])), len(_ids(texte[i:])))
    assert (int(dit_vivantes.group(1)), int(dit_dormantes.group(1))) == mesure, (
        f"l'en-tête dit {dit_vivantes.group(1)} vivantes / {dit_dormantes.group(1)} "
        f"dormantes, le catalogue en porte {mesure[0]} / {mesure[1]}. Il annonçait 196 / "
        "206 pour 211 / 203 le 2026-09-25 — un nombre écrit à la main se périme.")


def test_no_class_above_the_separator_meets_the_criterion() -> None:
    """(d) Le sens qui manquait : une classe qui s'ENDORT doit descendre."""
    texte = _CAT.read_text(encoding="utf-8")
    sante = json.loads(_SANTE.read_text(encoding="utf-8"))["classes"]
    endormies = [c for c in _ids(texte[:texte.index(_SEP)])
                 if c in sante and _dormante(sante[c])]
    assert not endormies, (
        f"{len(endormies)} classe(s) au-dessus du séparateur remplissent le critère du "
        f"sommeil : {endormies[:5]}. 31 le 2026-09-25, invisibles parce que seul le sens "
        "« réveil » était vérifié. Remède : make error-health.")
