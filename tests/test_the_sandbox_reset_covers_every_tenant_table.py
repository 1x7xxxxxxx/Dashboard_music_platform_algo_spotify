"""Le reset du bac à sable couvre TOUTES les tables du locataire, ou il le dit.

Type: Test
Uses: importlib
Depends on: tools/create_sandbox.py, src/utils/tenant_tables.py
Persists in: nothing

`--reset` existe pour rejouer la mise en route depuis zéro. Sa liste de tables était
écrite à la main et en portait **six** ; le schéma en compte **81** scopées-locataire.
**75 n'étaient pas vidées** — Meta 26, Apple 4, Instagram 3, Hypeddit 2, ML 2,
SoundCloud 1, SACEM 1 — donc « depuis zéro » n'était vrai que pour Spotify/S4A et
YouTube, et l'écart était invisible parce que rien ne comparait la liste au schéma.

⚠️ **Et la correction évidente aurait détruit le compte.** `tenant_scoped_tables()`
répond à « cette colonne désigne-t-elle un locataire par son TYPE », pas à « cette
table est-elle sûre à vider ». `saas_users` en fait partie : dériver les 81 et tout
vider supprimait le login du bac à sable à chaque reset, contre le contrat écrit de
l'outil (« same tenant, same login »). Refusé par `code-critic` AVANT écriture.

Ce que ce garde fixe
--------------------
1. **La couverture** : l'union de ce qu'on vide et de ce qu'on préserve ÉGALE le schéma.
   Ce n'est pas tautologique — `tenant_scoped_tables()` bouge à chaque migration, donc
   ce test échoue au moment précis où une table neuve apparaît sans qu'un humain ait
   tranché son sort. C'est exactement l'omission silencieuse qui a produit le trou de 75.
2. **Les quatre dangereuses, par leur NOM.** `saas_users`, `active_sessions`,
   `app_error_log` et `data_revisions` sont ancrées nommément : les déplacer vers le
   côté « vidé » fait rougir ce test par leur nom, pas par un comptage global. La portée
   d'un garde est le défaut, et un compte global laisserait passer un échange.
3. **Aucune table des deux côtés à la fois.**

Ce qu'il ne couvre PAS
----------------------
Que chaque table préservée MÉRITE de l'être : le classement reste un jugement humain,
écrit avec sa raison dans `_PRESERVE_ON_RESET`. Ce garde vérifie qu'aucune table
n'échappe au jugement, pas que le jugement soit bon.

Mutation record — 2026-09-18 : en retirant `saas_users` de `_PRESERVE_ON_RESET`, ce
garde le nomme ; en retirant une table quelconque des deux ensembles (via un filtre sur
la dérivation), la couverture rougit.

---
rex: []
---
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

# Les quatre dont l'effacement est une PERTE, ancrées par leur nom.
_JAMAIS_VIDEES = ("saas_users", "active_sessions", "app_error_log", "data_revisions")


def _sandbox():
    spec = importlib.util.spec_from_file_location(
        "_sandbox_tool", _ROOT / "tools" / "create_sandbox.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_schema_still_names_tenant_tables() -> None:
    """Anti-vacuité : deux ensembles vides couvrent un schéma vide."""
    from src.utils.tenant_tables import tenant_scoped_tables

    assert len(tenant_scoped_tables()) >= 50, (
        "moins de 50 tables scopées-locataire lues dans le schéma — il y en avait 81 "
        "le 2026-09-18. La dérivation est cassée, et tout ce fichier devient vert à "
        "vide.")


def test_every_tenant_table_is_either_wiped_or_preserved() -> None:
    from src.utils.tenant_tables import tenant_scoped_tables

    mod = _sandbox()
    vide = set(mod._tenant_data_tables())
    garde = set(mod._PRESERVE_ON_RESET)
    schema = set(tenant_scoped_tables())

    oubliees = sorted(schema - vide - garde)
    assert not oubliees, (
        f"{len(oubliees)} table(s) scopée(s)-locataire ne sont ni vidées ni "
        "explicitement préservées : personne n'a tranché leur sort, et le silence "
        "signifie « pas vidée ». C'est l'omission qui a laissé 75 tables derrière un "
        f"`--reset` jusqu'au 2026-09-18.\n  {oubliees[:12]}")

    inventees = sorted((vide | garde) - schema)
    assert not inventees, (
        f"{inventees} sont classées ici mais n'existent pas (ou ne sont pas "
        "scopées-locataire) dans le schéma : une liste qui nomme des tables mortes "
        "fait croire à une couverture qu'elle n'a pas.")


def test_no_table_is_on_both_sides(monkeypatch) -> None:
    mod = _sandbox()
    deux = set(mod._tenant_data_tables()) & set(mod._PRESERVE_ON_RESET)
    assert not deux, f"{sorted(deux)} sont à la fois vidées et préservées."


def test_the_account_tables_are_never_wiped() -> None:
    """Les quatre dont l'effacement est une PERTE, nommées une par une."""
    mod = _sandbox()
    vide = set(mod._tenant_data_tables())
    fautives = [t for t in _JAMAIS_VIDEES if t in vide]
    assert not fautives, (
        f"{fautives} seraient VIDÉES par `--reset`.\n"
        "`saas_users` est le compte de connexion, et l'outil promet « same tenant, "
        "same login ». `app_error_log` et `data_revisions` portent des historiques "
        "dont la survie EST la raison d'être. `active_sessions` n'est pas une donnée "
        "collectée.\n"
        "Si l'une doit vraiment être vidée un jour, c'est une décision à écrire — pas "
        "un effet de bord d'une dérivation.")


def test_every_preserved_table_says_why() -> None:
    """Une exemption sans raison écrite est indistinguable d'un oubli."""
    mod = _sandbox()
    muettes = [t for t, raison in mod._PRESERVE_ON_RESET.items()
               if not (raison or "").strip()]
    assert not muettes, (
        f"{muettes} sont préservées sans raison écrite. Le prochain lecteur ne peut "
        "pas distinguer « vérifié » de « oublié », et les deux se ressemblent.")
