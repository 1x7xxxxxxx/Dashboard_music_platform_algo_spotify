"""L'application n'a pas besoin d'exécuter des commandes sur l'hôte.

Type: Test
Uses: pytest, live Postgres (facultatif — les prédicats statiques tournent sans base)
Depends on: migrations/098_the_app_is_not_a_superuser.sql, docker-compose.yml
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
L'application — dashboard, API, DAGs — se connecte en `postgres`, donc en
SUPERUTILISATEUR. Ce que cela veut dire concrètement, et qui n'est pas « lire les
tables » :

* `COPY … TO PROGRAM` exécute une commande shell **sur l'hôte de la base** ;
* `pg_authid` livre les empreintes de mots de passe de tous les rôles ;
* aucune contrainte, aucun garde en base ne lui résiste.

Entre une erreur applicative — une injection, un DSN qui fuit dans un log, un
`except` trop large — et la machine, il n'y avait aucune couche. Les 0/93 tables sous
RLS sont un choix assumé, mais elles n'ajoutent rien ici non plus.

Ce que ce fichier garde
-----------------------
La migration 098 crée `streamlytics_app`, prouvé suffisant (`make db-role-check`).
Ce test empêche que ce rôle soit un jour promu — par une migration ultérieure, par un
correctif pressé — et vérifie que le fichier compose lit le rôle dans
l'environnement au lieu de l'imposer. La BASCULE, elle, reste un geste
d'exploitation : ce test ne l'exige pas, il rend impossible que le filet disparaisse.
"""
from __future__ import annotations

import os
import re
import socket
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=4)
def _read(rel: str) -> str:
    """Lu à l'APPEL, pas à l'import.

    Une lecture au niveau module fait lever `FileNotFoundError` à la collecte le jour
    où le fichier disparaît : pytest rapporte « errors » sans nommer une seule des
    propriétés perdues. Un échec nomme ce qu'on a perdu, une erreur de collecte non.
    """
    return (ROOT / rel).read_text(encoding="utf-8")


def MIG() -> str:
    return _read("migrations/098_the_app_is_not_a_superuser.sql")
# LE FICHIER VERSIONNÉ, PAS CELUI DE CETTE MACHINE.
#
# `docker-compose.yml` est gitignoré (chaque poste a le sien, la prod a le sien) : un
# garde qui le lit ne tourne jamais en CI et ne dit rien de ce que le dépôt livre.
# C'est la classe « un contrôle qui ne peut jamais passer », déjà payée trois fois
# ici. Le contrat public est `docker-compose.example.yml` ; le local est vérifié en
# plus, quand il existe.
def COMPOSE() -> str:
    return _read("docker-compose.example.yml")


_LOCAL = ROOT / "docker-compose.yml"

# Tout ce qu'un rôle applicatif ne doit jamais porter. `pg_read_server_files` et
# `pg_write_server_files` sont là parce qu'ils redonnent, par un autre chemin, ce que
# `NOSUPERUSER` venait de retirer.
FORBIDDEN = ("SUPERUSER", "CREATEDB", "CREATEROLE", "BYPASSRLS",
             "pg_execute_server_program", "pg_read_server_files",
             "pg_write_server_files", "pg_monitor")


def _statements(sql: str) -> list[str]:
    """Le SQL sans ses commentaires — un garde ne se juge pas sur sa propre prose."""
    no_line = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in no_line.split(";") if s.strip()]


def test_the_migration_never_grants_what_it_exists_to_deny() -> None:
    for stmt in _statements(MIG()):
        for word in FORBIDDEN:
            # NOSUPERUSER contient SUPERUSER : on cherche le mot NON préfixé de NO.
            for m in re.finditer(rf"(?<![A-Z_]){re.escape(word)}\b", stmt, re.I):
                before = stmt[max(0, m.start() - 2):m.start()].upper()
                assert before == "NO" or word.startswith("pg_") and "GRANT" not in stmt.upper(), (
                    f"la migration du rôle applicatif accorde `{word}` :\n  {stmt[:200]}")


def test_the_migration_pins_the_role_down_on_every_replay() -> None:
    """`make migrate` est rejoué à chaque déploiement : c'est la ceinture."""
    assert re.search(r"ALTER ROLE\s+streamlytics_app\s+NOSUPERUSER", MIG(), re.I), (
        "rien ne redescend le rôle s'il a été promu à la main entre deux "
        "déploiements — or c'est le seul moment où on peut s'en apercevoir")


def test_no_password_is_committed_in_the_migration() -> None:
    assert "PASSWORD '" not in MIG().replace("PASSWORD %L", ""), (
        "un mot de passe en clair dans un fichier versionné")
    assert "current_setting('app.streamlytics_app_password'" in MIG()


_READS_ENV = re.compile(r"DATABASE_USER:\s*\$\{DATABASE_USER:-postgres\}")


def test_the_shipped_compose_template_reads_the_role_from_the_environment() -> None:
    """Imposer `postgres` en dur rend la bascule impossible sans éditer le dépôt."""
    assert _READS_ENV.search(COMPOSE()), (
        "docker-compose.example.yml fige DATABASE_USER : chaque déploiement issu de "
        "ce gabarit repartirait en superutilisateur, et basculer demanderait un "
        "commit — donc ne se ferait pas")


def test_the_local_compose_did_not_drift_from_the_template() -> None:
    """Le fichier de cette machine est ignoré par git : rien d'autre ne le compare."""
    if not _LOCAL.exists():
        pytest.skip("pas de docker-compose.yml local")
    local = _LOCAL.read_text(encoding="utf-8")
    if "DATABASE_USER" not in local:
        pytest.skip("ce compose local ne câble pas la base de l'app")
    assert _READS_ENV.search(local), (
        "le compose de CETTE machine fige DATABASE_USER alors que le gabarit le lit "
        "dans l'environnement — la dérive silencieuse entre le poste et le dépôt")


# ── Le contrôle sur la base vivante ──────────────────────────────────────────
def _db_ready() -> bool:
    if os.environ.get("DATABASE_URL"):
        return True
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=1.5):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _db_ready(), reason="pas de Postgres joignable sur 5433")
def test_the_live_role_holds_its_bounds() -> None:
    """Le même contrôle que `make db-role-check`, mais dans la suite."""
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        pytest.skip("connexion indisponible")
    try:
        row = db.fetch_query(
            "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls "
            "FROM pg_roles WHERE rolname = 'streamlytics_app'")
        if not row:
            pytest.skip("rôle absent de CETTE base — `make migrate` ne l'a pas jouée")
        assert row[0][0] is False, (
            "streamlytics_app porte un attribut de privilège : le rôle applicatif "
            "peut de nouveau exécuter des commandes sur l'hôte")
        host = db.fetch_query(
            "SELECT count(*) FROM pg_auth_members m "
            "JOIN pg_roles r ON r.oid = m.roleid JOIN pg_roles u ON u.oid = m.member "
            "WHERE u.rolname = 'streamlytics_app' AND r.rolname IN "
            "('pg_execute_server_program','pg_read_server_files','pg_write_server_files')")
        assert host[0][0] == 0, (
            "le rôle applicatif est membre d'un rôle d'accès à l'hôte — "
            "`NOSUPERUSER` ne protège plus de rien")
    finally:
        db.close()
