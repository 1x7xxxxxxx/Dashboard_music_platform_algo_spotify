#!/usr/bin/env python3
"""La concurrence RÉELLE du dashboard, mesurée par des navigateurs.

Type: Utility
Uses: playwright (dev only), un navigateur Chromium
Triggers: make loadtest-concurrency
Persists in: nothing

Pourquoi cet outil existe
-------------------------
Ce dépôt cite depuis trois mois un plafond de « ~46 puis ~55 utilisateurs actifs ».
**Ce nombre n'a jamais été observé.** Il est calculé — `1 / p50 × 0,7 × le temps de
lecture` — et `tools/loadtest_dashboard.py:27-40` dit lui-même pourquoi il ne peut pas
faire mieux : sous `AppTest`, un `st.write('hello')` passe de **352 ms à un fil à
2 144 ms à six**, plus un timeout. L'instrument se sature avant le sujet.

Mesurer vraiment la concurrence demande des clients qui parlent le websocket de
Streamlit. Le seul qui le parle sans que nous ayons à le réimplémenter est un
NAVIGATEUR. C'est tout ce que fait ce fichier : N onglets, un clic simultané, et le
temps que met chaque rerun à revenir.

Ce qui est dans le chiffre, et qu'il faut savoir avant de le lire
----------------------------------------------------------------
* **Le réseau et Cloudflare y sont**, puisqu'on tape l'URL publique. C'est assumé : le
  générateur ne vole alors aucun CPU au serveur mesuré, ce qui compte davantage. Et le
  signal recherché est la **FORME** — comment p50 se dégrade quand N monte — qui survit
  à une latence constante. Ne pas lire la valeur absolue comme un temps de rendu.
* **Le mode anonyme mesure la page de connexion**, plus légère qu'un tableau de bord.
  Le plafond qu'on en déduirait serait donc optimiste. Ce qu'il mesure honnêtement,
  c'est la **contention** : un processus, un GIL, N reruns qui se sérialisent.
* `--user/--password` mesure une vraie page de produit, et **écrit dans
  `usage_events`** : se connecter alors comme un locataire `is_sandbox`, que
  `tools/scale_check.sh` exclut déjà de la requête de seuil. Sans quoi la mesure
  déclencherait le seuil qu'elle sert à éclairer.

Ce qu'il ne fait pas
--------------------
Il ne conclut pas. Il rend un tableau. La décision sur les répliques et sur un magasin
partagé se prend ensuite, dans un ADR, avec ce tableau dedans.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Le même environnement que le dashboard et les DAGs, pas celui du shell qui lance.
# Exigé par `tests/test_a_tool_that_reads_the_env_loads_it.py`, et la raison vaut ici :
# `--user` / `--password` peuvent venir de `.env.local`, et un outil qui ne charge pas
# l'environnement du projet ne les verrait pas — il annoncerait « pas d'identifiants »
# alors qu'ils sont posés. C'est la forme « je n'ai pas pu demander » déguisée en
# « j'ai demandé », que cette séance a déjà payée deux fois.
from src.utils.env_files import load_project_env  # noqa: E402

load_project_env()

_MARKER = '[data-testid="stStatusWidget"]'
_APP = '[data-testid="stApp"]'


def _heavy_local_processes() -> int:
    """Combien de processus lourds tournent ICI — la mesure en dépend.

    Le 2026-09-15 ce dépôt a publié trois chiffres faux parce qu'ils avaient été pris
    pendant que trois sous-agents et un audit parcouraient le disque : facteur **12,8**
    d'erreur, et trois conclusions bâties dessus. Classe
    `a-measurement-taken-under-self-inflicted-load`.
    """
    try:
        out = subprocess.run(["ps", "-eo", "cmd"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return 0
    keys = ("pytest", "audit_runner", "playwright", "chromium", "node ")
    return sum(1 for line in out.stdout.splitlines() if any(k in line for k in keys))


async def _settle(page, timeout_ms: int) -> None:
    """Attend que l'application soit rendue et au repos."""
    await page.wait_for_selector(_APP, state="attached", timeout=timeout_ms)
    try:
        await page.wait_for_selector(_MARKER, state="detached", timeout=3000)
    except Exception:          # noqa: BLE001 — pas de rerun en cours : c'est l'état voulu
        pass


async def _one_rerun(page, selector: str, timeout_ms: int) -> float | None:
    """Un clic, puis le temps jusqu'à la fin du rerun. None si le marqueur n'est pas vu.

    **None n'est pas zéro.** Un outil qui rendrait 0 ms parce qu'il n'a rien vu
    fabriquerait exactement le nombre qu'on cherche à éviter.
    """
    target = page.locator(selector).first
    t0 = time.perf_counter()
    try:
        await target.click(timeout=timeout_ms)
        await page.wait_for_selector(_MARKER, state="attached", timeout=timeout_ms)
        await page.wait_for_selector(_MARKER, state="detached", timeout=timeout_ms)
    except Exception:          # noqa: BLE001 — un rerun perdu se compte, il ne s'invente pas
        return None
    return (time.perf_counter() - t0) * 1000.0


