# Connexion Google — bilan de sécurité (R267, 2026-09-28)

Réponse aux trois questions de la note L138 : l'e-mail est-il toujours récupéré ? est-ce
plus sûr que le mot de passe ? quelles autres fonctions Google valent la peine ? Chaque
affirmation renvoie au code ou au test qui la prouve.

## 1. L'e-mail est-il toujours récupéré ?

Oui. Les scopes demandés sont `openid email profile` (`.streamlit/secrets.toml.example`,
section `[auth]`) : les scopes **non sensibles** de Google, qui ne déclenchent aucune
vérification d'application. Le jeton porte `email` et `email_verified`.

Mais l'e-mail n'est **pas** la clé : c'est `sub`, l'identifiant stable que Google
recommande, parce qu'une adresse Google peut changer. L'e-mail ne sert qu'à la première
liaison — `test_the_stable_key_is_sub_and_not_the_email`.

## 2. Plus sûr que le mot de passe ?

**Pour l'artiste qui l'utilise : oui, sur trois points.** Pas de mot de passe
streaMLytics à réutiliser ou à faire fuiter ; l'authentification forte de Google
(double facteur, détection de connexion suspecte) s'applique ; le formulaire de
connexion par mot de passe, et son limiteur, ne sont plus sa porte d'entrée.

**Pour le produit : aussi sûr, pas plus — et c'est voulu.** Google est une façon
SUPPLÉMENTAIRE d'hydrater la même session (`src/dashboard/utils/google_auth.py`, seul
lecteur de `st.user`), jamais une seconde autorité. Les quatre contrôles du chemin mot de
passe s'appliquent au chemin Google, chacun gardé par un test de
`tests/test_google_sign_in_refuses_what_the_password_path_refuses.py` :

| contrôle | test |
|---|---|
| e-mail vérifié par Google | `test_an_email_google_has_not_verified_is_refused` |
| compte actif | `test_a_deactivated_account_cannot_come_in_through_google` |
| second facteur (TOTP) non contourné | `test_the_google_path_defers_to_the_second_factor` |
| pas de liaison sur un compte local non vérifié (*account pre-hijacking*) | `test_an_unverified_local_account_is_never_linked` |
| une adresse déjà liée à un autre compte Google est refusée | `test_an_address_already_linked_to_another_google_account_is_refused` |
| la déconnexion tue les deux autorités | `test_logging_out_kills_both_authorities` |
| une inscription entamée expire (15 min) | `test_a_pending_signup_expires` |

**Le risque qui reste** est une dépendance : si le compte Google de l'artiste est
compromis, son compte streaMLytics l'est aussi — sauf s'il a activé le TOTP, que le
chemin Google respecte. C'est le même compromis que tout « Se connecter avec Google », et
il se dit à l'artiste, il ne se corrige pas dans le code.

## 3. D'autres fonctions Google ?

- **Google Analytics (GA4)** : prévu comme pixel de la page d'atterrissage (avec le
  pixel Meta), **clos par décision, non livré** — `archive.md`, « Pixel client sur la
  LANDING uniquement ». Il n'a rien à voir avec la connexion : il ne lit aucune donnée
  d'artiste.
- **YouTube Analytics** (abonnés au jour près) : il faut les scopes
  `yt-analytics.readonly` et `youtube.readonly`, **sensibles**, donc la vérification de
  l'application par Google (politique de confidentialité, domaine vérifié, vidéo). La
  procédure est dans `runbook-actions-utilisateur.md` ; tant qu'elle n'est pas faite, les
  jetons de rafraîchissement expirent en 7 jours. Ajouter ces scopes au bouton de connexion
  ferait basculer toute la connexion Google dans cette vérification — ils vivront dans un
  consentement séparé, au moment de connecter YouTube.

Rien d'autre n'est recommandé : chaque scope ajouté allonge l'examen de Google et élargit
ce qu'un jeton volé permet.
