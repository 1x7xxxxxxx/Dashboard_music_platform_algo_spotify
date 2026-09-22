"""La couture Google : le SEUL endroit du dépôt qui lit `st.user`.

Type: Core
Uses: streamlit (st.login / st.user / st.logout), src.dashboard.auth
Depends on: saas_users.google_sub (migration 135), .streamlit/secrets.toml [auth]
Triggers: src/dashboard/auth.py::require_login
Persists in: PostgreSQL spotify_etl (saas_users.google_sub, google_linked_at)

Le principe, et pourquoi il tient tout le fichier
--------------------------------------------------
Google devient une façon SUPPLÉMENTAIRE d'obtenir une session hydratée. Ce n'est
jamais un second système de session. `st.user` est lu ici et nulle part ailleurs ;
partout ailleurs l'autorité reste `st.session_state` et la ligne `saas_users`.

La raison est écrite dans ce dépôt, dans `auth.py:820-824` : « Two copies of this
precedence would drift towards billing a customer for premium while a nightly job
treats them as free. » Deux autorités de session dériveraient de la même façon, et
la dérive se lirait comme une session valide.

⚠️ Conséquence pratique : `st.user.is_logged_in` ne veut PAS dire « connecté à
streaMLytics ». Il veut dire « Google a reconnu quelqu'un ». Entre les deux il y a
quatre contrôles, et ils ont tous été trouvés manquants dans la première version du
design, par une critique menée AVANT écriture :

    1. `email_verified` du jeton — sinon la pré-inscription (voir plus bas)
    2. `active = TRUE` — sinon un compte désactivé par l'admin rentre quand même
    3. `totp_enabled` — sinon le second facteur est contourné
    4. `email_verified` DE NOTRE CÔTÉ avant toute liaison

Ce que ce module refuse de faire
---------------------------------
**Lier automatiquement sur un e-mail non vérifié.** L'attaque s'appelle
*account pre-hijacking* : un attaquant crée un compte mot de passe avec TON adresse
avant que tu ne t'inscrives ; tu arrives ensuite par « Se connecter avec Google » ;
un système naïf lie ton identité Google à SON compte, et il garde un mot de passe qui
y donne accès. Le claim `email_verified` de Google est nécessaire mais **pas
suffisant** — il faut que les deux côtés soient vérifiés.

**Utiliser l'e-mail comme clé.** Google dit d'utiliser `sub`, parce qu'une adresse
Google peut changer. L'e-mail ne sert qu'à la PREMIÈRE liaison.

**Créer un compte tout seul.** Une inscription pose des choses qu'un jeton d'identité
ne porte pas : le nom d'artiste, l'acceptation des CGU (obligation légale), le
consentement marketing, un éventuel code de parrainage. Le parcours passe donc par un
formulaire court, et par le MÊME `_create_artist_and_user()` que l'inscription
classique — pas par une seconde écriture qui divergerait.
"""
from __future__ import annotations

import time
from typing import NamedTuple

import streamlit as st

#: La durée de vie de l'état intermédiaire entre le retour de Google et la
#: soumission du formulaire court.
#:
#: ⚠️ Il en faut une, et ce dépôt sait pourquoi : R24 a mesuré qu'une autorisation
#: lue une fois et jamais revérifiée devient fausse avec le temps — c'est
#: `_REAUTH_INTERVAL_SECS` et `_IDLE_TIMEOUT_SECS` dans `auth.py`. Un onglet laissé
#: ouvert après le retour de Google, repris le lendemain, créerait un compte sur un
#: jeton d'identité que personne n'a revérifié. Streamlit, lui, ne vérifie PAS
#: l'expiration du jeton tout seul — c'est écrit dans sa propre documentation.
#:
#: Quinze minutes : le temps de choisir un nom d'artiste, pas le temps d'oublier.
INSCRIPTION_TTL_SECS = 15 * 60

#: La clé de l'état intermédiaire dans `session_state`.
_CLE_INSCRIPTION = "_google_inscription_en_cours"


class Identite(NamedTuple):
    """Ce qu'on retient du jeton d'identité. Rien de plus."""

    sub: str
    email: str
    nom: str


class Refus(NamedTuple):
    """Un refus NOMMÉ. Jamais un `None` silencieux.

    `raison` est une clé i18n, `defaut` le texte français. Un refus qui ne dit pas
    pourquoi envoie l'utilisateur réessayer la même chose — et ce dépôt a une règle
    transverse là-dessus : « une lecture qui échoue ne se déguise pas en rien à
    lire ».
    """

    raison: str
    defaut: str


