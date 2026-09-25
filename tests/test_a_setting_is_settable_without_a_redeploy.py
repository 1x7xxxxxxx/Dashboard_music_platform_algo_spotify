"""Un réglage que seul un redéploiement peut poser laisse la fonction éteinte.

Type: Test
Uses: pytest
Depends on: src/dashboard/utils/app_settings.py, views/billing.py, views/admin.py
Persists in: nothing (le test écrit puis efface sa propre clé)

Le défaut, et il est de MA main — 2026-09-21
---------------------------------------------
Le lien de prise de rendez-vous a d'abord été lu dans `SERVICE_CALENDLY_URL`,
sans valeur par défaut. Le refus d'inventer une URL était juste : un bouton vers
une page morte, c'est un rendez-vous qu'on croit pris. Mais la conséquence ne
l'était pas — poser le lien demandait d'éditer `.env.local`, de rebâtir
l'environnement du conteneur en production, et de redémarrer. Personne ne fait ça
pour changer un lien de rendez-vous, donc la fonctionnalité restait ÉTEINTE.

Classe : `a-feature-whose-only-switch-is-a-redeploy`. Elle passe tous les tests —
le code est correct, il n'a simplement aucun moyen d'être allumé.

Ce que ce garde tient
---------------------
1. le réglage s'écrit et se relit depuis la base, sans variable d'environnement ;
2. l'environnement PRIME quand il est posé, et la page Admin le dit ;
3. les valeurs dangereuses sont REFUSÉES en nommant la raison, jamais nettoyées
   en douce — cette URL devient le `href` d'un bouton montré aux artistes ;
4. la page de facturation lit le réglage, pas la constante figée.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_CLE = "service_calendly_url"

# Every DB test here writes the SAME global row. Without a group, `--dist loadgroup`
# spreads them over workers and one reads a neighbour's value — red once in CI on
# 2026-09-25 (shard 2/6), green on rerun. Guard: test_a_shared_db_test_declares_its_group.
pytestmark = pytest.mark.xdist_group("app_settings")


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    if conn is None:
        pytest.skip("base indisponible")
    # L'état d'origine est RESTAURÉ : ce test écrit dans une table de production.
    from src.dashboard.utils.app_settings import get_setting
    avant = get_setting(None, _CLE) or ""
    try:
        depuis_base = conn.fetch_query(
            "SELECT value FROM app_settings WHERE key = %s", (_CLE,))
        avant = depuis_base[0][0] if depuis_base else ""
    except Exception:
        pytest.skip("`app_settings` absente — migration 134 non appliquée")
    yield conn
    conn.execute_query(
        "INSERT INTO app_settings (key, value) VALUES (%s, %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (_CLE, avant))
    conn.close()


def test_the_setting_round_trips_through_the_database(db, monkeypatch) -> None:
    """Écrire, relire, effacer — sans toucher à l'environnement."""
    from src.dashboard.utils.app_settings import get_setting, set_setting

    monkeypatch.delenv("SERVICE_CALENDLY_URL", raising=False)
    set_setting(db, _CLE, "https://calendly.com/essai/30min")
    assert get_setting(db, _CLE) == "https://calendly.com/essai/30min"
    set_setting(db, _CLE, "")
    assert get_setting(db, _CLE) == ""


def test_the_value_is_trimmed_but_never_rewritten(db, monkeypatch) -> None:
    """Les espaces d'un copier-coller partent ; le reste est intact ou refusé."""
    from src.dashboard.utils.app_settings import get_setting, set_setting

    monkeypatch.delenv("SERVICE_CALENDLY_URL", raising=False)
    set_setting(db, _CLE, "  https://calendly.com/essai/30min  ")
    assert get_setting(db, _CLE) == "https://calendly.com/essai/30min"


def test_the_environment_wins_when_it_is_set(db, monkeypatch) -> None:
    """Douze facteurs : on impose une valeur en prod sans toucher aux données."""
    from src.dashboard.utils.app_settings import env_impose, get_setting, set_setting

    set_setting(db, _CLE, "https://calendly.com/base/30min")
    monkeypatch.setenv("SERVICE_CALENDLY_URL", "https://calendly.com/env/30min")
    assert get_setting(db, _CLE) == "https://calendly.com/env/30min"
    assert env_impose(_CLE) is True, (
        "`env_impose` doit rendre True : sans elle, la page Admin laisse "
        "l'exploitant saisir une valeur, la voir enregistrée, et l'écran "
        "afficher l'autre — sans rien qui l'explique")
    monkeypatch.delenv("SERVICE_CALENDLY_URL", raising=False)
    assert get_setting(db, _CLE) == "https://calendly.com/base/30min"


