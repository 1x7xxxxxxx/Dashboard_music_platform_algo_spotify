"""La frontière du registre tient même si `error_alert` arrive EN COURS de test.

Type: Test
Uses: pytest, importlib, sys.meta_path
Depends on: tests/conftest.py (`_no_registry_writes`, `_SilenceOnImport`)
Persists in: nothing

Ce qui a été mesuré (2026-09-15)
--------------------------------
`_no_registry_writes` importait `src.dashboard.utils.error_alert` de façon
INCONDITIONNELLE, à chaque test. Cet import exécute
`src/dashboard/utils/__init__.py`, qui coûte **5,35 s** (dont 5,19 s de
`streamlit`). Résultat : `conftest.py` facturait **10,5 s à chaque processus
pytest** — 14,85 s pour UN test trivial dans `tests/`, contre 4,39 s pour le même
test hors de `tests/`. Sous `-n 8`, huit workers paient cette facture.

Le raccourci évident est FAUX, et c'est ce que ce fichier garde
--------------------------------------------------------------
« Si le module n'est pas dans `sys.modules`, ne rien faire » paraît suffisant. Ça
ne l'est pas : **286 tests rendent une page Streamlit**, et un rendu peut importer
la chaîne pendant que le test tourne. Ce test-là se retrouverait alors avec un
`error_alert` importé et NON borné, libre d'écrire dans `app_error_log` — une
écriture réelle dans la base, pendant la suite, exactement ce que la fixture
existe pour empêcher.

La fixture enveloppe donc le **loader** et pas seulement le finder : `exec_module`
rend la main après avoir exécuté le module, et la rustine est posée là, avant que
l'`import` de l'appelant ne retourne. La fenêtre sans frontière est vide par
construction — et c'est cette affirmation-là qui est vérifiée ici, sur un import
réellement déclenché, pas sur une lecture du code.
"""
from __future__ import annotations

import importlib
import sys

import pytest

_MOD = "src.dashboard.utils.error_alert"

_WRITE_DOORS = ("_record", "_mark_emailed")


def _is_silenced(module) -> bool:
    """Les deux portes d'écriture ont-elles été remplacées par des no-op ?"""
    for door in _WRITE_DOORS:
        fn = getattr(module, door, None)
        if fn is None:
            return False
        # La rustine est un lambda défini dans conftest ; l'original est une
        # fonction nommée du module. On compare le NOM, pas l'identité : un
        # `lambda` porte `<lambda>`.
        if getattr(fn, "__name__", "") != "<lambda>":
            return False
    return True


def test_a_module_imported_during_the_test_is_already_silenced():
    """Le cas qui a motivé le crochet : l'import arrive au milieu du test."""
    if _MOD in sys.modules:
        pytest.skip(
            "`error_alert` est déjà importé dans ce processus — c'est le premier "
            "régime de la fixture, couvert par "
            "`test_an_already_imported_module_is_silenced_too`. Le régime tardif "
            "ne peut être exercé que dans un processus qui ne l'a pas encore vu."
        )

    module = importlib.import_module(_MOD)

    assert _is_silenced(module), (
        f"`{_MOD}` vient d'être importé PENDANT un test et ses portes d'écriture "
        f"{_WRITE_DOORS} ne sont pas bornées. Tout ce qui suit dans ce test peut "
        "écrire dans `app_error_log`. Le crochet `_SilenceOnImport` de "
        "`tests/conftest.py` doit poser la rustine depuis `exec_module`, pas "
        "depuis le démontage de la fixture — au démontage, il est trop tard."
    )


def test_an_already_imported_module_is_silenced_too():
    """L'autre régime : le module était là avant le test."""
    module = importlib.import_module(_MOD)      # no-op si déjà importé

    assert _is_silenced(module), (
        f"`{_MOD}` était importé avant ce test et n'est pas borné : la branche "
        "« déjà dans sys.modules » de `_no_registry_writes` ne pose plus la rustine."
    )


def test_the_predicate_can_tell_a_silenced_module_from_a_live_one():
    """Non-vacuité : un prédicat toujours vrai laisserait les deux tests passer à vide.

    Sans cette assertion, `_is_silenced` pourrait rendre `True` sur n'importe quoi
    et les deux gardes ci-dessus deviendraient décoratifs.
    """
    class _Live:
        def _record(self, *a, **k):
            """La vraie porte, une fonction nommée."""

        def _mark_emailed(self, *a, **k):
            """L'autre."""

    class _Silenced:
        _record = staticmethod(lambda *a, **k: None)
        _mark_emailed = staticmethod(lambda *a, **k: None)

    class _HalfSilenced:
        _record = staticmethod(lambda *a, **k: None)

        def _mark_emailed(self, *a, **k):
            """Celle-ci est restée vivante."""

    assert _is_silenced(_Silenced()), "un module borné doit être reconnu comme tel"
    assert not _is_silenced(_Live()), "un module VIVANT est pris pour un module borné"
    assert not _is_silenced(_HalfSilenced()), (
        "une seule porte bornée suffit à tromper le prédicat : l'autre reste "
        "capable d'écrire."
    )
