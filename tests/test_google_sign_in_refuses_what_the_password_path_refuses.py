"""La connexion Google ne laisse entrer personne que le mot de passe refuserait.

Type: Guard
Uses: ast, src.dashboard.utils.google_auth
Depends on: saas_users (migration 135)
Persists in: nothing

Pourquoi ce fichier existe
---------------------------
La première version du design de la connexion Google a été critiquée AVANT qu'une
ligne soit écrite, et la critique a trouvé **trois trous qui laissaient entrer
quelqu'un que le système refuse aujourd'hui** :

    1. le second facteur n'était jamais redemandé   → contournement du TOTP
    2. `active = FALSE` n'était jamais relu          → contournement d'une révocation
    3. `password_hash IS NULL` n'était pas traité    → plantage sur surface anonyme

Aucun des trois ne se voyait dans un test : ils ne se voient qu'en comparant, ligne
à ligne, ce que le chemin mot de passe vérifie et ce que le chemin Google oubliait.
C'est la raison d'être de ce fichier — il fixe la comparaison pour qu'un quatrième
chemin d'entrée ne puisse pas oublier les mêmes choses.

⚠️ Ce que ces tests ne prouvent PAS
------------------------------------
Ils ne prouvent pas que Google se comporte comme on le croit. Ils prouvent que NOTRE
code réagit correctement à ce que Google renvoie — le jeton est simulé. Le
comportement réel de Google est vérifié une fois, à la main, à la mise en route ; il
est décrit dans le runbook.
"""
from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"

#: Le seul fichier qui a le droit de lire `st.user`.
_LA_COUTURE = "src/dashboard/utils/google_auth.py"


# ══════════════════════════════════════════════════════════════════════════
# 1. UNE SEULE AUTORITÉ
# ══════════════════════════════════════════════════════════════════════════

def test_streamlit_user_is_read_at_exactly_one_seam() -> None:
    """`st.user` est lu dans `google_auth.py` et nulle part ailleurs.

    C'est LE principe d'architecture, et il porte tout le reste : `st.user` dit
    « Google a reconnu quelqu'un », pas « cette personne peut entrer ». Entre les
    deux il y a quatre contrôles. Une page qui lirait `st.user.is_logged_in` pour
    décider quoi que ce soit les sauterait tous les quatre.

    Ce dépôt connaît le prix de deux autorités pour un même fait — `auth.py` le dit
    sur la résolution de plan : « Two copies of this precedence would drift towards
    billing a customer for premium while a nightly job treats them as free. »

    Par l'AST : une mention de `st.user` dans un commentaire ou une docstring — et
    il y en a plusieurs, ce fichier-ci en porte — ne compte pas.
    """
    fautifs: list[str] = []
    for f in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        rel = str(f.relative_to(_ROOT))
        if rel == _LA_COUTURE:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if (isinstance(n, ast.Attribute) and n.attr == "user"
                    and getattr(n.value, "id", None) == "st"):
                fautifs.append(f"{rel}:{n.lineno}")

    assert not fautifs, (
        f"`st.user` est lu hors de la couture : {fautifs}. Il dit que Google a "
        "reconnu quelqu'un, PAS que cette personne peut entrer — entre les deux il "
        f"y a quatre contrôles, tous dans `{_LA_COUTURE}`. Une seconde lecture les "
        "saute tous.")


def test_the_seam_itself_still_reads_it() -> None:
    """NON-VACUITÉ du test ci-dessus : il passerait sur un dépôt sans Google."""
    tree = ast.parse((_ROOT / _LA_COUTURE).read_text(encoding="utf-8"))
    lit = any(isinstance(n, ast.Attribute) and n.attr == "user"
              and getattr(n.value, "id", None) == "st"
              for n in ast.walk(tree))
    assert lit, (
        f"`{_LA_COUTURE}` ne lit plus `st.user` : le test de couture unique passe "
        "sur un dépôt où plus rien ne lit l'identité Google, donc il ne garde rien.")


# ══════════════════════════════════════════════════════════════════════════
# 2. LES QUATRE CONTRÔLES, EXERCÉS
# ══════════════════════════════════════════════════════════════════════════

class _FauxUser(dict):
    """`st.user` est dict-like, pas un dict — il porte `is_logged_in` en attribut."""

    def __init__(self, **claims):
        super().__init__(**claims)
        self.is_logged_in = True


