"""Une méthode qui REMPLIT un mémo doit le CONSULTER, sinon ce n'est pas un mémo.

Type: Utility
Uses: ast
Triggers: pytest
Persists in: nothing

Error class `a-memo-field-written-and-never-consulted`.

Mesuré le 2026-09-17. `ConfigLoader.load()` écrivait `self._config` à chaque appel et
**ne le relisait jamais** : elle rouvrait et reparsait `config/config.yaml` à chaque
fois. Trois `get_*_config()` consultaient le champ ; celle qui le remplit, non.

Le coût, mesuré : **4,92 ms par appel** (médiane de 30) pour **2 424 octets** de YAML.
Le fichier est minuscule — le coût est l'ouverture, parce que ce dépôt vit sur `/mnt/c`,
monté par `drvfs`, où chaque `open()` est un message 9P à travers la frontière VM/hôte.

Sur l'accueil, profils alternés, séries DISJOINTES :

    avec mémo   64 · 66 · 69 ms        sans mémo   82 · 88 · 94 ms

**−25 % du `show()` de l'accueil**, pour relire un fichier qui n'a pas changé.

Un champ de mémoïsation écrit et jamais consulté se LIT comme un cache. C'est la même
famille que `a-cache-key-that-can-never-be-hit-twice` : *« un cache sans succès se
comporte exactement comme pas de cache »*, et aucun des deux ne laisse de trace.

## La question que ce garde pose

Pour chaque classe : existe-t-il un attribut `self._x` que **d'autres** méthodes lisent,
et qu'une méthode ÉCRIT sans jamais le lire ? Cette asymétrie est la signature — le
champ sert de mémo à tout le monde sauf à celui qui le remplit.

## Ce qu'il ne couvre pas

Un mémo que personne ne lit du tout (c'est du code mort, une autre classe) ; un mémo
volontairement ré-écrit à chaque appel pour rafraîchir (il n'y en a pas ici, et le cas
échéant la méthode porterait `force=`) ; les mémos hors des classes — une variable de
module, un `functools.lru_cache` mal posé, un `st.cache_data` sur une clé volatile.

Mutation record — 2026-09-17, vue rouge : le `if self._config is not None and not
force:` retiré de `ConfigLoader.load()` → ce garde la nomme en `fichier:méthode` ;
remis, vert.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SCANNED = ("src",)


def _short_circuits_on(fn: ast.AST, attr: str) -> bool:
    """La méthode sort-elle TÔT quand le mémo est déjà rempli ?

    ⚠️ C'est la troisième formulation, et les deux premières ne voyaient pas le défaut
    pour lequel ce fichier existe.

    La première demandait « le remplisseur lit-il le mémo ? ». `ConfigLoader.load()`
    finissait par `return self._config` — donc il le LIT, et le défaut passait. **Un
    garde qui ne rougit pas sur son propre cas ne garde rien**, et il aurait fallu le
    découvrir en production.

    La seconde, plus large, dénonçait cinq sites SAINS : `_get_access_token` d'un
    collecteur ÉCRIT le jeton et `_ensure_token` le LIT pour décider d'appeler — c'est
    la bonne division du travail, un rafraîchisseur n'est pas un accesseur.

    La signature exacte est ailleurs : un accesseur qui recalcule INCONDITIONNELLEMENT.
    Il écrit le mémo, le rend, et **ne teste jamais s'il est déjà rempli avant de
    refaire le travail**. Un `if self._x …: return …` en tête est la seule chose qui
    distingue un cache d'une relecture déguisée en cache.
    """
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        if not _reads(node.test, attr):
            continue
        if any(isinstance(n, ast.Return) for n in ast.walk(node)):
            return True
    return False


def _reads(node: ast.AST, attr: str) -> bool:
    return any(
        isinstance(n, ast.Attribute) and n.attr == attr
        and isinstance(n.ctx, ast.Load)
        and isinstance(n.value, ast.Name) and n.value.id == "self"
        for n in ast.walk(node))


def _writes(node: ast.AST, attr: str) -> bool:
    return any(
        isinstance(n, ast.Attribute) and n.attr == attr
        and isinstance(n.ctx, ast.Store)
        and isinstance(n.value, ast.Name) and n.value.id == "self"
        for n in ast.walk(node))


def _returns(fn: ast.AST, attr: str) -> bool:
    """La méthode REND le mémo — c'est ce qui en fait un accesseur, pas un setter."""
    return any(
        isinstance(n, ast.Return) and n.value is not None and _reads(n.value, attr)
        for n in ast.walk(fn))


