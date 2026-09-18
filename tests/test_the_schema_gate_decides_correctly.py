"""La porte de dérive de schéma décide, et personne ne vérifiait sa décision.

Type: Test
Uses: pytest, importlib
Depends on: tools/dev/schema_drift_check.py
Persists in: nothing

`make schema-check` et `make schema-check-local` reposent entièrement sur ce script :
il compare un dump de la base VIVANTE au schéma canonique (`init_db.sql` +
`migrations/*.sql`) et sort **1** s'il trouve une dérive, **0** sinon. Un runbook lit ce
vert avant de déployer.

Balayé le 2026-09-18 : **8 outils du dépôt sortent en code non nul pour dire non**, et
**deux n'étaient nommés par aucun test** — celui-ci et
`.claude/scripts/audit_collectors_ast.py`, qui est pourtant une étape BLOQUANTE de la
CI. C'est la classe `gate-with-no-test-of-its-own` : la logique qui décide n'est
vérifiée par personne, et son vert est cru.

Ce que ce fichier fixe
----------------------
Les quatre décisions que la porte peut prendre, et la seule qui doit rendre 0. Plus
deux propriétés que sa prose promet et qu'aucun test ne tenait :

  · une colonne en trop D'UN CÔTÉ OU DE L'AUTRE est une dérive (les deux sens comptent :
    une colonne présente en canonique et absente en prod signale une migration non
    appliquée, ce qui est au moins aussi grave) ;
  · une divergence de CONTRAINTE ou d'index unique compte aussi — c'est ce qui décide
    quelles lignes peuvent coexister et quels `ON CONFLICT` résolvent ;
  · le LABEL du côté comparé est repris dans la sortie. Il valait « prod » par défaut
    et était imprimé tel quel quand `schema-check-local` comparait la base LOCALE : un
    rapport qui se trompe de sujet est la façon dont un vert se fait mal lire.

Ce qu'il ne couvre PAS
----------------------
`_used_in_src()`, qui lance un `grep` sur `src/` pour étiqueter une colonne `USED` ou
`orphan?` : c'est une aide au TRI, elle n'entre pas dans le code de sortie. Et la
production des dumps eux-mêmes, qui vit dans le Makefile et demande Docker et SSH.

Mutation record — 2026-09-18 : en remplaçant la condition de sortie
`if prod_extra or canon_extra or key_drift:` par `if prod_extra:`, les cas « colonne
manquante côté vivant » et « contrainte divergente » passent au vert et ce fichier les
nomme ; rétablie, il passe.

---
rex: []
---
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_GATE = _ROOT / "tools" / "dev" / "schema_drift_check.py"


def _module():
    spec = importlib.util.spec_from_file_location("_schema_gate", _GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dump(tmp_path: Path, nom: str, lignes: list[str]) -> str:
    p = tmp_path / nom
    p.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return str(p)


def _run(monkeypatch, tmp_path, vivant: list[str], canon: list[str],
         label: str | None = None) -> tuple[int, str]:
    """Lance la porte et rend (code de sortie, sortie imprimée)."""
    mod = _module()
    # `_used_in_src` lance un `grep` sur tout `src/` : c'est une aide au tri, pas une
    # décision. On l'immobilise pour que le test mesure la PORTE, pas le dépôt.
    monkeypatch.setattr(mod, "_used_in_src", lambda _col: False)
    argv = ["schema_drift_check.py", _dump(tmp_path, "live.tsv", vivant),
            _dump(tmp_path, "canon.tsv", canon)]
    if label:
        argv.append(label)
    monkeypatch.setattr(mod.sys, "argv", argv)
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), pytest.raises(SystemExit) as exc:
        mod.main()
    return int(exc.value.code or 0), buf.getvalue()


def test_the_gate_exists_and_is_wired() -> None:
    """Anti-vacuité : sans la porte, tout le reste est vert sur rien."""
    assert _GATE.is_file(), "`tools/dev/schema_drift_check.py` a disparu."
    mk = (_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "schema_drift_check.py" in mk, (
        "la porte n'est plus appelée par le Makefile : soit `make schema-check` a "
        "changé d'outil, soit elle est devenue du code mort — et une porte que rien "
        "n'appelle ne garde rien.")


def test_identical_schemas_pass(monkeypatch, tmp_path) -> None:
    lignes = ["col:artists.id", "col:artists.name", "key:artists_pkey PRIMARY KEY (id)"]
    code, sortie = _run(monkeypatch, tmp_path, lignes, lignes)
    assert code == 0, f"deux schémas identiques doivent passer, sortie :\n{sortie}"


def test_a_column_only_in_the_live_database_is_drift(monkeypatch, tmp_path) -> None:
    code, sortie = _run(monkeypatch, tmp_path,
                        ["col:artists.id", "col:artists.surprise"], ["col:artists.id"])
    assert code == 1, "une colonne présente en base et absente du canonique est une dérive"
    assert "artists.surprise" in sortie


def test_a_column_missing_from_the_live_database_is_drift(monkeypatch, tmp_path) -> None:
    """L'AUTRE sens compte : il signale une migration non appliquée là-bas."""
    code, sortie = _run(monkeypatch, tmp_path,
                        ["col:artists.id"], ["col:artists.id", "col:artists.attendue"])
    assert code == 1, (
        "une colonne du canonique absente de la base vivante est une dérive — c'est "
        "une migration qui n'a pas tourné, et un déploiement qui s'appuie dessus "
        "échouera en production.")
    assert "artists.attendue" in sortie


def test_a_diverging_constraint_is_drift(monkeypatch, tmp_path) -> None:
    """Les colonnes concordent, les CONTRAINTES non — et ça change les `ON CONFLICT`."""
    code, sortie = _run(
        monkeypatch, tmp_path,
        ["col:t.a", "uix:t_a_key UNIQUE (a)"],
        ["col:t.a", "uix:t_a_key UNIQUE (a, b)"])
    assert code == 1, (
        "un index unique divergent décide quelles lignes peuvent coexister et quels "
        "`ON CONFLICT` résolvent : le manquer rend vert une base où un upsert ne fait "
        "pas ce que le code croit.")
    assert "UNIQUE" in sortie.upper()


def test_the_report_names_the_side_it_compared(monkeypatch, tmp_path) -> None:
    """Un rapport qui se trompe de sujet est la façon dont un vert se fait mal lire."""
    _, sortie = _run(monkeypatch, tmp_path, ["col:t.a"], ["col:t.a"], label="local")
    assert "local" in sortie, (
        "le label du côté comparé n'apparaît pas : `schema-check-local` imprimerait "
        "« prod » en comparant la base LOCALE.")
    assert "prod" not in sortie.replace("prod_extra", ""), (
        "le rapport dit encore « prod » alors qu'on lui a passé « local ».")