class _FauxDB:
    """Une base qui rend ce qu'on lui a dit, et RETIENT ce qu'on lui écrit."""

    def __init__(self, par_sub=None, par_email=None):
        self._par_sub = par_sub
        self._par_email = par_email
        self.ecritures: list[tuple] = []

    def fetch_query(self, sql, params=None):
        if "google_sub = %s" in sql:
            return [self._par_sub] if self._par_sub else []
        return [self._par_email] if self._par_email else []

    def execute_query(self, sql, params=None):
        self.ecritures.append((sql, params))


def _ligne(*, uid=7, email="a@exemple.fr", verifie=True, totp=False,
           actif=True, sub=None, pw_hash="$2b$xx"):
    """Une ligne `saas_users` dans l'ORDRE que la requête de la couture demande."""
    return (uid, "artiste", email, pw_hash, 3, "artist", verifie, totp,
            "SECRET" if totp else None, actif, sub)


@pytest.fixture
def ga(monkeypatch):
    from src.dashboard.utils import google_auth
    return google_auth


def _poser_user(monkeypatch, ga, **claims):
    monkeypatch.setattr(ga.st, "user", _FauxUser(**claims), raising=False)


def test_an_email_google_has_not_verified_is_refused(monkeypatch, ga) -> None:
    """LE BLOCAGE AMONT. Google peut rendre une adresse NON vérifiée.

    Typiquement sur certains comptes Workspace. La traiter comme vérifiée est
    exactement ce qui ouvre la pré-inscription : quelqu'un fait porter à son compte
    Google l'adresse de quelqu'un d'autre, et entre sur son compte.
    """
    _poser_user(monkeypatch, ga, sub="G1", email="a@exemple.fr",
                email_verified=False, name="A")
    r = ga.identite_courante()
    assert isinstance(r, ga.Refus), (
        "une adresse que Google n'a PAS vérifiée a été acceptée comme identité")
    assert r.raison == "google.email_not_verified"


def test_a_verified_identity_comes_through(monkeypatch, ga) -> None:
    """LA RÉCIPROQUE. Sans elle, un refus systématique passerait le test ci-dessus."""
    _poser_user(monkeypatch, ga, sub="G1", email="A@Exemple.FR",
                email_verified=True, name="Artiste")
    r = ga.identite_courante()
    assert isinstance(r, ga.Identite)
    assert r.sub == "G1"
    assert r.email == "a@exemple.fr", "l'adresse doit être normalisée en minuscules"


def test_a_deactivated_account_cannot_come_in_through_google(ga) -> None:
    """CONTOURNEMENT DE RÉVOCATION — trou nº 2 du design initial.

    La requête du chemin mot de passe porte `AND active = TRUE` depuis toujours.
    Le chemin Google ne le portait pas : un accès coupé par l'administrateur
    continuait d'entrer.
    """
    db = _FauxDB(par_sub=_ligne(actif=False, sub="G1"))
    user, refus = ga.trouver_ou_refuser(db, ga.Identite("G1", "a@exemple.fr", "A"))
    assert user is None, "un compte désactivé a été hydraté"
    assert refus is not None and refus.raison == "google.account_inactive"


def test_a_deactivated_account_does_not_fall_through_to_signup(ga) -> None:
    """LE TROU DÉRIVÉ, et c'est le plus vicieux des deux.

    Si un compte inactif rendait simplement « inconnu » au lieu d'un refus, la
    personne serait routée vers l'INSCRIPTION — et obtiendrait un second compte
    tout neuf sur une adresse qu'un humain avait fermée exprès. La révocation
    deviendrait une formalité qu'il suffit de recommencer.
    """
    db = _FauxDB(par_email=_ligne(actif=False, sub=None))
    user, refus = ga.trouver_ou_refuser(db, ga.Identite("G9", "a@exemple.fr", "A"))
    assert (user, refus) != (None, None), (
        "un compte désactivé est rendu comme « inconnu » : la personne sera routée "
        "vers l'inscription et obtiendra un second compte sur la même adresse")
    assert refus is not None and refus.raison == "google.account_inactive"


def test_an_unverified_local_account_is_never_linked(ga) -> None:
    """LA PRÉ-INSCRIPTION (*account pre-hijacking*).

    Un attaquant crée un compte mot de passe avec l'adresse de la victime AVANT
    qu'elle s'inscrive. Elle arrive par Google. Un système naïf lie son identité au
    compte de l'attaquant — qui garde un mot de passe valide dessus.

    `email_verified` de Google est nécessaire mais PAS suffisant : il faut que les
    deux côtés aient prouvé l'adresse.
    """
    db = _FauxDB(par_email=_ligne(verifie=False, sub=None))
    user, refus = ga.trouver_ou_refuser(db, ga.Identite("G1", "a@exemple.fr", "A"))
    assert user is None, "liaison sur un compte dont l'adresse n'est pas vérifiée"
    assert refus is not None and refus.raison == "google.unverified_local_account"
    assert not db.ecritures, "aucune écriture ne doit avoir eu lieu"