def configure() -> bool:
    """La connexion Google est-elle configurée sur cette instance ?

    Lue depuis les secrets, jamais supposée. Sans `[auth]` dans
    `.streamlit/secrets.toml`, `st.login()` lève — afficher le bouton quand même
    offrirait un chemin qui plante, ce qui est pire qu'un bouton absent. C'est la
    même doctrine que le bouton de rendez-vous sans lien (`views/service.py`).
    """
    try:
        auth = st.secrets.get("auth")
    except Exception:      # noqa: BLE001 — pas de fichier de secrets du tout
        return False
    if not auth:
        return False
    return bool(auth.get("client_id") and auth.get("redirect_uri"))


def identite_courante() -> Identite | Refus | None:
    """L'identité Google de la session, ou un refus, ou `None` si personne.

    ⚠️ C'est LA fonction qui lit `st.user`, et la seule. Un garde le vérifie :
    `tests/test_google_identity_is_read_at_exactly_one_seam.py`.
    """
    try:
        if not st.user.is_logged_in:
            return None
    except Exception:      # noqa: BLE001 — `[auth]` absent : st.user lève
        return None

    sub = _claim("sub")
    email = (_claim("email") or "").strip().lower()

    # Le claim, pas une supposition. Google peut rendre une adresse NON vérifiée —
    # typiquement sur certains comptes Workspace — et la traiter comme vérifiée est
    # exactement ce qui ouvre la pré-inscription.
    verifie = st.user.get("email_verified") if hasattr(st.user, "get") else None
    if verifie is not True:
        return Refus(
            "google.email_not_verified",
            "Google n'a pas confirmé cette adresse e-mail. Vérifie-la dans ton "
            "compte Google, puis réessaie — ou connecte-toi avec un mot de passe.")

    if not sub or not email:
        return Refus(
            "google.incomplete_token",
            "Google n'a pas renvoyé assez d'informations pour te connecter. "
            "Réessaie, ou utilise un mot de passe.")

    return Identite(sub=sub, email=email, nom=(_claim("name") or "").strip())


def _claim(nom: str):
    """Un claim du jeton, ou `None`. `st.user` est dict-like, pas un dict."""
    try:
        return st.user.get(nom) if hasattr(st.user, "get") else getattr(st.user, nom)
    except Exception:      # noqa: BLE001 — claim absent
        return None


def trouver_ou_refuser(db, ident: Identite) -> tuple[dict | None, Refus | None]:
    """La ligne `saas_users` correspondante, ou un refus, ou (None, None) = inconnu.

    (None, None) n'est PAS une erreur : c'est « cette personne n'a pas de compte »,
    donc une inscription et non une connexion. Le distinguer d'un refus est ce qui
    empêche un compte désactivé de retomber dans le parcours d'inscription et d'y
    obtenir un second compte sur la même adresse.

    Les quatre contrôles, dans l'ordre où ils doivent tomber :

    1. Recherche par `google_sub` — la clé stable, et le cas de tous les retours.
    2. Sinon recherche par e-mail, pour la PREMIÈRE liaison seulement.
    3. Un compte trouvé mais `active = FALSE` → refus nommé, jamais un silence.
    4. Une liaison n'a lieu que si NOTRE `email_verified` est vrai aussi.
    """
    colonnes = ("id, username, email, password_hash, artist_id, role, "
                "email_verified, totp_enabled, totp_secret, active, google_sub")

    rows = db.fetch_query(
        f"SELECT {colonnes} FROM saas_users WHERE google_sub = %s LIMIT 1",
        (ident.sub,))
    if rows:
        user = _en_dict(rows[0])
        if not user["active"]:
            return None, _refus_inactif()
        return user, None

    rows = db.fetch_query(
        f"SELECT {colonnes} FROM saas_users WHERE LOWER(email) = LOWER(%s) LIMIT 1",
        (ident.email,))
    if not rows:
        return None, None       # inconnu → inscription

    user = _en_dict(rows[0])

    # ⚠️ Le contrôle `active` vient AVANT celui de la vérification, et l'ordre compte :
    # un compte désactivé dont l'e-mail n'est pas vérifié doit dire « désactivé », pas
    # « vérifie ton adresse ». Le second message enverrait quelqu'un tourner en rond
    # sur un compte qu'un humain a fermé exprès.
    if not user["active"]:
        return None, _refus_inactif()

    if not user["email_verified"]:
        # LE BLOCAGE DE LA PRÉ-INSCRIPTION. Ce compte porte l'adresse mais personne
        # n'a jamais prouvé la posséder — il a pu être créé par quelqu'un d'autre
        # avant l'arrivée du propriétaire légitime. Le lier donnerait à son créateur
        # un mot de passe valide sur les données de l'arrivant.
        return None, Refus(
            "google.unverified_local_account",
            "Un compte existe déjà avec cette adresse, mais elle n'a jamais été "
            "vérifiée. Ouvre le lien de vérification reçu par e-mail, ou connecte-toi "
            "avec ton mot de passe — ensuite la connexion Google marchera.")

    # ⚠️ LA PRISE DE CONTRÔLE PAR LIAISON — trouvée par l'audit de sécurité, dans
    # la première version de CETTE fonction, le 2026-09-22.
    #
    # Le `AND google_sub IS NULL` de l'UPDATE ci-dessous était censé empêcher
    # d'écraser une liaison existante. Il ne le peut pas : `execute_query` rend
    # `None` — il n'expose aucun `rowcount` (`postgres_handler.py:443`) — donc un
    # UPDATE qui ne touche AUCUNE ligne est indiscernable d'un UPDATE réussi, et la
    # fonction rendait `user` quand même. Le compte était hydraté.
    #
    # Le scénario, et il n'est pas théorique : un artiste s'inscrit avec
    # `contact@son-label.fr`, vérifie l'adresse, lie son compte Google A. Un
    # administrateur du domaine Workspace recrée cette même adresse — Google rend
    # alors un `sub` B, et `email_verified` vrai. La recherche par B ne trouve rien,
    # la recherche par e-mail trouve la ligne de l'artiste, l'UPDATE ne touche rien,
    # et le porteur de B entrait sur les données de l'artiste.
    #
    # C'est exactement le danger que l'en-tête de la migration 135 cite pour
    # justifier de clé sur `sub` — et la fonction le rouvrait par l'autre bout.
    #
    # Le contrôle est fait EN PYTHON, sur une valeur qu'on a lue, et non délégué à
    # une clause SQL dont on ne peut pas observer l'effet. Un garde qui dépend d'un
    # résultat qu'on ne regarde pas n'est pas un garde.
    if user["google_sub"] and user["google_sub"] != ident.sub:
        return None, Refus(
            "google.linked_to_another_google_account",
            "Cette adresse est déjà reliée à un autre compte Google. Connecte-toi "
            "avec ton mot de passe, ou écris-nous.")

    # Première liaison : les deux côtés ont prouvé l'adresse, et aucune autre
    # identité Google ne la revendique.
    db.execute_query(
        "UPDATE saas_users SET google_sub = %s, google_linked_at = NOW() "
        "WHERE id = %s AND google_sub IS NULL",
        (ident.sub, user["id"]))
    user["google_sub"] = ident.sub
    return user, None


