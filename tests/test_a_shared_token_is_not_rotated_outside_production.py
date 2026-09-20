"""Un jeton que le fournisseur FAIT TOURNER ne se consomme qu'en production.

Type: Test
Uses: unittest.mock
Depends on: src/collectors/soundcloud_api_collector, src/utils/instance_identity
Persists in: nothing

Pourquoi ce garde existe
------------------------
SoundCloud fait tourner le `refresh_token` à l'usage : la valeur consommée devient
invalide, et seule la nouvelle vaut. Le magasin de credentials étant partagé entre les
instances, une collecte lancée en DÉVELOPPEMENT invalidait celui de la PRODUCTION — qui
échouait la nuit suivante sur un jeton qu'elle n'avait jamais utilisé.

Mesuré : c'est l'incident du 2026-08-24 qui a créé la classe
`a-dev-instance-sends-production-shaped-mail`. Le symptôme (des mails de dev en forme de
prod) a été réparé par `email_alerts._outbound_blocked()` ; **la cause côté credentials
est restée vivante treize mois**.

⚠️ Le garde porte sur le GESTE — « consommer un jeton que le fournisseur fait tourner » —
et non sur le nom `refresh_token`. Le geste voisin non couvert est nommé dans
`test_the_uncovered_neighbour_is_named` ci-dessous.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _collecteur():
    from src.collectors.soundcloud_api_collector import SoundCloudCollector
    c = SoundCloudCollector.__new__(SoundCloudCollector)
    c.client_id, c.client_secret = "cid", "csecret"     # pragma: allowlist secret
    c.refresh_token = "rt-partage"                      # pragma: allowlist secret
    c.artist_id = 1
    c.session = mock.MagicMock()
    c._access_token = None
    c._token_expires_at = 0.0
    return c


@pytest.mark.parametrize("env", ["local", "ci", "staging", ""])
def test_rotation_is_refused_outside_production(env: str) -> None:
    """LE GARDE. Hors production, la rotation lève AVANT tout appel réseau."""
    c = _collecteur()
    with mock.patch.dict("os.environ", {"STREAMLYTICS_ENV": env}, clear=False):
        with pytest.raises(RuntimeError) as e:
            c._get_user_token()
    assert "REFUSÉE" in str(e.value)
    assert not c.session.post.called, (
        "la rotation a été REFUSÉE mais l'appel réseau a quand même eu lieu — donc le "
        "jeton de production a été consommé. Le garde doit lever AVANT le POST.")


def test_the_refusal_says_what_to_do() -> None:
    """Un blocage sans alternative se contourne au lieu de changer l'habitude."""
    c = _collecteur()
    with mock.patch.dict("os.environ", {"STREAMLYTICS_ENV": "local"}, clear=False):
        with pytest.raises(RuntimeError) as e:
            c._get_user_token()
    message = str(e.value)
    assert "STREAMLYTICS_ENV=production" in message
    assert "client_credentials" in message, (
        "le refus ne nomme pas le mode qui reste disponible — un opérateur conclura "
        "qu'on ne peut plus collecter SoundCloud en local du tout.")


def test_production_is_not_blocked() -> None:
    """FAUX POSITIF fabriqué : la production DOIT pouvoir faire tourner son jeton.

    Sans cette moitié, un garde qui refuse partout passerait les assertions ci-dessus —
    et casserait la collecte réelle.
    """
    c = _collecteur()
    reponse = mock.MagicMock(status_code=200)
    reponse.json.return_value = {"access_token": "at", "expires_in": 3600}
    c.session.post.return_value = reponse
    with mock.patch.dict("os.environ", {"STREAMLYTICS_ENV": "production"}, clear=False):
        c._get_user_token()
    assert c.session.post.called, "la production doit pouvoir faire tourner son jeton"
    assert c._access_token == "at"


