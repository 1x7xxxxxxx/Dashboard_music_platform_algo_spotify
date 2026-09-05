# ADR-017 — La demande de partenariat Meta est fermée par une capacité d'app

- **Date** : 2026-09-05
- **Statut** : Accepté (constat mesuré, à rouvrir si Meta accorde l'accès)
- **Ferme** : R62 pour sa moitié « envoi ». La moitié « détection » existait déjà.

## Le contexte

Pour collecter les chiffres Meta d'un artiste, son compte publicitaire doit nous être
partagé. C'est aujourd'hui un geste manuel dans *son* Business Manager, et il a bloqué
la session Benken du 2026-06-19. La demande était d'**envoyer la demande
automatiquement** à l'enregistrement, pour que l'artiste n'ait plus qu'à accepter.

## Ce qui a été mesuré, et non supposé

Le jeton System User **porte déjà** `business_management`, avec `ads_management`,
`ads_read` et `instagram_manage_insights`. Les arêtes de partenariat répondent **en
lecture** :

```
GET  212173878482503/owned_ad_accounts          → 3 comptes
GET  212173878482503/client_ad_accounts         → []   partages ACCEPTÉS
GET  212173878482503/pending_client_ad_accounts → []   demandes EN ATTENTE
```

**Les deux écritures sont refusées, et la même erreur pour les deux :**

```
POST 212173878482503/client_ad_accounts   → (#3) Application does not have
POST act_567214713853881/agencies         →      the capability to make this API call.
```

Le contrôle qui tranche : **une écriture Business ordinaire passe**
(`POST /212173878482503` avec `name` → `{"id": "212173878482503"}`). Ce n'est donc ni le
jeton, ni ses permissions, ni une panne : c'est une **capacité de l'application**, que
Meta accorde par une revue distincte de l'octroi des permissions.

## La décision

**On n'envoie pas la demande.** Le guide garde le geste manuel — qui, lui, fonctionne —
et l'app le rend aussi court que possible : un numéro à coller, `META_BUSINESS_ID`, dans
« Attribuer un partenaire ».

## Ce qu'on rejette

- **Contourner par le jeton d'un artiste** (flux OAuth Facebook Login). Cela déplacerait
  le modèle central (ADR-006) vers un jeton par locataire, avec sa péremption et son
  renouvellement — le problème que le System User a précisément supprimé.
- **Attendre la revue Meta avant de livrer le reste.** L'accès demandé est incertain et
  hors de notre calendrier.

## Ce qui existait déjà et qu'on ne réécrit pas

La **détection** est en place depuis le 2026-08 : `check_onboarding_readiness`
(`airflow/dags/alert_monitor.py`) sonde chaque nuit les plateformes rouges et écrit le
verdict dans `tenant_platform_probe`. Le jour où l'artiste accepte le partage, la sonde
suivante obtient 200 et la matrice passe au vert **sans qu'il re-teste**. Latence ≤ 24 h.

Bâtir un second mécanisme de détection aurait dupliqué celui-là.

## La règle d'expédition

Ce qui change avec cet ADR est le **vocabulaire**, pas la plomberie : l'état « ce compte
ne nous est pas encore partagé » (`SHARING_MISSING`) est désormais distinct de « ça ne
marche pas ». Un écran ne dit plus ❌ là où il y a un geste à faire.

## Rouvrir

Demander à Meta l'accès avancé « Business Asset Management » pour l'app
`ETL_DASHBOARD_SPOTIFY`. Le contrôle qui dit que c'est ouvert est exactement celui
ci-dessus : le `POST` cesse de répondre `(#3)`.

---

## Correction du 2026-09-05 (même jour) — deux affirmations non mesurées

Cet ADR concluait : « Le guide garde le geste manuel — **qui, lui, fonctionne** ». Cette
phrase n'a jamais été vérifiée. Elle est fausse deux fois, et l'artiste l'a rencontrée
dans l'heure qui a suivi.

**1. Le geste ne s'applique pas à un compte que nous possédons déjà.**

```
GET 212173878482503/owned_ad_accounts
  → 651785234086429, 567214713853881, 780537043765438
```

`567214713853881` est le compte du locataire 1. Meta **exclut du sélecteur de
partenaires le business qui possède déjà le compte** : coller `212173878482503` ne
pouvait rien trouver. La consigne était infaisable, et une installation qui marchait
paraissait cassée.

L'app affirmait « il faut partager » sans jamais lire l'état du partage — alors que les
trois arêtes qui le disent sont lisibles depuis le début et servaient déjà, dans ce même
ADR, à prouver autre chose. `src/utils/meta_partner.share_state()` les lit désormais :
`owned` / `accepted` / `pending` / `absent` / `unknown`, et le bloc ne parle que sur les
deux derniers. `unknown` n'est pas `absent` : une lecture ratée ne prouve aucune absence.

**2. Le chemin nommé n'était pas celui qui ajoute un partenaire.**

Le guide envoyait vers `settings/ad-accounts` → compte → onglet « Partenaires » →
« Attribuer un partenaire ». Cet écran **gère les attributions existantes** ; son champ
de recherche filtre cette liste. Le chemin canonique est `settings/partners` →
**Ajouter** → **Donner à un partenaire l'accès à tes assets** → coller le numéro →
cocher le compte → rôle Analyste.

Aucune URL ne peut pré-remplir cet écran : le paramètre `business_id` de Meta désigne le
business **du lecteur**, que nous ne connaissons pas. Le lien direct par compte, ajouté
quelques heures plus tôt, ouvrait donc précisément l'écran qui ne sert à rien.

**Ce que la moitié « détection » ne couvrait pas.** L'ADR disait la détection déjà faite
par la sonde nocturne. C'est vrai pour « le partage est-il arrivé ? » ; ce n'est pas vrai
pour « ce geste est-il seulement à faire ? ». La sonde regarde si l'appel passe, jamais
si la consigne s'adresse à quelqu'un.

Garde : `tests/test_the_share_step_is_hidden_when_there_is_nothing_to_share.py`.
