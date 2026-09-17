"""L'instantané de santé du catalogue ne peut que s'améliorer — sauf le taux.

Type: Test
Uses: tools/dev/error_class_health, json
Depends on: .claude/dev-docs/error-class-health.{json,md}
Persists in: nothing

Mutation record — 2026-09-16 : huit mutations jouées, **huit vues ROUGES**.
  1. plafond `cause_inferred` relevé de 1       → rouge (plafond au-dessus de la mesure)
  2. classe synthétique sans les trois champs   → rouge (`seen_red_unknown` grandit)
  3. `cause_evidence: inferred` sur une classe  → rouge (2 tests : trou + plafond lâche)
  4. plancher d'exposition porté à 999 999      → rouge (fenêtre rétrécie)
  5. SUPPRESSION d'une classe du catalogue      → rouge (plancher de population)
  6. parseur rendant 0 classe                   → rouge (5 tests — jamais vert-sur-vide)
  7. ids divergents entre les deux lecteurs     → rouge (4 tests)
  8. document édité à la main sans régénérer    → rouge (fraîcheur, nomme le remède)
  9. deux fins de ligne au lieu d'une           → rouge AU COMMIT SUIVANT (voir ci-dessous)

  ⚠️ Deux de ces mutations ont d'abord été écrites FAUSSES et rendaient le garde vert :
  la n° 3 insérait le champ dans le bloc `## Per-class schema` — un gabarit, pas une
  classe — et une première tentative renommait une variable des deux côtés, donc ne
  désactivait rien. **Une mutation qu'on n'inspecte pas ment dans le même sens que le
  garde**, et les deux fois j'ai failli conclure « il ne mord pas ».

  ⚠️ Et le premier commit a été REFUSÉ par pre-commit, pour deux raisons que seul le
  commit pouvait révéler : `end-of-file-fixer` retirait la ligne vide finale du document,
  donc le disque cessait d'égaler `build()` **dès le commit** ; et `detect-secrets` voyait
  les SHA de commit stockés dans le JSON comme 89 secrets à haute entropie. Le SHA est
  sorti du document — le marquer en faux positif ferait enfler `.secrets.baseline` à
  chaque régénération, et un fichier qui change tous les jours n'a rien à faire dans une
  liste d'exceptions. **Un générateur doit produire exactement ce que les crochets
  laissent passer**, sinon son cliquet est rouge sans que rien n'ait bougé.

Ce qui est cranté, et ce qui ne l'est surtout PAS
--------------------------------------------------
**Le taux de récidive n'est pas cranté**, et c'est la décision centrale de ce fichier.
Mesuré le 2026-09-16, normalisé par le temps d'exposition, il **monte** : la cohorte de
septembre porte 0,35 évènement par classe-mois contre 0,11 pour celle de mai. Un cliquet
« le taux ne peut que baisser » serait donc rouge le jour où on l'écrit — et ce dépôt a
la classe `a-gate-that-can-never-be-green` pour ça.

Ce qui se crante, c'est la **MÉTHODE** : la part de classes dont la connaissance est
invérifiable. Elle ne baisse que par du travail. Et des **planchers de population**
empêchent de la faire baisser en supprimant des classes — un taux s'améliore aussi bien
en corrigeant qu'en effaçant, et seul le plancher distingue les deux.

Le résultat qui a justifié tout ça
------------------------------------
Première mesure séparant les strates, 2026-09-16 : une classe **sans garde automatique
récidive 5,2× plus** (1,005 évènement par classe-mois contre 0,193), et **les intervalles
à 95 % ne se recouvrent pas** (0,433–1,980 contre 0,142–0,257). Deux estimations
précédentes — « 15 % contre 23 % », puis « pas robuste » — étaient fausses pour la même
raison : elles comptaient des CLASSES, pas des évènements par temps d'exposition.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_DATA = _ROOT / ".claude" / "dev-docs" / "error-class-health.json"
_DOC = _ROOT / ".claude" / "dev-docs" / "error-class-health.md"

# ── Gelé à la MESURE du 2026-09-16, jamais à une estimation ──────────────────
# Ces plafonds ne peuvent que BAISSER. Les faire baisser demande soit de renseigner un
# champ sur une classe, soit de retirer une classe devenue fausse — les deux sont des
# progrès. Les planchers plus bas interdisent la seconde de devenir un raccourci.
_CEILINGS = {
    # Resserrés le 2026-09-16 dans le commit de la passe mécanique, comme
    # `test_the_ceiling_is_not_slack` l'exige : un plafond laissé au-dessus de la mesure
    # est du budget pour régresser en silence.
    "seen_red_unknown": 331,          # 363 → 352 (n-a) → 332 (phase B : traces de mutation)
    "seen_red_never": 0,
    "cause_unknown": 241,             # 363 → 241 : les causes qui nomment un chemin vérifiable
    "cause_inferred": 0,
    "scope_unknown": 0,               # 363 → 0 : la famille est dérivable pour toutes
    "scope_without_not_covered": 304,
    # ⚠️ Compteur NEUF le 2026-09-17, gele a sa premiere mesure. Une classe dont le
    # fichier de garde est PARTAGE avec une autre doit nommer SES tests — sinon sa
    # portee se lit comme « je possede tout ce fichier ». 50 fichiers sur 286 sont
    # partages, et le defaut s'est produit DEUX fois en deux lots avant d'etre
    # mesure : une classe s'etait attribue le croisement Caddy de sa voisine, une
    # autre le taux de censure d'une troisieme.
    "scope_on_a_shared_guard_without_naming_its_tests": 20,  # phase C ; -1 le 2026-09-17 : `two-doors-onto-one-database`
                                      # est la PREMIERE classe dont les trois preuves sont
                                      # observées le même jour — date vue rouge, cause mesurée,
                                      # portée écrite en lisant le garde. Les trois compteurs
                                      # baissent ensemble, ce qui est le signe recherché.
    # Liste de RELECTURE, pas une faute à corriger dans une direction imposée : un
    # désaccord peut venir du garde comme de l'expression de la famille.
    # `scope_family_disagreements` RETIRÉ le 2026-09-16 : 10 désaccords sur 18 portées,
    # presque tous du côté de la dérivation (une regex de mots-clés sur un symptôme).
    # 55 % de faux positifs — un compteur bruyant fait ignorer les vrais. Remplacé par
    # une vérification sans faux positif : la famille déclarée EXISTE-t-elle ?
    "scope_family_invalid": 0,
    "guards_ref_missing": 0,
}
_FLOORS = {
    # Relevés le 2026-09-16 : deux classes écrites AVEC la nouvelle méthode. Un plancher
    # monte quand la population grandit — c'est son sens.
    # +1 au lot 5 : `a-guard-names-a-class-nobody-wrote`, **la première classe du
    # catalogue dont `seen_red` porte une DATE OBSERVÉE** et non un rétro-portage.
    # +1 encore : `a-runbook-that-names-a-command-nobody-can-run`, écrite parce que le
    # garde précédent l'a EXIGÉE — sa docstring annonçait l'identifiant avant qu'il
    # existe. Première fois que la chaîne se referme sans qu'on y pense.
    # +1 encore : `a-shared-database-read-while-another-test-writes-it`, écrite sur
    # DEUX rouges de suite complète le même soir, chacun vert en isolation.
    # +1 : `a-fallback-that-runs-when-the-first-branch-succeeded`, écrite sur MON
    # erreur du soir — un `|| git commit` dont la première branche a réussi, avec le
    # message d'un vieux commit. Livrée `guarded` et non `reported` parce qu'une classe
    # sans garde fait monter DEUX plafonds (`prose_only`, `seen_red_unknown`) : les
    # relever pour sa propre erreur serait la leçon inverse. Elle a une surface réelle,
    # les fichiers versionnés, et son garde y a trouvé un faux positif dès la première
    # exécution.
    # +1 : `a-memo-field-written-and-never-consulted`, trouvee en cherchant AUTRE chose —
    # R121 annoncait `platform_chart` comme meilleur candidat ; le profil dit 1,4 ms
    # pour lui et 12,5 ms pour `config_loader.load()`.
    # +1 : `a-renderer-that-recomputes-what-its-caller-already-has`, DEUX instances
    # dans deux fichiers sans rapport le meme jour — `onboarding_health` (324 → 181
    # requetes) et `db_health` (22 → 11 `fetch_df`).
    # +5 le 2026-09-17 : les cinq classes qu'un garde nommait sans qu'elles existent,
    # ecrites depuis la docstring de leur garde. Les CINQ arrivent avec un `seen_red`
    # DATE — chacune vue rouge par mutation, dont deux avec la valeur fautive d'origine
    # (`_COLUMN_WIDTH_PX = 720`, `noise_tokens` retire de l'appel de production).
    # `seen_red_unknown` ne bouge donc pas : +5 classes, +5 dates observees.
    # +1 : `a-parser-that-knows-one-of-two-syntaxes`.
    # ⚠️ `automatic_guard` fait un BOND de 358 a 367, et ce n'est pas du travail : c'est
    # la correction du parseur. Il ne lisait qu'une des deux syntaxes de `guard:`, donc
    # neuf classes gardees etaient comptees comme non gardees depuis toujours. Le
    # plancher monte parce que la MESURE a change, pas le depot.
    "classes": 378,
    "with_signature": 367,
    "automatic_guard": 368,
}
# Le plancher qui n'a pas d'équivalent dans `gold-coverage`, et le plus important ici :
# un taux s'améliore aussi en RÉTRÉCISSANT la fenêtre d'observation.
_EXPOSURE_FLOOR = 7628


def _fresh() -> tuple[str, str]:
    import tools.dev.error_class_health as h
    return h.build()


def _payload() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def test_the_snapshot_still_describes_the_catalogue() -> None:
    """Les deux artefacts sur le disque sont ceux que le dépôt produit."""
    js, md = _fresh()
    assert _DATA.exists() and _DOC.exists(), "instantané absent — `make error-health`"
    assert _DATA.read_text(encoding="utf-8") == js, (
        "`error-class-health.json` ne décrit plus le catalogue.\n"
        "Remède : make error-health")
    assert _DOC.read_text(encoding="utf-8") == md, (
        "`error-class-health.md` ne décrit plus le catalogue.\n"
        "Remède : make error-health")


def test_no_hole_counter_ever_grows() -> None:
    holes = _payload()["aggregate"]["holes"]
    grown = {k: (holes.get(k, 0), c) for k, c in _CEILINGS.items() if holes.get(k, 0) > c}
    assert not grown, (
        "compteur(s) de trou en hausse (mesure, plafond) : " + repr(grown)
        + "\n\nUn trou est une classe dont la connaissance est INVÉRIFIABLE : signature "
          "jamais vue rouge, cause non établie, portée du garde non nommée. C'est cela "
          "qui est cranté — pas le taux de récidive, qui monte et dont un cliquet serait "
          "rouge à l'écriture.")


def test_the_ceiling_is_not_slack() -> None:
    """Un plafond au-dessus de la mesure est du budget pour régresser en silence.

    C'est la discipline qui fait fonctionner `gold-coverage` : le plafond ÉGALE la
    mesure, et resserrer fait partie du commit qui améliore.
    """
    holes = _payload()["aggregate"]["holes"]
    slack = {k: (holes.get(k, 0), c) for k, c in _CEILINGS.items() if holes.get(k, 0) < c}
    assert not slack, (
        "plafond(s) plus haut que la mesure (mesure, plafond) : " + repr(slack)
        + "\n\nLe baisser DANS LE MÊME COMMIT que l'amélioration, sinon le budget "
          "reste ouvert et la prochaine régression passe sans rougir.")


def test_the_population_did_not_shrink() -> None:
    agg = _payload()["aggregate"]
    pop = agg["population"]
    shrunk = {k: (pop.get(k, 0), f) for k, f in _FLOORS.items() if pop.get(k, 0) < f}
    assert not shrunk, (
        "population en baisse (mesure, plancher) : " + repr(shrunk)
        + "\n\nUn compteur de trous s'améliore aussi en SUPPRIMANT des classes. Le "
          "plancher est ce qui distingue « on a corrigé » de « on a effacé ». Si une "
          "classe devait vraiment disparaître, baisser le plancher DANS LE MÊME COMMIT, "
          "avec la raison.")
    exposed = agg["recurrence"].get("class_days_exposed", 0)
    assert exposed >= _EXPOSURE_FLOOR, (
        f"fenêtre d'observation rétrécie : {exposed} classe-jours contre un plancher de "
        f"{_EXPOSURE_FLOOR}. Un taux d'évènements par classe-mois s'améliore en "
        "raccourcissant la fenêtre aussi sûrement qu'en corrigeant des défauts.")


def test_a_falling_rate_is_not_a_ratchet() -> None:
    """Le NON-test délibéré. Il documente ce qu'on refuse de cranter, et pourquoi.

    Il vérifie seulement que le taux est PUBLIÉ avec son intervalle. Cranter sa baisse
    serait rouge à l'écriture : normalisé par l'exposition, il monte.
    """
    rec = _payload()["aggregate"]["recurrence"]
    obs = rec.get("observed") or {}
    assert obs.get("per_class_month") is not None, (
        "le taux observé n'est plus publié — sans lui, les strates ne se lisent pas")
    assert obs.get("ci95"), (
        "le taux est publié SANS intervalle. Les sous-groupes portent 8 à 47 "
        "évènements : un écart de facteur 5 peut n'être que du bruit, et seul "
        "l'intervalle le dit.")
    for key in ("by_guard", "by_seen_red", "by_scope"):
        assert key in rec, f"la strate `{key}` a disparu — c'est elle qui répond à la question posée"


def test_the_two_readers_of_the_catalogue_agree() -> None:
    """Deux cliquets sur une même population ne doivent pas dériver."""
    sys.path.insert(0, str(_ROOT / ".claude" / "scripts"))
    import audit_runner

    text = (_ROOT / ".claude" / "dev-docs" / "error-classes.md").read_text(encoding="utf-8")
    theirs = {c["id"] for c in audit_runner.parse_all_headers(text)}
    mine = set(_payload()["classes"])
    assert mine == theirs, (
        f"les deux lecteurs du catalogue ne voient pas les mêmes classes : "
        f"{sorted(mine ^ theirs)[:8]}. Deux parseurs d'un même fichier qui divergent, "
        "c'est une grandeur avec deux définitions.")

    from tests.test_a_class_binds_or_it_is_only_prose import _classes, _is_automatic
    prose_other = sum(1 for _, g in _classes() if not _is_automatic(g))
    assert _payload()["aggregate"]["population"]["prose_only"] == prose_other, (
        "le compte de classes « prose seule » diffère entre ce cliquet et "
        "`test_a_class_binds_or_it_is_only_prose.py`.")


def test_the_scan_is_not_vacuous() -> None:
    """Sans ça, un parseur cassé rendrait tous les tests ci-dessus verts à vide."""
    p = _payload()
    assert len(p["classes"]) >= 300, (
        f"{len(p['classes'])} classes lues — la lecture est cassée, et « zéro trou » "
        "sur zéro classe est vrai sans rien dire.")
    agg = p["aggregate"]
    assert agg["recurrence"].get("window_start"), "aucune fenêtre d'observation"
    assert agg["generated_from"]["catalogue_revisions"] >= 100, (
        "moins de 100 révisions rejouées : le rejeu git ne trouve plus l'historique du "
        "catalogue, donc la récidive OBSERVÉE serait nulle par construction.")
    assert agg["population"]["ever_recurred_observed"] >= 1, (
        "aucune récidive observée sur tout l'historique : le détecteur ne détecte plus.")
