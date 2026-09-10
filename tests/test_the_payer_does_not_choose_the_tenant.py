"""Le payeur ne choisit pas le locataire qu'on provisionne.

Type: Test
Uses: pytest
Depends on: src/api/routers/stripe_webhook.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
`client_reference_id` arrive dans le lien de paiement, construit côté client et
**modifiable dans la barre d'adresse**. La signature Stripe passe : elle garantit que
l'événement vient bien de Stripe, pas que la valeur qu'il transporte soit légitime.

Sans appariement, la chaîne d'atteinte tenait en quatre lignes : un locataire A édite
le lien avec l'identifiant d'un locataire V, paie 10 €, et l'`ON CONFLICT (artist_id)`
écrase la ligne de V avec le client Stripe de A. A passe V en premium, puis annule dans
son propre portail — et V redevient `canceled`.

La seconde conséquence est pire que la première : **V, s'il payait réellement, cesse
d'être synchronisé**. Ses propres événements portent son vrai client Stripe, qui n'est
plus sur aucune ligne ; la mise à jour touche zéro ligne, sans erreur. Un client payant
gèle.

Même racine, cas non malveillant : un identifiant inexistant lève une violation de clé
étrangère, donc un 500, donc un rejeu Stripe pendant trois jours — carte débitée, plan
jamais posé. C'est la classe déjà payée le 2026-08-23, fermée alors sur les deux
surfaces d'ÉMISSION du lien et pas sur celle de RÉCEPTION.
"""
from __future__ import annotations

from src.api.routers.stripe_webhook import _verified_artist_id


class _Conn:
    """Une base minimale : le locataire 7 existe, et son seul compte est alice@x."""

    def __init__(self, tenants=(7,), users=((7, "alice@x"),)):
        self._tenants, self._users, self._last = set(tenants), set(users), None

    def cursor(self):
        return self

    def execute(self, sql, params):
        if "FROM saas_artists" in sql:
            self._last = (params[0] in self._tenants)
        elif "FROM saas_users" in sql:
            self._last = ((params[0], params[1]) in self._users)
        else:
            self._last = False

    def fetchone(self):
        return (1,) if self._last else None


def _session(email="alice@x"):
    return {"customer_details": {"email": email}}


def test_the_right_payer_provisions_their_own_tenant() -> None:
    assert _verified_artist_id(_Conn(), "7", _session()) == 7


def test_a_payer_cannot_provision_someone_elses_tenant() -> None:
    """Le cas malveillant : l'e-mail est celui du payeur, l'identifiant celui d'un autre."""
    conn = _Conn(tenants=(7, 42), users=((7, "alice@x"), (42, "victim@y")))
    assert _verified_artist_id(conn, "42", _session("alice@x")) is None, (
        "un payeur a provisionné le locataire d'un autre : il peut l'activer, puis "
        "l'annuler depuis son propre portail Stripe, et le vrai payeur cesse d'être "
        "synchronisé en silence")


def test_an_unknown_tenant_is_refused_before_it_can_500() -> None:
    """Une clé étrangère violée rend 500, donc Stripe rejoue trois jours : carte
    débitée, plan jamais posé."""
    assert _verified_artist_id(_Conn(), "999999", _session()) is None


def test_a_non_integer_reference_is_refused() -> None:
    """Tout ce qui n'est pas un entier vient d'un lien bricolé, quelle qu'en soit la forme."""
    for bad in ("7 OR 1=1", "", None, "abc", "7.5", "../7", "7\n42"):
        assert _verified_artist_id(_Conn(), bad, _session()) is None, bad


def test_a_session_without_an_email_is_refused_rather_than_trusted() -> None:
    """Sans e-mail, rien à apparier : on refuse au lieu de faire confiance."""
    assert _verified_artist_id(_Conn(), "7", {"customer_details": {}}) is None
    assert _verified_artist_id(_Conn(), "7", {}) is None


def test_the_email_match_is_case_and_space_insensitive() -> None:
    """Stripe rend l'e-mail tel que saisi ; la comparaison ne doit pas s'y casser."""
    assert _verified_artist_id(_Conn(), "7", _session("  Alice@X  ")) == 7
