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