def test_a_verified_local_account_is_linked_once(ga) -> None:
    """LA RÉCIPROQUE : quand les deux côtés ont prouvé, la liaison a lieu.

    Et elle est CONDITIONNELLE en SQL (`AND google_sub IS NULL`) : deux onglets qui
    reviennent en même temps n'écrasent pas une liaison déjà posée.
    """
    db = _FauxDB(par_email=_ligne(verifie=True, sub=None))
    user, refus = ga.trouver_ou_refuser(db, ga.Identite("G1", "a@exemple.fr", "A"))
    assert refus is None and user is not None
    assert len(db.ecritures) == 1
    assert db.ecritures[0][1][0] == "G1"


def test_an_address_already_linked_to_another_google_account_is_refused(ga) -> None:
    """LA PRISE DE CONTRÔLE PAR LIAISON — trouvée par l'audit de sécurité.

    Un artiste a lié son compte Google `DEJA`. Quelqu'un se présente avec la même
    adresse mais un `sub` différent — un administrateur de domaine Workspace qui
    recrée l'adresse obtient exactement ça, avec `email_verified` vrai. Sans ce
    refus, la recherche par e-mail rendait la ligne de l'artiste et la session
    était hydratée pour l'arrivant.

    ⚠️ CE TEST REMPLACE UNE VÉRIFICATION TEXTUELLE qui cherchait la chaîne
    « google_sub IS NULL » dans le SQL. Elle passait sur le défaut : la clause
    ÉTAIT là, et elle ne servait à rien puisque `execute_query` ne rend aucun
    `rowcount` — un UPDATE qui ne touche aucune ligne se lit comme un succès. Un
    garde qui lit la FORME d'un remède plutôt que son EFFET est aveugle, et ce
    dépôt a une classe pour ça.
    """
    db = _FauxDB(par_email=_ligne(verifie=True, sub="DEJA"))
    user, refus = ga.trouver_ou_refuser(db, ga.Identite("AUTRE", "a@exemple.fr", "A"))
    assert user is None, (
        "une adresse déjà reliée à une AUTRE identité Google a été hydratée : "
        "prise de contrôle de compte")
    assert refus is not None
    assert refus.raison == "google.linked_to_another_google_account"
    assert not db.ecritures, "aucune écriture ne doit avoir eu lieu"


def test_the_same_google_account_coming_back_by_email_is_not_refused(ga) -> None:
    """LA RÉCIPROQUE — sinon le refus ci-dessus pourrait être inconditionnel.

    Le cas arrive : une ligne liée dont la recherche par `sub` échoue (base
    répliquée en retard, index reconstruit). Le même `sub` doit passer.
    """
    db = _FauxDB(par_email=_ligne(verifie=True, sub="G1"))
    user, refus = ga.trouver_ou_refuser(db, ga.Identite("G1", "a@exemple.fr", "A"))
    assert refus is None and user is not None, (
        "le MÊME compte Google, revenu par la recherche e-mail, a été refusé")


def test_the_stable_key_is_sub_and_not_the_email(ga) -> None:
    """Google le dit : `sub` est la clé, l'e-mail peut changer.

    Ici, la base contient un compte dont l'adresse a changé côté Google. La
    recherche par `sub` doit le retrouver — sinon l'artiste se verrait proposer de
    créer un second compte sur ses propres données.
    """
    db = _FauxDB(par_sub=_ligne(email="ancienne@exemple.fr", sub="G1"))
    user, refus = ga.trouver_ou_refuser(
        db, ga.Identite("G1", "nouvelle@exemple.fr", "A"))
    assert refus is None and user is not None and user["id"] == 7, (
        "la recherche par `sub` n'a pas retrouvé le compte : une adresse Google "
        "changée créerait un doublon sur les mêmes données")


# ══════════════════════════════════════════════════════════════════════════
# 3. LE SECOND FACTEUR, ET LA DÉCONNEXION
# ══════════════════════════════════════════════════════════════════════════

