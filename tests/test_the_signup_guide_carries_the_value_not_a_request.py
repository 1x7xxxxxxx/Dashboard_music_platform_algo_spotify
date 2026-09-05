"""Le guide reçu à l'inscription porte la valeur, il ne la fait pas demander.

Type: Test
Uses: subprocess (interpréteur NU, sans environnement chargé)
Depends on: src/dashboard/content/credential_guides.py, docs/guides/index.html
Persists in: —

Demandé le 2026-09-05 : « intègre directement le nom de l'app quand quelqu'un
s'inscrit pour faciliter la vie à l'utilisateur ». Mesuré : le PDF **envoyé à la
vérification d'e-mail** disait « demande-nous notre numéro de Business » au lieu de le
porter — un aller-retour par courriel imposé à chaque nouvel artiste, pour une valeur
que nous connaissons.

La cause n'était pas le texte mais **qui l'a construit** : le dashboard tourne sous
`streamlit run`, qui charge l'environnement ; le générateur de guide tourne en
`python -m` depuis le `Makefile` et ne le chargeait pas. `META_BUSINESS_ID` était donc
vide **au moment de la construction du PDF, et là seulement**. Le repli fonctionnait ;
c'est ce qui l'a rendu invisible.

Ce test relance un interpréteur **nu** — c'est la seule façon de reproduire la
condition du générateur depuis une suite qui, elle, a chargé l'env.
"""
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def test_the_constant_resolves_without_a_preloaded_environment():
    """Un interpréteur nu doit obtenir la valeur, pas la chaîne vide."""
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, '.');"
         "from src.dashboard.content.credential_guides import META_BUSINESS_ID;"
         "print(META_BUSINESS_ID)"],
        cwd=_ROOT, capture_output=True, text=True, timeout=120,
        env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home())},  # AUCUNE var Meta
    )
    assert out.returncode == 0, out.stderr[-400:]
    value = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""

    # La condition est ce que le DISQUE porte, pas ce que le sous-processus a rendu.
    # Skipper sur une valeur vide rendrait ce test aveugle à la seule régression qu'il
    # garde : retirer le chargement d'env produit exactement une valeur vide. Vu vert
    # sur cette mutation au premier jet — un skip n'est pas une preuve.
    declared = [f for f in (_ROOT / ".env", _ROOT / ".env.local")
                if f.exists() and "META_BUSINESS_ID=" in f.read_text(encoding="utf-8")]
    if not declared:
        pytest.skip("aucun `.env` ne déclare META_BUSINESS_ID ici — rien à charger")

    assert value, (
        f"{declared[0].name} déclare META_BUSINESS_ID, et un interpréteur nu obtient "
        "une chaîne vide : le générateur de guide tourne dans cette condition, et le "
        "PDF d'inscription repartirait avec « demande-le nous »")
    assert value.isdigit(), (
        f"la constante ne résout plus un numéro depuis un interpréteur nu : {value!r}. "
        "Le générateur de guide tourne dans cette condition, et le PDF d'inscription "
        "repartirait avec « demande-le nous ».")


def test_the_shipped_guide_carries_the_number_rather_than_asking_for_it():
    """Ce que l'artiste reçoit vraiment, lu dans l'artefact livré."""
    page = _ROOT / "docs/guides/index.html"
    if not page.exists():
        pytest.skip("guide non construit ici — `make guide`")
    text = page.read_text(encoding="utf-8")

    assert "Attribuer un partenaire" in text, (
        "le guide livré ne porte plus le geste de partage")
    assert "demande-le nous" not in text, (
        "le guide livré renvoie l'artiste NOUS DEMANDER une valeur que nous "
        "connaissons — c'est un aller-retour par e-mail à chaque inscription")
    # Et jamais l'ancienne consigne, celle que personne ne pouvait suivre.
    assert "ETL_DASHBOARD_SPOTIFY" not in text
    assert "Business Assets" not in text