async def _level(browser, url: str, n: int, reps: int, selector: str,
                 timeout_ms: int, storage) -> tuple[list[float], int]:
    """N onglets, `reps` clics simultanés chacun. Rend (durées ms, reruns perdus)."""
    contexts = [await browser.new_context(storage_state=storage) for _ in range(n)]
    pages = []
    try:
        for ctx in contexts:
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await _settle(page, timeout_ms)
            pages.append(page)

        durations: list[float] = []
        lost = 0
        for _ in range(reps):
            # LE point de la mesure : les N clics partent ENSEMBLE. Séquentiellement,
            # on mesurerait N fois la latence d'un seul utilisateur.
            results = await asyncio.gather(
                *(_one_rerun(p, selector, timeout_ms) for p in pages))
            for r in results:
                if r is None:
                    lost += 1
                else:
                    durations.append(r)
        return durations, lost
    finally:
        for ctx in contexts:
            await ctx.close()


async def _login(browser, url: str, user: str, password: str, timeout_ms: int):
    """Une SEULE authentification, dont l'état est réutilisé par tous les onglets.

    Ce n'est pas une optimisation : `src/dashboard/utils/throttle.py:44-45` limite les
    tentatives de connexion à **30 par 900 s et par IP**. Une rampe qui se
    reconnecterait à chaque palier se ferait limiter, et mesurerait le limiteur.
    """
    ctx = await browser.new_context()
    page = await ctx.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    await _settle(page, timeout_ms)
    inputs = page.locator("input")
    await inputs.nth(0).fill(user)
    await inputs.nth(1).fill(password)
    await page.get_by_role("button", name="Se connecter").first.click(timeout=timeout_ms)
    await page.wait_for_timeout(4000)
    state = await ctx.storage_state()
    await ctx.close()
    return state


def _pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1)))))
    return ordered[k]


async def _run(args) -> int:
    from playwright.async_api import async_playwright

    levels = [int(x) for x in args.levels.split(",") if x.strip()]
    print(f"▶ {args.url}   paliers {levels}   {args.reps} clic(s) par onglet et par palier")
    print(f"  interaction : {args.selector}")
    print()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        storage = None
        try:
            if args.user:
                print("  authentification unique (état réutilisé par tous les onglets)…")
                storage = await _login(browser, args.url, args.user, args.password,
                                       args.timeout * 1000)

            rows = []
            base_p50 = None
            for n in levels:
                durations, lost = await _level(browser, args.url, n, args.reps,
                                               args.selector, args.timeout * 1000, storage)
                if not durations:
                    print(f"  ❌ palier {n} : AUCUN rerun mesuré ({lost} perdus). "
                          "Le marqueur n'est pas vu — l'instrument ne mesure rien, et "
                          "un tableau vide vaut mieux qu'un tableau faux.")
                    return 1
                p50, p95 = _pct(durations, 50), _pct(durations, 95)
                base_p50 = base_p50 or p50
                rows.append((n, p50, p95, max(durations), lost, p50 / base_p50))
                print(f"  {n:3d} onglet(s) → p50 {p50:7.0f} ms   p95 {p95:7.0f} ms   "
                      f"max {max(durations):7.0f} ms   perdus {lost}")

            print()
            print("| onglets | p50 (ms) | p95 (ms) | max (ms) | perdus | p50 / p50(1) |")
            print("|---|---|---|---|---|---|")
            for n, p50, p95, mx, lost, ratio in rows:
                print(f"| {n} | {p50:.0f} | {p95:.0f} | {mx:.0f} | {lost} | **×{ratio:.2f}** |")
            print()
            print("La colonne qui compte est la DERNIÈRE. Un processus unique sérialise "
                  "les reruns :\n"
                  "si p50 croît proportionnellement à N, la contention est totale ; s'il "
                  "reste plat,\nle service absorbe la concurrence. Le réseau est dans la "
                  "valeur absolue, pas dans\nle rapport.")
            return 0
        finally:
            await browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", default=os.getenv("LOADTEST_URL", "http://localhost:8501"))
    parser.add_argument("--levels", default="1,2,4,8,12,16",
                        help="nombre d'onglets simultanés, séparés par des virgules")
    parser.add_argument("--reps", type=int, default=5, help="clics par onglet et par palier")
    parser.add_argument("--selector", default='[data-testid="stBaseButton-secondary"]',
                        help="l'élément cliqué pour provoquer un rerun")
    parser.add_argument("--timeout", type=int, default=60, help="secondes")
    parser.add_argument("--user", default=os.getenv("LOADTEST_USER"))
    parser.add_argument("--password", default=os.getenv("LOADTEST_PASSWORD"))
    parser.add_argument("--force-busy", action="store_true",
                        help="mesurer même si la machine est occupée (les temps y sont du bruit)")
    args = parser.parse_args()

    heavy = _heavy_local_processes()
    if heavy > 2 and not args.force_busy:
        print(f"❌ {heavy} processus lourds tournent ici. Une mesure prise sous charge "
              "auto-infligée a déjà coûté un facteur 12,8 à ce dépôt.\n"
              "   Attendre, ou --force-busy en sachant ce qu'on lit.")
        return 1
    if args.user and not args.password:
        print("❌ --user sans --password")
        return 1
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