def _refus_inactif() -> Refus:
    return Refus(
        "google.account_inactive",
        "Cet accès a été désactivé. Écris-nous si c'est une erreur.")


def _en_dict(row) -> dict:
    """La ligne en dictionnaire, aux noms que `_hydrate_session` attend."""
    return {
        "id": row[0], "username": row[1], "email": row[2],
        "password_hash": row[3], "artist_id": row[4], "role": row[5],
        "email_verified": row[6], "totp_enabled": row[7], "totp_secret": row[8],
        "active": row[9], "google_sub": row[10],
    }


# ── L'état intermédiaire de l'inscription ────────────────────────────────────

def memoriser_inscription(ident: Identite) -> None:
    """Retient l'identité le temps du formulaire court, avec son échéance."""
    st.session_state[_CLE_INSCRIPTION] = {
        "sub": ident.sub, "email": ident.email, "nom": ident.nom,
        "expire_a": time.time() + INSCRIPTION_TTL_SECS,
    }


def inscription_en_cours() -> Identite | None:
    """L'identité mémorisée, si elle n'a pas expiré. Sinon `None`, et on oublie.

    L'expiration est vérifiée à la LECTURE et non par une minuterie : rien ne tourne
    en arrière-plan dans une session Streamlit, et un état qui n'expire que quand on
    y pense n'expire pas.
    """
    etat = st.session_state.get(_CLE_INSCRIPTION)
    if not isinstance(etat, dict):
        return None
    if time.time() > etat.get("expire_a", 0):
        st.session_state.pop(_CLE_INSCRIPTION, None)
        return None
    return Identite(sub=etat["sub"], email=etat["email"], nom=etat["nom"])


def oublier_inscription() -> None:
    st.session_state.pop(_CLE_INSCRIPTION, None)


def deconnecter() -> None:
    """La déconnexion Google, à appeler AVEC `session_state.clear()`.

    ⚠️ Les deux modes de défaillance sont ASYMÉTRIQUES, et c'est pour ça que cette
    fonction existe plutôt qu'un appel nu :

    * n'appeler que `session_state.clear()` (le code d'avant le 2026-09-22) est
      inoffensif : plus rien ne relit `st.user`, donc la session applicative est bien
      morte, même si le cookie d'identité de Google survit côté navigateur ;
    * n'appeler que `st.logout()` laisserait `authenticated=True` intact, et
      `require_login()` teste ça EN PREMIER sans jamais consulter `st.user` : la
      personne croit être déconnectée et ne l'est pas.

    Le second est une session fantôme. On appelle donc les deux, et un garde exige
    que les deux soient là.
    """
    try:
        if st.user.is_logged_in:
            st.logout()
    except Exception:      # noqa: BLE001 — `[auth]` absent : rien à déconnecter
        pass