@pytest.mark.parametrize("mauvais", [
    "javascript:alert(document.cookie)",
    # ⚠️ CELLE-CI REND LE CONTRÔLE DE SCHÉMA PORTANT, et elle manquait au premier
    # jet. `javascript:alert(1)` n'a PAS de `netloc` : il était refusé par le
    # second contrôle, pas par le premier. Mutation du 2026-09-21 — schéma
    # `javascript` autorisé — **le garde est resté vert**, tenu par le mauvais
    # contrôle. Avec un domaine, `urlparse` rend `scheme='javascript'` et
    # `netloc='evil.com'` : seul le contrôle de schéma l'arrête.
    "javascript://evil.com/%0aalert(document.cookie)",
    "data://exemple.fr/x",
    "data:text/html,<script>alert(1)</script>",
    "http://calendly.com/en-clair",
    "calendly.com/sans-schema",
    "https://",
])
def test_a_dangerous_url_is_refused_by_name(db, mauvais: str) -> None:
    """REFUSÉE, pas assainie. Cette valeur devient le `href` d'un bouton public.

    Un réglage corrigé en silence est un réglage que celui qui l'a saisi croira
    posé — et `javascript:` dans un lien montré aux artistes ferait de la page
    Admin une surface d'injection.
    """
    from src.dashboard.utils.app_settings import ReglageInvalide, set_setting

    with pytest.raises(ReglageInvalide) as e:
        set_setting(db, _CLE, mauvais)
    assert str(e.value).strip(), "le refus doit NOMMER sa raison"


def test_an_unknown_key_is_refused(db) -> None:
    """`app_settings` est une table de configuration, pas un sac fourre-tout."""
    from src.dashboard.utils.app_settings import ReglageInvalide, set_setting

    with pytest.raises(ReglageInvalide):
        set_setting(db, "cle_inventee_par_une_vue", "https://exemple.fr")


@pytest.mark.parametrize("surface", ["billing.py", "service.py"])
def test_the_page_that_draws_the_button_reads_the_setting(surface: str) -> None:
    """Sinon le champ de l'admin existe et ne change rien à l'écran.

    ⚠️ La propriété n'est PAS « `billing.py` appelle `get_setting` » — c'est
    ce qu'elle disait jusqu'au 2026-09-22, et déplacer le rendu vers la page
    dédiée l'aurait fait rougir pour une raison fausse. La propriété est :
    **toute surface qui dessine le bouton de rendez-vous résout le lien
    elle-même**. Deux surfaces le dessinent, donc deux surfaces sont gardées ;
    une troisième qui le dessinerait sans lire le réglage naîtrait figée sur
    l'environnement, et la seule façon de poser le lien redeviendrait un
    redéploiement.

    Par l'AST : le nom de la constante DOIT pouvoir être cité en prose, c'est
    là qu'on explique pourquoi elle n'est plus que le défaut.
    """
    tree = ast.parse((_ROOT / "src" / "dashboard" / "views" / surface)
                     .read_text(encoding="utf-8"))
    lit = any(isinstance(n, ast.Call)
              and (getattr(n.func, "id", None) == "get_setting"
                   or getattr(n.func, "attr", None) == "get_setting")
              for n in ast.walk(tree))
    assert lit, (
        f"`{surface}` dessine le bouton de rendez-vous sans appeler "
        "`get_setting` : le lien y redevient figé dans l'environnement, et la "
        "seule façon de le poser redevient un redéploiement.")


def test_the_admin_exposes_a_way_to_set_it() -> None:
    """NON-VACUITÉ de tout ce fichier : un réglage sans écran reste éteint."""
    src = (_ROOT / "src" / "dashboard" / "views" / "admin.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    noms = {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "_tab_reglages" in noms, (
        "la page Admin n'a plus d'onglet Réglages : le réglage est de nouveau "
        "posable uniquement par un redéploiement, ce qui est exactement le "
        "défaut que ce fichier garde.")
    appelle = any(isinstance(n, ast.Call)
                  and getattr(n.func, "id", None) == "_tab_reglages"
                  for n in ast.walk(tree))
    assert appelle, (
        "`_tab_reglages` existe mais n'est appelée nulle part — une couche "
        "débranchée, que ce dépôt a déjà payée trois fois.")
