"""Une récompense qu'aucun code n'applique ne se promet pas au futur passif.

Type: Test
Uses: ast, pytest
Depends on: src/dashboard/views/{referral,billing,referral_admin}.py,
            src/dashboard/views/register.py
Persists in: nothing

Le défaut, balayé le 2026-09-21
--------------------------------
Deux surfaces affichaient, au futur et à la voix passive :

    « Ils seront appliqués avant votre prochain cycle de facturation. »
    « Un rabais de 20% SERA APPLIQUÉ à votre premier mois payant. »

comme si un mécanisme s'en chargeait. Balayé sur tout l'arbre : **rien ne
consomme `referral_free_months` ni `first_month_discount_pct`.** Les deux
colonnes sont ÉCRITES à l'inscription (`register._apply_referral`), LUES par deux
pages d'affichage et un tableau de bord admin, et par personne d'autre. La montée
en gamme passe par un lien de paiement Stripe **statique**
(`STRIPE_CHECKOUT_URL`), qui ne peut porter aucune remise par client sans un
appel à l'API Stripe que personne n'écrit.

Personne n'avait encore été lésé — zéro ligne dans `referral_events` ce jour-là.
C'est exactement la fenêtre où la correction ne coûte rien : au premier filleul,
la promesse devient un impayé, et l'artiste l'apprend sur sa facture.

Classe : `a-promise-with-no-mechanism-behind-it`.

Ce que ce garde tient
---------------------
1. tant qu'aucun écrivain n'existe, le texte affiché ne dit pas « automatique » ;
2. **et la réciproque** : le jour où quelqu'un écrit le mécanisme, ce garde le
   voit et exige que le texte redevienne une promesse ferme. Sans cette moitié,
   il figerait la prudence en dogme et le produit mentirait dans l'autre sens.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Les colonnes de récompense, et LE lieu qui a le droit de les écrire : le
# parcours d'inscription, qui les crédite.
_COLONNES = ("referral_free_months", "first_month_discount_pct")
_CREDITEUR = "src/dashboard/views/register.py"

# Les surfaces qui PARLENT de la récompense à l'utilisateur.
_SURFACES = ("src/dashboard/views/referral.py",
             "src/dashboard/views/billing.py")

_PROD = [p for p in (_ROOT / "src").rglob("*.py") if "__pycache__" not in str(p)]

# Une promesse d'automatisme. Le motif cherche la FORME qui trompe — un futur ou
# un adverbe d'automaticité accolé à l'application — pas le mot « appliquer »,
# qui doit rester disponible pour dire « on les applique à la main ».
# ⚠️ SYMÉTRIQUE, et il ne l'était pas au premier jet. Une mutation du 2026-09-22
# — « Vos mois offerts sont **crédités automatiquement** » — passait au travers :
# le motif ne portait l'adverbe qu'APRÈS `appliqu`, et devant les verbes il ne
# connaissait pas `crédit`. Un prédicat qui attrape une TOURNURE plutôt qu'une
# PROPRIÉTÉ laisse la classe vivante sous la phrase d'à côté (règle transverse 20).
#
# Les trois verbes couverts sont ceux d'une récompense : appliquer, créditer,
# envoyer. L'adverbe est accepté des deux côtés du verbe.
_VERBES = r"(?:appliqu|crédit|credit|envoy|débit|debit)"
_PROMESSE = re.compile(
    rf"(ser(?:a|ont)\s+{_VERBES}"
    rf"|s'appliquent\s+automatiquement"
    rf"|{_VERBES}\w*\s+automatiquement"
    rf"|automatiquement\s+{_VERBES}"
    r"|automatically\s+(?:applied|credited|sent)"
    r"|will\s+be\s+(?:applied|credited|sent))", re.I)


def _chaines(path: pathlib.Path) -> list[str]:
    """Les littéraux du module, DOCSTRINGS ET COMMENTAIRES EXCLUS.

    ⚠️ Par l'AST. Ce fichier documente la promesse fautive en la CITANT : un
    prédicat textuel rougirait sur la prose qui explique le défaut — quatre
    gardes de ce dépôt se sont fait prendre ainsi, et deux sur leur propre
    docstring le 2026-09-21.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):       # pragma: no cover
        return []
    docs = set()
    for n in ast.walk(tree):
        corps = getattr(n, "body", None)
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                          ast.AsyncFunctionDef)) and corps \
                and isinstance(corps[0], ast.Expr) \
                and isinstance(corps[0].value, ast.Constant) \
                and isinstance(corps[0].value.value, str):
            docs.add(id(corps[0].value))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                and id(n) not in docs:
            out.append(n.value)
        elif isinstance(n, ast.JoinedStr):
            out.append("".join(v.value for v in n.values
                               if isinstance(v, ast.Constant)
                               and isinstance(v.value, str)))
    return out


def _consommateurs() -> list[str]:
    """Les fichiers qui font autre chose que LIRE ou CRÉDITER la récompense.

    Un consommateur DÉCRÉMENTE ou remet à zéro. Le prédicat cherche donc la
    colonne du côté gauche d'un `SET`, hors du fichier qui la crédite.
    """
    out = []
    for p in _PROD:
        rel = str(p.relative_to(_ROOT))
        if rel == _CREDITEUR:
            continue
        for sql in _chaines(p):
            for col in _COLONNES:
                if re.search(rf"SET\s+[^;]*\b{col}\s*=", sql, re.I | re.S):
                    out.append(rel)
                    break
    return sorted(set(out))


