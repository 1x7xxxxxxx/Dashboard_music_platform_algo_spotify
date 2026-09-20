"""Le saut d'UN niveau de composition SQL — R145.

Type: Utility
Uses: tools/dev/gold_coverage
Triggers: `make test`, `make gold-coverage-check`
Depends on: src/utils/mrr.py, src/dashboard/views/billing.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Mesuré le 2026-09-20. R140 a unifié la définition du MRR, qui était calculée à TROIS
endroits avec DEUX réponses sous le même libellé. La correction est juste — et elle a
fait tomber les figures à source établie de **93 à 85 sur 204**, parce que le SQL a
cessé d'être un littéral au site d'appel.

Le remède ne pouvait pas être de défaire la centralisation. C'est l'analyseur qui devait
apprendre à suivre un appel dont le corps rend un littéral.

Ce que ce garde empêche, c'est la RÉGRESSION SILENCIEUSE : si le saut redevient vacant,
la carte se remet à dire « je ne sais pas » sur des tables parfaitement lisibles, et le
seul symptôme est un compteur qui monte dans un document que personne ne relit ligne à
ligne.

⚠️ Vu ROUGE sur la mutation qui incarne le défaut : `_sql_through_call` rendant `None`
d'entrée fait retomber la carte à 85 / 204 et `sql-dynamique` à 25. Restauré : 93 et 17.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))

import gold_coverage as gc  # noqa: E402


def test_the_hop_exists_and_is_wired_into_every_sql_read() -> None:
    """Le saut existe ET les quatre lecteurs lui passent leur module.

    Un saut présent que personne n'alimente est exactement le motif
    `correct-code-nothing-reaches` : il est là, il est juste, il ne s'exécute jamais.
    """
    src = (ROOT / "tools" / "dev" / "gold_coverage.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    methodes = {n.name for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)}
    assert "_sql_through_call" in methodes, "le saut d'un niveau a disparu"

    appels = [n for n in ast.walk(arbre)
              if isinstance(n, ast.Call)
              and getattr(n.func, "attr", "") == "_read_sql"]
    assert len(appels) >= 4, f"{len(appels)} lecteurs SQL trouvés, 4 attendus"
    sans_module = [a for a in appels if len(a.args) < 5]
    assert not sans_module, (
        f"{len(sans_module)} appel(s) à `_read_sql` ne passent pas leur module `here`. "
        "Sans lui le saut ne peut pas résoudre l'appel, et ces surfaces retombent en "
        "`sql-dynamique` sans que rien ne le dise.")


def test_the_hop_resolves_the_helper_that_made_it_necessary() -> None:
    """NON-VACUITÉ, sur le cas RÉEL : `mrr_by_plan_sql()` doit rendre ses trois tables.

    Ancré sur le helper qui a causé la perte, pas sur un exemple fabriqué : c'est lui
    qui doit rester lisible, et un exemple synthétique resterait vert le jour où la
    signature du vrai helper change.
    """
    helper = ROOT / "src" / "utils" / "mrr.py"
    arbre = ast.parse(helper.read_text(encoding="utf-8"))
    fns = {n.name: n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)}
    assert "mrr_by_plan_sql" in fns, (
        "`mrr_by_plan_sql` a disparu de `src/utils/mrr.py` — ce garde vise un helper "
        "qui n'existe plus, donc il ne garde plus rien. Le recaler sur le helper réel.")

    rendus = [n.value for n in ast.walk(fns["mrr_by_plan_sql"])
              if isinstance(n, ast.Return) and n.value is not None]
    assert rendus, "`mrr_by_plan_sql` ne rend plus rien"

    litteral = "".join(
        v.value for r in rendus if isinstance(r, ast.JoinedStr)
        for v in r.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    for table in ("artist_subscriptions", "subscription_plans", "saas_artists"):
        assert table in litteral, (
            f"`{table}` n'est plus un littéral dans le corps de `mrr_by_plan_sql`. "
            "Le saut d'un niveau ne la retrouvera pas, et la figure du MRR redeviendra "
            "indéterminée sur la carte.")


@pytest.mark.parametrize("motif", ["sql-dynamique", "portent une source établie"])
def test_the_generated_map_still_publishes_what_the_ratchet_reads(motif: str) -> None:
    """Le cliquet lit le DOCUMENT : si la phrase disparaît, il devient vert sur rien."""
    doc = (ROOT / ".claude" / "dev-docs" / "gold-coverage.md").read_text(encoding="utf-8")
    assert motif in doc, (
        f"« {motif} » a disparu de la carte générée. Le cliquet "
        "`test_no_counter_of_holes_ever_grows` lit ce document : sans cette phrase il "
        "ne mesure plus rien et reste vert quoi qu'il arrive.")