def _offenders() -> list[str]:
    bad = []
    for root in _SCANNED:
        for path in sorted((REPO / root).rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, OSError):
                continue
            for cls in ast.walk(tree):
                if not isinstance(cls, ast.ClassDef):
                    continue
                for fn in cls.body:
                    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if fn.name == "__init__":
                        continue
                    for attr in {n.attr for n in ast.walk(fn)
                                 if isinstance(n, ast.Attribute)
                                 and isinstance(n.ctx, ast.Store)
                                 and n.attr.startswith("_")
                                 and isinstance(n.value, ast.Name)
                                 and n.value.id == "self"}:
                        if not (_writes(fn, attr) and _returns(fn, attr)):
                            continue
                        if _short_circuits_on(fn, attr):
                            continue
                        bad.append(
                            f"{path.relative_to(REPO)}::{cls.name}.{fn.name} "
                            f"rend `self.{attr}` en le recalculant a chaque appel")
    return bad


def test_the_predicate_sees_the_defect_it_was_written_for() -> None:
    """Non-vacuite, sur la forme EXACTE d'avant le correctif du 2026-09-17.

    ⚠️ Ce test existe parce que les deux premieres formulations du predicat rendaient
    ce cas VERT. Le reproduire ici littéralement est la seule facon de garantir que la
    troisieme ne redevienne pas aveugle.
    """
    before = ast.parse(
        "class C:\n"
        "    def load(self):\n"
        "        if not self.p.exists():\n"
        "            self._config = {}\n"
        "            return self._config\n"
        "        with open(self.p) as f:\n"
        "            self._config = yaml.safe_load(f) or {}\n"
        "        return self._config\n")
    fn = before.body[0].body[0]
    assert _writes(fn, "_config") and _returns(fn, "_config")
    assert not _short_circuits_on(fn, "_config"), (
        "le predicat ne voit pas la forme d'avant le correctif — il est redevenu "
        "aveugle sur son propre cas")

    after = ast.parse(
        "class C:\n"
        "    def load(self, force=False):\n"
        "        if self._config is not None and not force:\n"
        "            return self._config\n"
        "        self._config = read()\n"
        "        return self._config\n")
    assert _short_circuits_on(after.body[0].body[0], "_config")


def test_a_refresher_is_not_an_accessor() -> None:
    """La forme SAINE que la deuxieme formulation denonçait a tort.

    `_get_access_token` ECRIT le jeton, `_ensure_token` le LIT pour decider d'appeler :
    c'est la bonne division du travail. Cinq sites de `src/collectors/` avaient ete
    denonces ainsi.
    """
    healthy = ast.parse(
        "class C:\n"
        "    def _refresh(self):\n"
        "        self._token = fetch()\n"
        "        self._expires = soon()\n"
        "    def _ensure(self):\n"
        "        if self._token is None: self._refresh()\n"
        "        return self._token\n")
    refresh = healthy.body[0].body[0]
    assert _writes(refresh, "_token")
    assert not _returns(refresh, "_token"), (
        "un rafraichisseur ne REND pas le memo — sinon il serait un accesseur")


def test_no_accessor_recomputes_its_memo_unconditionally() -> None:
    offenders = _offenders()
    assert not offenders, (
        "ces methodes rendent un memo qu'elles recalculent a CHAQUE appel :\n  "
        + "\n  ".join(offenders)
        + "\n\nUn champ de memoisation ecrit et jamais consulte se LIT comme un cache "
          "et n'en est pas un — rien ne le signale. `ConfigLoader.load()` reparsait "
          "ainsi 2 424 octets de YAML a chaque appel, 4,92 ms sur `/mnt/c`, soit 25 % "
          "du `show()` de l'accueil.")