def test_meta_does_not_write_the_shared_store_outside_production() -> None:
    """Le GESTE VOISIN, couvert à la mesure de sa conséquence — qui n'est pas la même.

    Trouvé par la version précédente de ce test, qui balayait les collecteurs persistant
    un credential pendant un rafraîchissement : `instagram_api_collector.py:107` le fait.

    ⚠️ **La conséquence diffère, et je l'ai vérifiée avant d'écrire le garde.** Meta
    utilise `fb_exchange_token`, qui ÉMET un nouveau jeton longue durée **sans invalider
    l'ancien** — contrairement à SoundCloud. La production ne casserait donc pas. Ce qui
    change quand même est `expires_at` : un jeton rafraîchi depuis une copie ancienne
    peut valoir moins longtemps que celui que la prod détenait.
    Le collecteur garde donc le jeton neuf EN MÉMOIRE (la collecte locale marche), et
    seule l'ÉCRITURE partagée est refusée. Deux gestes, une cause, deux sévérités.
    """
    from src.collectors.instagram_api_collector import InstagramCollector
    c = InstagramCollector.__new__(InstagramCollector)
    c.app_id, c.app_secret = "aid", "asecret"          # pragma: allowlist secret
    c.access_token, c.artist_id = "vieux", 1           # pragma: allowlist secret
    c.base_url, c.session = "https://graph.facebook.com/v21.0", mock.MagicMock()
    reponse = mock.MagicMock(status_code=200)
    reponse.json.return_value = {"access_token": "neuf", "expires_in": 5184000}
    c.session.get.return_value = reponse

    with mock.patch.dict("os.environ", {"STREAMLYTICS_ENV": "local"}, clear=False), \
         mock.patch("src.utils.credential_loader.update_platform_secret") as ecrit:
        ok = c._refresh_access_token()
    assert ok is True, "la collecte locale doit continuer avec le jeton neuf en mémoire"
    assert c.access_token == "neuf"
    assert not ecrit.called, (
        "une instance hors production a ÉCRIT dans le magasin de credentials partagé — "
        "elle remplace le jeton de la production et peut raccourcir son `expires_at`.")


def test_meta_still_persists_in_production() -> None:
    """FAUX POSITIF fabriqué : la production DOIT persister son jeton rafraîchi."""
    from src.collectors.instagram_api_collector import InstagramCollector
    c = InstagramCollector.__new__(InstagramCollector)
    c.app_id, c.app_secret = "aid", "asecret"          # pragma: allowlist secret
    c.access_token, c.artist_id = "vieux", 1           # pragma: allowlist secret
    c.base_url, c.session = "https://graph.facebook.com/v21.0", mock.MagicMock()
    reponse = mock.MagicMock(status_code=200)
    reponse.json.return_value = {"access_token": "neuf", "expires_in": 5184000}
    c.session.get.return_value = reponse

    with mock.patch.dict("os.environ", {"STREAMLYTICS_ENV": "production"}, clear=False), \
         mock.patch("src.utils.credential_loader.update_platform_secret") as ecrit:
        c._refresh_access_token()
    assert ecrit.called, (
        "la production ne persiste plus son jeton rafraîchi — au prochain démarrage elle "
        "repartirait de l'ancien, et le garde aurait cassé ce qu'il protège.")


def test_no_third_collector_writes_the_shared_store_unguarded() -> None:
    """La PORTÉE, rejouée : un troisième collecteur qui écrirait doit être vu.

    Les deux connus sont couverts. Ce test échoue si un autre collecteur se met à
    persister un credential pendant un rafraîchissement sans passer par
    `is_production()` — pour que la portée soit rouverte plutôt qu'oubliée.
    """
    import ast
    _COUVERTS = {"soundcloud_api_collector.py", "instagram_api_collector.py"}
    coupables = []
    for f in sorted((ROOT / "src" / "collectors").glob("*.py")):
        if f.name in _COUVERTS:
            continue
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            corps = ast.dump(noeud)
            if "update_platform_secret" in corps and "is_production" not in corps:
                coupables.append(f"{f.name}::{noeud.name}")
    assert not coupables, (
        f"collecteur(s) écrivant le magasin partagé sans garde d'instance : {coupables}.\n"
        "Si ce fournisseur INVALIDE l'ancien jeton, bloquer l'appel (cas SoundCloud). "
        "S'il ne l'invalide pas, bloquer seulement l'ÉCRITURE (cas Meta). La question à "
        "poser au fournisseur est : « l'ancien jeton survit-il au rafraîchissement ? »")