def test_the_reward_still_has_no_consumer() -> None:
    """LA PRÉMISSE. Tout ce fichier repose dessus ; on la mesure, on ne la suppose pas."""
    consommateurs = _consommateurs()
    if consommateurs:
        pytest.skip(
            f"un mécanisme est apparu ({consommateurs}) — c'est une bonne "
            "nouvelle, et `test_the_promise_firms_up_once_a_mechanism_exists` "
            "prend le relais")
    assert True


@pytest.mark.parametrize("rel", _SURFACES)
def test_no_surface_promises_an_automatic_application(rel: str) -> None:
    if _consommateurs():
        pytest.skip("un mécanisme existe : la promesse ferme est désormais légitime")
    coupables = [" ".join(s.split())[:110] for s in _chaines(_ROOT / rel)
                 if _PROMESSE.search(s)]
    assert not coupables, (
        f"{rel} promet une application automatique :\n  " + "\n  ".join(coupables)
        + "\nRien ne consomme " + " ni ".join(_COLONNES) + " : le lien de paiement "
        "Stripe est statique et ne porte pas de remise par client. Dis que "
        "l'application est manuelle, ou écris le mécanisme.")


def test_the_promise_firms_up_once_a_mechanism_exists() -> None:
    """LA RÉCIPROQUE, et elle compte autant.

    Un garde qui n'interdit que l'excès de promesse fige la prudence : le jour où
    les coupons Stripe sont posés, l'artiste lirait encore « écris-nous », et on
    lui ferait faire à la main un geste que la machine fait. Le mensonge par
    défaut est un mensonge aussi.
    """
    consommateurs = _consommateurs()
    if not consommateurs:
        pytest.skip("aucun mécanisme : c'est l'autre test qui s'applique")
    manuelles = []
    for rel in _SURFACES:
        for s in _chaines(_ROOT / rel):
            if re.search(r"pas encore automatique|à la main|by hand|not yet automatic", s, re.I):
                manuelles.append(f"{rel} : {' '.join(s.split())[:90]}")
    assert not manuelles, (
        f"un mécanisme existe ({consommateurs}) et les pages disent encore que "
        "c'est manuel :\n  " + "\n  ".join(manuelles))


def test_the_operator_can_see_what_is_owed() -> None:
    """Tant que c'est manuel, quelqu'un doit pouvoir TENIR la promesse.

    Dire à l'artiste « écris-nous » sans donner à l'exploitant la liste chiffrée
    de ce qu'il doit, c'est déplacer le problème d'un cran, pas le résoudre.

    ⚠️ LE PRÉDICAT CHERCHE UNE LECTURE SQL, PAS LE NOM DE LA COLONNE — et la
    première version faisait l'erreur. Elle testait `col in sql`, où `sql` était
    la concaténation de TOUTES les chaînes du module, y compris la légende qui
    EXPLIQUE le défaut et qui cite les deux colonnes. Mutation du 2026-09-21 :
    les deux colonnes retirées de la requête et remplacées par des zéros
    constants — **le garde est resté vert**, tenu debout par sa propre prose.
    C'est la cinquième fois que ce dépôt prend un garde textuel sur son propre
    texte, et la leçon ne change pas : on lit la STRUCTURE.
    """
    admin = _ROOT / "src" / "dashboard" / "views" / "referral_admin.py"
    requetes = [s for s in _chaines(admin) if re.search(r"\bSELECT\b", s, re.I)]
    assert requetes, "la page d'administration ne porte plus aucune requête"
    for col in _COLONNES:
        lu = any(re.search(rf"\b{col}\b[^;]*\bFROM\b", s, re.I | re.S)
                 or re.search(rf"\bWHERE\b[^;]*\b{col}\b", s, re.I | re.S)
                 for s in requetes)
        assert lu, (
            f"aucune REQUÊTE de `referral_admin.py` ne lit `{col}` : "
            "l'exploitant n'a aucun moyen de savoir ce qu'il doit, et la promesse "
            "faite à l'artiste ne repose sur personne. (Le nom cité dans une "
            "légende ne compte pas — c'est ce qui a rendu ce garde aveugle au "
            "premier jet.)")


def test_the_predicate_sees_the_sentence_it_was_written_for() -> None:
    """NON-VACUITÉ. Les deux phrases exactes qui vivaient dans le produit."""
    assert _PROMESSE.search(
        "Ils seront appliqués avant votre prochain cycle de facturation.")
    assert _PROMESSE.search(
        "Un rabais de 20% sera appliqué à votre premier mois payant.")
    assert _PROMESSE.search("They will be applied before your next billing cycle.")
    # La tournure qui ÉCHAPPAIT au premier jet — mutation du 2026-09-22.
    assert _PROMESSE.search(
        "Vos mois offerts sont crédités automatiquement sur votre abonnement.")
    assert _PROMESSE.search("Le rabais sera crédité à la facture suivante.")
    assert _PROMESSE.search("Your free months are automatically credited.")
    # Et la version honnête ne doit PAS déclencher — sinon le remède est interdit.
    assert not _PROMESSE.search(
        "Écris-nous avant ton prochain paiement et on les applique sur ton "
        "abonnement — l'application n'est pas encore automatique.")
    assert not _PROMESSE.search(
        "Write to us before your next payment and we apply them.")
