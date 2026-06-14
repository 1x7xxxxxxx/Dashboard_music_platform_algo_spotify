# Cloudflare — débloquer les webhooks Stripe (plan Free)

**Type:** Utility (runbook ops). **Depends on:** Cloudflare zone `streamlytics.fr`,
prod Hetzner `167.233.92.1`. **Triggers:** à appliquer dès qu'un fix Cloudflare
bot-protection est requis.

## Problème

Cloudflare **Bot Fight Mode** (+ AI Labyrinth, activés 2026-06-13/14) renvoie un
**403 `cf-mitigated: challenge`** ("Just a moment") à tout client **non-navigateur**.
Or les **webhooks Stripe** sont des requêtes serveur-à-serveur (pas de navigateur,
pas de JS) → ils ne peuvent pas résoudre le challenge → la notification de paiement
**n'atteint jamais** `api.streamlytics.fr/webhooks/stripe`.

Preuve live (2026-06-14) :
- `POST /webhooks/stripe` **via Cloudflare** → `403` (challenge)
- `POST /webhooks/stripe` **direct origin** (loopback) → `400` (signature invalide = OK, l'app marche)

Conséquence : `checkout.session.completed`, `customer.subscription.updated/deleted`,
`invoice.payment_failed` ne se synchronisent plus → tier d'abonnement faux. Stripe
retente ~3 j puis **désactive l'endpoint**.

> **Contrainte** : on ne peut PAS passer `api.*` en grey-cloud (DNS-only) — le
> firewall origine (ufw) n'autorise QUE les IP Cloudflare. Passer hors-proxy
> rendrait l'API injoignable. Le fix doit donc être **côté Cloudflare**.

## Fix recommandé (Free) — IP Access Rules "Allow" pour Stripe

Une IP en liste blanche (Allow) **bypasse Bot Fight Mode** tout en gardant la
protection bot + AI Labyrinth pour tout le reste. Disponible sur le plan Free.

**Cloudflare → `streamlytics.fr` → Security → WAF → onglet "Tools" (IP Access Rules)**
→ pour chaque IP : *Action* = `Allow`, *Zone* = `streamlytics.fr` → Add.

### IP des notifications webhook Stripe (source : https://docs.stripe.com/ips, capturé 2026-06-14)

```
3.18.12.63
3.130.192.231
13.235.14.237
13.235.122.149
18.211.135.69
35.154.171.200
52.15.183.38
54.88.130.119
54.88.130.237
54.187.174.169
54.187.205.235
54.187.216.72
35.157.207.129
3.69.109.8
3.120.168.93
```

(15 IP. Téléchargeables : https://stripe.com/files/ips/ips_webhooks.txt)

> ⚠️ Stripe donne un **préavis de 7 jours** avant tout changement d'IP, via la
> *API announce mailing list*. S'y abonner, ou re-vérifier cette liste
> périodiquement. Si un jour les webhooks re-403, c'est la 1ʳᵉ chose à recontrôler.

## Alternative simple (1 clic) — désactiver Bot Fight Mode

**Cloudflare → Security → Bots → "Bot Fight Mode" OFF.** Débloque tout d'un coup.
Inconvénients : (1) plus de protection bot sur le dashboard — acceptable car l'app
a son propre lockout brute-force + rate-limit ; (2) **peut désactiver l'AI
Labyrinth** (lié à la détection bot). → Préférer la liste blanche IP ci-dessus.

## Vérification

1. Côté Stripe : **Developers → Webhooks → endpoint → Recent deliveries** — les
   livraisons doivent passer (200) ; chercher les 403 récents = events perdus.
2. Côté serveur (re-test) :
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" \
     -d '{}' https://api.streamlytics.fr/webhooks/stripe
   # attendu APRÈS fix : 400 (signature invalide), PLUS 403
   ```

## Note API REST

`POST /auth/token` et le reste de l'API sont aussi 403'és via CF (clients
programmatiques = non-navigateur). Non bloquant tant que l'API n'est consommée que
par le dashboard (navigateur). Si un client M2M externe en a besoin : allowlister
son IP de la même façon, ou utiliser l'alternative Bot Fight Mode OFF.