def test_the_google_path_defers_to_the_second_factor(ga) -> None:
    """CONTOURNEMENT DE 2FA — trou nº 1, le plus grave du design initial.

    Un compte avec `totp_enabled` entrait par Google sans jamais présenter son
    code. C'est exactement le trou que R26 a fermé côté mot de passe.

    Le contrôle est structurel, dans `auth.py` : le traitement du retour Google
    doit tester `totp_enabled` et poser `_totp_pending` AVANT toute hydratation.
    Un test de comportement demanderait de piloter un rerun Streamlit ; l'AST dit
    la même chose et ne peut pas être satisfait par accident.
    """
    src = (_SRC / "dashboard" / "auth.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef)
               and n.name == "_traiter_retour_google"), None)
    assert fn is not None, "`_traiter_retour_google` a disparu de `auth.py`"

    lignes_totp = [n.lineno for n in ast.walk(fn)
                   if isinstance(n, ast.Constant) and n.value == "totp_enabled"]
    lignes_hydrate = [n.lineno for n in ast.walk(fn)
                      if isinstance(n, ast.Call)
                      and getattr(n.func, "id", None) == "_hydrate_session"]
    assert lignes_totp, (
        "le retour Google ne consulte jamais `totp_enabled` : un compte protégé "
        "par un second facteur entre sans présenter son code.")
    assert lignes_hydrate, "le retour Google n'hydrate jamais — il ne connecte rien"
    assert min(lignes_totp) < min(lignes_hydrate), (
        "`totp_enabled` est consulté APRÈS l'hydratation : la session est déjà "
        "ouverte quand on se demande s'il fallait un second facteur.")


def test_logging_out_kills_both_authorities() -> None:
    """LES DEUX, et les modes de défaillance sont ASYMÉTRIQUES.

    * `session_state.clear()` seul est inoffensif : plus rien ne relit `st.user`.
    * `st.logout()` seul laisserait `authenticated=True`, et `require_login()`
      teste ça EN PREMIER sans consulter `st.user` — la personne croit être
      déconnectée et ne l'est pas. Une session fantôme.

    C'est le second qu'on garde ; le premier est cité pour que personne ne
    « corrige » l'ordre en croyant bien faire.
    """
    src = (_SRC / "dashboard" / "auth.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef)
               and n.name == "render_logout_footer"), None)
    assert fn is not None, "`render_logout_footer` a disparu"

    appelle_deconnecter = any(
        isinstance(n, ast.Call) and getattr(n.func, "id", None) == "deconnecter"
        for n in ast.walk(fn))
    vide_la_session = any(
        isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "clear"
        for n in ast.walk(fn))
    assert appelle_deconnecter, (
        "la déconnexion ne coupe pas l'identité Google : le cookie d'identité "
        "survit, et le bouton « Se connecter avec Google » reconnecte sans écran "
        "de consentement, sur un poste que la personne croyait quitté.")
    assert vide_la_session, (
        "la déconnexion ne vide plus `session_state` : `authenticated` resterait "
        "vrai et `require_login()` le teste en premier — session fantôme.")


# ══════════════════════════════════════════════════════════════════════════
# 4. L'ÉTAT INTERMÉDIAIRE
# ══════════════════════════════════════════════════════════════════════════

def test_a_pending_signup_expires(monkeypatch, ga) -> None:
    """R24 transposé : une autorisation lue une fois devient fausse avec le temps.

    Un onglet laissé ouvert après le retour de Google, repris le lendemain,
    créerait un compte sur un jeton que plus rien n'a revérifié — et Streamlit ne
    vérifie PAS l'expiration du jeton d'identité tout seul.
    """
    etat = {}
    monkeypatch.setattr(ga.st, "session_state", etat, raising=False)
    ga.memoriser_inscription(ga.Identite("G1", "a@exemple.fr", "A"))
    assert ga.inscription_en_cours() is not None, "elle devrait valoir tout de suite"

    # ⚠️ L'horloge réelle est capturée AVANT d'être remplacée. Le premier jet
    # écrivait `lambda: time.time() + TTL`, qui s'appelle lui-même : `RecursionError`
    # au lieu d'un verdict. Un test qui plante n'est pas un test qui échoue.
    plus_tard = time.time() + ga.INSCRIPTION_TTL_SECS + 1
    monkeypatch.setattr(time, "time", lambda: plus_tard)

    assert ga.inscription_en_cours() is None, (
        "un retour de Google vieux de plus de "
        f"{ga.INSCRIPTION_TTL_SECS} s crée encore un compte")
    assert "_google_inscription_en_cours" not in etat, (
        "l'état expiré n'est pas oublié : il repartirait au prochain passage")


def test_the_ttl_is_short_enough_to_mean_something(ga) -> None:
    """Un TTL d'un jour serait une absence de TTL écrite en chiffres."""
    assert 60 <= ga.INSCRIPTION_TTL_SECS <= 3600, (
        f"TTL de {ga.INSCRIPTION_TTL_SECS} s : hors de la plage qui a du sens "
        "(le temps de choisir un nom d'artiste, pas le temps d'oublier).")
