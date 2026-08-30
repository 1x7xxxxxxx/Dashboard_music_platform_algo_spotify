# ADR-003 — React + FastAPI dashboard rewrite : considered, deferred

- **Status:** Deferred (not implemented)
- **Date:** 2026-05-14
- **Deciders:** @1x7xxxxxxx
- **Supersedes:** —
- **Related:** DEVLOG 2026-05-14 perf audit ; `.claude/dev-docs/roadmap/checklist.md` § P3 Performance dashboard

## Context

The dashboard is a Streamlit application (`src/dashboard/`, ~18 views, multi-tenant SaaS with auth + Stripe billing + 12 data sources). A static perf audit (2026-05-14) identified concrete bottlenecks (N+1 Airflow API calls, missing `@st.cache_data`, top-level plotly imports — all listed in roadmap § P3 Performance dashboard) that can be fixed in ~2 days of Python work for an estimated -50 % render time.

Beyond those incremental fixes, a question arose : would a **full rewrite to React + FastAPI + Next.js** be a better long-term bet ? Streamlit has structural limitations that no amount of caching can fix :

- Full-page re-render on every widget interaction (no real partial update outside `@st.fragment`)
- No native WebSocket / SSE → no real-time notifications
- Mobile experience is degraded (responsive but not touch-first)
- No SEO on public pages (the framework is not server-side-rendered for unauthenticated routes)
- Animations / micro-interactions feel "data-app", not "product"

These are framework limits, not implementation problems.

## Considered alternatives

### Option A — Stay on Streamlit + apply incremental perf fixes (P3 roadmap items)

- Effort : ~2 jours
- Gain : -50 % render time (from ~2-3 s to ~1-1.5 s)
- Risk : zero (changes are local + reversible)
- Ceiling : framework limits remain — won't help with mobile UX, SEO, or animations

### Option B — Full rewrite to React + FastAPI + Next.js

**Stack cible** :
- Frontend : Next.js 15 (App Router) + Tailwind + shadcn/ui
- Backend API : FastAPI existant (Brick 14, JWT auth déjà en place) — à étendre, pas à recréer
- Auth : NextAuth contre l'API JWT FastAPI
- State client : React Query (TanStack)
- Charts : Recharts (mieux pour React que Plotly)
- Conservé tel quel : DB PostgreSQL, Airflow DAGs, collectors Python, ML pipeline

**Effort** : 3-6 mois temps plein (1 dev senior). 18+ vues Streamlit → 18+ pages Next.js. Migration auth flow, billing UI, admin, onboarding wizard.

**Bénéfices** :
- ✅ UX fluide (pas de re-render global)
- ✅ Mobile-first
- ✅ SEO sur landing / pricing
- ✅ App-like feel, PWA possible
- ✅ Plus facile à embaucher (React >> Streamlit côté marché)

**Coûts** :
- ❌ 3-6 mois sans nouvelles features data
- ❌ Maintenance double codebase pendant la transition (Streamlit + Next.js cohabitent)
- ❌ Capitalisation perdue sur l'écosystème Streamlit (composants custom, theming, intégrations)
- ❌ Re-test complet de tous les flows (auth, Stripe webhooks, exports PDF/CSV)

## Decision

**Defer the rewrite.** Apply the 7 P3 perf items first (~2 jours) and revisit when at least one of these signals fires :

1. **Recurring user UX complaints** — feedback explicite d'artistes sur la lenteur perçue, le mobile, ou l'aspect "outil interne" de l'interface
2. **Need for WebSocket / SSE** — alerts push, notifications temps réel, collaboration multi-user
3. **SEO requirement on public pages** — landing + pricing à indexer (acquisition organique)
4. **Scaling beyond ~50 active artists** — où Streamlit commence à montrer ses limites de concurrence (chaque session = 1 process Python, RAM grimpe vite)

Aucun de ces 4 signaux n'est actif aujourd'hui (~5 artistes en pilote, zéro retour UX négatif documenté, aucune contrainte SEO).

### Signal review — 2026-08-30

The three signals were read against the product, not remembered. **None has fired.**

| Signal | State on 2026-08-30 |
|---|---|
| Recurring artist UX complaints (slowness, mobile, "internal tool" feel) | **None on slowness.** The ~30 field notes from the two beta artists (Benken 2026-06-19, GRiNCH 2026-08-12) were about *reachability* and *credentials* — a page outside the navigation, a wizard reachable only from an e-mail, an identity field missing from a form. Not one about speed. |
| WebSocket / SSE need | None. Alerts go out by e-mail, nightly. |
| SEO on public pages | The landing page is already planned **outside Streamlit** — a separate static site (roadmap section E), because Streamlit cannot host a tracking pixel either. So this signal is structurally routed around rather than pending. |

Two measurements this ADR did not have, both from the production container:

- **Server render p50 = 61 ms**, p95 = 378 ms, 33 of 42 views under 150 ms. Option A's
  premise ("incremental perf fixes are enough") held.
- **Delivery is not the bottleneck**: the Streamlit JS bundle is served from the
  Cloudflare edge cache (`cf-cache-status: HIT`, `immutable`, 1 year). A React bundle
  would be served the same way, from the same edge, for the same cost.

The slowest page left, `trigger_algo` at 662 ms, is slow for a reason a rewrite does
**not** address either: it builds 36 plotly figures per rerun because Streamlit
executes every tab body. The fix for that is lazy rendering within Streamlit, logged
as a standing condition in ADR-007 — not a framework change.

**Decision unchanged: defer.** Re-read this table when inviting the beta (R1), which
is the event most likely to make signal 1 fire — or to show that it does not.

## Consequences

**Short-term (next 1-3 months)** :
- Exécuter les 7 P3 perf items (roadmap § P3 Performance dashboard) lorsqu'on a 2 jours libres
- Continuer à shipper des features data sur Streamlit (workflow connu, vélocité élevée)
- Documenter les pain points UX au fur et à mesure (template : DEVLOG entries flaggées `ux:`)

**Long-term (when a trigger fires)** :
- Provisionner 3-6 mois full-time sur la réécriture
- Stratégie de migration recommandée : **gradual** plutôt que big-bang — exposer les nouvelles pages Next.js sous un autre sous-domaine (`app.streamlytics.io`) pendant que `dashboard.streamlytics.io` reste sur Streamlit. Migrer une vue à la fois, finir par sunset Streamlit
- Réutiliser le FastAPI existant (Brick 14) comme backend unique → pas de réécriture backend, juste extension des endpoints
- Garder cette ADR à jour : ajouter section "Trigger fired on YYYY-MM-DD" quand le moment vient

## Out of scope

- **Migration Hetzner** (`.claude/dev-docs/migration-hetzner.md`) : indépendante, peut se faire avant ou après cette décision
- **Refactoring Streamlit** (au-delà des P3 perf) : pas pertinent — soit on optimise dans Streamlit, soit on réécrit. Pas d'entre-deux qui en vaut la peine
