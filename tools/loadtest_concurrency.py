#!/usr/bin/env python3
"""La concurrence RÉELLE du dashboard, mesurée par des navigateurs.

Type: Utility
Uses: playwright (dev only), un navigateur Chromium, psutil
Triggers: make loadtest-concurrency
Persists in: un JSON par palier, écrit AU FIL DE L'EAU (--out)

Pourquoi cet outil existe
-------------------------
Mesurer la concurrence demande des clients qui parlent le websocket de Streamlit. Le seul
qui le parle sans qu'on ait à le réimplémenter est un NAVIGATEUR. C'est tout ce que fait
ce fichier : N onglets, un clic simultané, et le temps que met chaque rerun à revenir.

`tools/loadtest_dashboard.py` ne peut pas faire mieux : sous `AppTest`, un
`st.write('hello')` passe de **352 ms à un fil à 2 144 ms à six**. L'instrument s'y
sature avant le sujet. (⚠️ Ce plancher de 352 ms est aussi ce qui a produit le « facteur
8 » faux entre chrome et vue — il n'avait jamais été soustrait. Voir l'addendum d'ADR-026.)

Ce qui a été RÉPARÉ le 2026-09-16 (R119), et pourquoi
------------------------------------------------------
La version d'avant rendait une colonne « reruns perdus » qui a servi de signal de
décision à R114, et **elle ne tenait pas**. Quatre défauts cumulables, tous corrigés ici :

1. **Le marqueur n'était pas spécifique aux reruns.** Il guettait
   `[data-testid="stStatusWidget"]`, que Streamlit monte aussi pour l'invite « File
   change » et pour `stConnectionStatus`. Un websocket dégradé laissait le nœud attaché,
   l'attente de détachement expirait, et le rerun était compté « perdu » **alors qu'il
   avait pu être servi**. La colonne mélangeait le rendu et le transport.

   Le remplaçant est vérifié dans le frontend livré (Streamlit 1.63) : l'élément
   `[data-testid="stApp"]` porte DEUX attributs distincts, et la distinction est
   exactement celle qui manquait —
   * `data-test-script-state` ∈ {`initial`, `notRunning`, `running`, `rerunRequested`,
     `stopRequested`, `compilationError`} : **le rerun** ;
   * `data-test-connection-state` : **le transport**, séparément.

2. **Un `except Exception` nu fusionnait trois causes.** Elles sont maintenant comptées
   séparément, et une seule parle du serveur :
   * `click_failed` — le clic n'est jamais devenu actionnable : DÉFAUT CLIENT ;
   * `never_started` — l'état n'a jamais quitté `notRunning` : le clic n'a pas déclenché
     de rerun, ou le transport l'a perdu. L'état de connexion est relevé pour trancher ;
   * `never_finished` — l'état est resté `running` jusqu'au bout du délai : **c'est le
     seul signal serveur**, et c'est celui qu'on cherchait depuis le début ;
   * `app_error` — `compilationError` : l'application a levé, ce n'est pas de la lenteur.

3. **Le p50 était calculé sur les SURVIVANTS.** À 24 onglets, 68 à 82 % des échantillons
   étaient censurés : le chiffre publié décrivait le quart qui avait réussi et
   **sous-estimait** la dégradation. Le taux de censure est désormais publié à côté, et
   au-delà de 20 % le rapport est marqué comme une **BORNE INFÉRIEURE**, jamais comme une
   mesure.

4. **Le compte n'était pas monotone** — 9 (N=8) → 33 (N=12) → **24** (N=16) → 98 (N=24).
   Aucune saturation serveur ne produit cette inversion, et la cause probable est le
   client : 175-217 Mo par `chrome-headless-shell`, donc 24 onglets ≈ 4,2 Go contre
   ~4,0 Go disponibles. La RAM du navigateur est donc mesurée **à chaque palier**, et le
   palier est refusé si elle franchit le seuil.

Et les mesures sont écrites **par palier, au fil de l'eau** : deux passes sur quatre sont
mortes en emportant toute la série. Un fichier par palier survit à l'interruption.

Ce qui est dans le chiffre, et qu'il faut savoir avant de le lire
----------------------------------------------------------------
* **Le réseau et Cloudflare y sont**, puisqu'on tape l'URL publique. C'est assumé : le
  générateur ne vole alors aucun CPU au serveur mesuré. Le signal recherché est la
  **FORME** — comment p50 se dégrade quand N monte — qui survit à une latence constante.
* **Le mode anonyme mesure la page de connexion**, plus légère qu'un tableau de bord. Ce
  qu'il mesure honnêtement, c'est la **contention** : un processus, un GIL, N reruns qui
  se sérialisent.
* `--user/--password` mesure une vraie page et **écrit dans `usage_events`** : se
  connecter comme un locataire `is_sandbox`, que `tools/scale_check.sh` exclut déjà.

Ce qu'il ne fait pas
--------------------
Il ne conclut pas. Il rend un tableau. **Et depuis R115 il n'est plus le seul témoin** :
l'histogramme serveur `streamlytics_rerun_duration_seconds` mesure la même chose sans
client. Croiser les deux est le seul moyen de dire si un rerun perdu est un défaut du
serveur ou de l'instrument — c'était tout le point.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Le même environnement que le dashboard et les DAGs, pas celui du shell qui lance.
# Exigé par `tests/test_a_tool_that_reads_the_env_loads_it.py` : `--user` / `--password`
# peuvent venir de `.env.local`, et un outil qui ne charge pas l'environnement du projet
# annoncerait « pas d'identifiants » alors qu'ils sont posés.
from src.utils.env_files import load_project_env  # noqa: E402

load_project_env()

_APP = '[data-testid="stApp"]'
_SCRIPT_STATE = "data-test-script-state"
_CONN_STATE = "data-test-connection-state"

# Les états où le script TOURNE. Relevés dans le frontend livré (1.63) :
#   NOT_RUNNING=notRunning  RUNNING=running  RERUN_REQUESTED=rerunRequested
#   STOP_REQUESTED=stopRequested  COMPILATION_ERROR=compilationError
# et `initial` quand `scriptRunId` vaut `<null>`.
_BUSY = ("running", "rerunRequested")
_IDLE = ("notRunning", "initial")
_ERROR = "compilationError"

# Les quatre issues possibles d'un rerun. UNE SEULE parle du serveur.
_OUTCOMES = ("ok", "click_failed", "never_started", "never_finished", "app_error")


def _heavy_local_processes(exclude_own_browser: bool = False) -> int | None:
    """Combien de processus lourds tournent ICI — la mesure en dépend.

    Le 2026-09-15 ce dépôt a publié trois chiffres faux parce qu'ils avaient été pris
    pendant que trois sous-agents et un audit parcouraient le disque : facteur **12,8**
    d'erreur. Classe `a-measurement-taken-under-self-inflicted-load`.

    ⚠️ `exclude_own_browser` corrige un défaut de la version d'avant : elle comptait
    `chromium` parmi ses clés, c'est-à-dire **ce qu'elle crée elle-même**. Rejouée en
    cours de mesure, elle se serait toujours trouvée trop chargée.
    """
    keys = ("pytest", "audit_runner")
    if not exclude_own_browser:
        keys += ("playwright", "chromium", "node ")
    try:
        out = subprocess.run(["ps", "-eo", "cmd"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None            # inconnu, pas « aucun » — voir `_local_load`
    return sum(1 for line in out.stdout.splitlines() if any(k in line for k in keys))


def _local_load() -> tuple[float, float] | None:
    """(charge 1 min normalisée par cœur, %CPU cumulé des processus lourds).

    ⚠️ Ajouté le 2026-09-17, et c'est un correctif de GARDE, pas un assouplissement.
    `_heavy_local_processes` compte des NOMS. Sa clé `"node "` attrape les processus
    du serveur VS Code — neuf ici — donc un développeur qui lance cette mesure depuis
    le terminal de son éditeur est refusé **par construction**, machine au repos ou non.

    Mesuré ce jour-là au moment du refus : charge **1,02 sur 8 cœurs (13 %)**, et les
    douze « lourds » consommaient **5,1 % de CPU à eux tous**. Le garde a bloqué une
    mesure sur une machine objectivement inactive. Famille
    `un-contrôle-qui-ne-peut-jamais-passer`.

    Ce qu'on garde de l'ancien : la LISTE, qui dit *quoi* regarder. Ce qu'on remplace :
    le verdict, qui devient la charge réelle au lieu d'un compte de présences.
    """
    try:
        with open("/proc/loadavg", encoding="utf-8") as fh:
            one_min = float(fh.read().split()[0])
        cores = os.cpu_count() or 1
        out = subprocess.run(["ps", "-eo", "pcpu,cmd"], capture_output=True,
                             text=True, timeout=10)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        # UNE EXPIRATION N'EST PAS UNE MACHINE INACTIVE (corrigé le 2026-09-18).
        #
        # `return (0.0, 0.0)` faisait dire au garde « charge 0.00/cœur — mesure
        # autorisée » alors qu'on venait seulement de CESSER D'ATTENDRE `ps`. Or un
        # `ps` qui met plus de dix secondes est précisément le symptôme d'une machine
        # chargée : le seul cas où la lecture échoue est celui où son verdict aurait
        # dû être « non ». Le défaut se déclenchait donc exactement quand il coûtait.
        #
        # On rend `None`, que l'appelant lit comme INCONNU et refuse — la direction
        # prudente. C'est `a-timeout-reported-as-a-missing-thing`, dans le fichier qui
        # porte déjà `a-measurement-taken-under-self-inflicted-load` : même cause,
        # deux classes.
        return None
    keys = ("pytest", "audit_runner", "playwright", "chromium")
    cpu = 0.0
    for line in out.stdout.splitlines()[1:]:
        pcpu, _, cmd = line.strip().partition(" ")
        if any(k in cmd for k in keys):
            try:
                cpu += float(pcpu)
            except ValueError:
                continue
    return (one_min / cores, cpu)


def _browser_rss_mb() -> float | None:
    """La RAM résidente de NOS processus de navigateur, en Mo. 0 si illisible.

    C'est la grandeur qui explique le compte non monotone de la version d'avant :
    175-217 Mo par `chrome-headless-shell`, donc 24 onglets tiennent mal dans 4 Go. Un
    client qui manque de mémoire produit des « reruns perdus » qui ne parlent que de lui.
    """
    try:
        out = subprocess.run(
            ["ps", "-eo", "rss,cmd"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None            # inconnu, pas « zéro octet » — voir `_local_load`
    total_kb = 0
    for line in out.stdout.splitlines()[1:]:
        rss, _, cmd = line.strip().partition(" ")
        if "chrome" in cmd or "chromium" in cmd:
            try:
                total_kb += int(rss)
            except ValueError:
                continue
    return total_kb / 1024.0


def _available_mb() -> float:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


async def _settle(page, timeout_ms: int) -> None:
    """Attend que l'application soit rendue ET au repos, par l'état du script."""
    await page.wait_for_selector(_APP, state="attached", timeout=timeout_ms)
    try:
        await page.wait_for_function(
            f'''() => {{
                const a = document.querySelector('{_APP}');
                return a && {json.dumps(_IDLE)}.includes(a.getAttribute('{_SCRIPT_STATE}'));
            }}''',
            timeout=min(timeout_ms, 15000))
    except Exception:          # noqa: BLE001 — déjà au repos, ou état absent : c'est le but
        pass


async def _read_state(page) -> tuple[str, str]:
    """(état du script, état de la connexion). ('?', '?') si illisible.

    Les DEUX, toujours ensemble : c'est leur confusion qui a produit une colonne de
    décision fausse, et les lire séparément est la correction.
    """
    try:
        return await page.evaluate(
            f'''() => {{
                const a = document.querySelector('{_APP}');
                return a ? [a.getAttribute('{_SCRIPT_STATE}') || '?',
                            a.getAttribute('{_CONN_STATE}') || '?'] : ['?', '?'];
            }}''')
    except Exception:          # noqa: BLE001
        return ("?", "?")


async def _one_rerun(page, selector: str, timeout_ms: int) -> tuple[str, float | None, str]:
    """Un clic, puis le temps du rerun. Rend (issue, durée ms ou None, état de connexion).

    **`None` n'est pas zéro**, et l'issue n'est jamais « perdu » tout court : un outil qui
    rendrait 0 ms parce qu'il n'a rien vu fabriquerait exactement le nombre qu'on cherche
    à éviter, et une catégorie fourre-tout empêche de savoir QUI a échoué.
    """
    def _js(states: tuple[str, ...]) -> str:
        return f'''() => {{
            const a = document.querySelector('{_APP}');
            if (!a) return false;
            return {json.dumps(list(states))}.includes(a.getAttribute('{_SCRIPT_STATE}'));
        }}'''

    target = page.locator(selector).first
    try:
        await target.click(timeout=timeout_ms)
    except Exception:          # noqa: BLE001 — le clic n'est jamais devenu actionnable
        _, conn = await _read_state(page)
        return ("click_failed", None, conn)

    t0 = time.perf_counter()
    try:
        # 1) le rerun a-t-il COMMENCÉ ? Court, à dessein : si le script ne part pas en
        #    quelques secondes, ce n'est pas de la lenteur serveur, c'est une perte.
        await page.wait_for_function(_js(_BUSY + (_ERROR,)), timeout=min(timeout_ms, 10000))
    except Exception:          # noqa: BLE001
        _, conn = await _read_state(page)
        return ("never_started", None, conn)

    script_state, conn = await _read_state(page)
    if script_state == _ERROR:
        return ("app_error", None, conn)

    try:
        # 2) a-t-il FINI ? C'est ici, et seulement ici, que le serveur est en cause.
        await page.wait_for_function(_js(_IDLE), timeout=timeout_ms)
    except Exception:          # noqa: BLE001
        _, conn = await _read_state(page)
        return ("never_finished", None, conn)

    return ("ok", (time.perf_counter() - t0) * 1000.0, conn)


async def _level(browser, url: str, n: int, reps: int, selector: str,
                 timeout_ms: int, creds: tuple[str, str] | None = None) -> dict:
    """N onglets, `reps` clics simultanés chacun. Rend un relevé complet du palier.

    `creds` est `(identifiant, mot de passe)` quand on mesure connecté : CHAQUE onglet
    ouvre alors son propre contexte et s'authentifie, parce que la session ne survit pas
    à un onglet neuf. Sans `creds`, on reste anonyme et rien n'est à partager.
    """
    # ⚠️ UNE CONNEXION PAR ONGLET, et ce n'est pas un choix de confort — mesuré le
    # 2026-09-17. L'authentification NE SURVIT PAS à un nouvel onglet : le bocal à
    # cookies d'un contexte authentifié ne porte que `_streamlit_xsrf` et
    # `cf_clearance`, jamais `music_dashboard`. Un onglet neuf — même dans le MÊME
    # contexte — réaffiche le formulaire de connexion.
    #
    # Conséquence : la promesse d'origine (« une seule authentification, réutilisée par
    # tous les onglets ») était irréalisable, et le mode authentifié mesurait en fait
    # des rendus ANONYMES sur la page de connexion, que la couture de métriques
    # n'observe pas. 402 clics « authentifiés » avaient produit 10 reruns serveur.
    #
    # Le prix : `src/dashboard/utils/throttle.py` limite à **30 tentatives / 900 s et
    # par IP**, seau PARTAGÉ entre instances depuis la migration 122. Une rampe complète
    # (1+2+4+8+12+16+24 = 67 connexions) mesurerait le limiteur. `--levels 1,2,4,8` en
    # demande 15, sous le seuil — et 8 est justement le palier de décision du protocole.
    authed_pages: list = []
    if creds is None:
        contexts = [await browser.new_context() for _ in range(n)]
    else:
        user, password = creds
        contexts = []
        for i in range(n):
            ctx = await browser.new_context()
            page = await _login_in(ctx, url, user, password, timeout_ms)
            if page is None:
                for c in contexts + [ctx]:
                    await c.close()
                raise RuntimeError(
                    f"connexion refusée à l'onglet {i + 1}/{n}. Cause la plus probable : "
                    "le limiteur (30 tentatives / 900 s et par IP). Attendre 15 min, ou "
                    "baisser `--levels` — une rampe complète demande 67 connexions. "
                    "On n'entre PAS en mesure anonyme sans le dire.")
            contexts.append(ctx)
            authed_pages.append(page)
    pages = []
    outcomes = dict.fromkeys(_OUTCOMES, 0)
    conn_states: dict[str, int] = {}
    durations: list[float] = []
    try:
        if authed_pages:
            # Les onglets de mesure SONT ceux qui se sont authentifiés.
            pages.extend(authed_pages)
        else:
            for ctx in contexts:
                page = await ctx.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                await _settle(page, timeout_ms)
                pages.append(page)

        rss_after_open = _browser_rss_mb()

        for _ in range(reps):
            # LE point de la mesure : les N clics partent ENSEMBLE. Séquentiellement, on
            # mesurerait N fois la latence d'un seul utilisateur.
            results = await asyncio.gather(
                *(_one_rerun(p, selector, timeout_ms) for p in pages))
            for outcome, ms, conn in results:
                outcomes[outcome] += 1
                conn_states[conn] = conn_states.get(conn, 0) + 1
                if ms is not None:
                    durations.append(ms)

        attempted = n * reps
        return {
            "tabs": n, "reps": reps, "attempted": attempted,
            "durations_ms": durations,
            "outcomes": outcomes,
            "connection_states": conn_states,
            # Le taux de CENSURE, publié. Le p50 ne décrit que `ok` ; au-delà de 20 % il
            # ne peut plus être lu comme une mesure de la dégradation.
            "censored_pct": 100.0 * (attempted - outcomes["ok"]) / attempted if attempted else 0.0,
            # `None` traverse jusqu'au JSON : un champ absent se lit comme une
            # absence, un `0.0` se lirait comme une mesure.
            "browser_rss_mb": (None if rss_after_open is None
                               else round(rss_after_open, 1)),
            "available_mb": round(_available_mb(), 1),
            "live_contexts": len(contexts),
            "timeout_ms": timeout_ms,
        }
    finally:
        for ctx in contexts:
            await ctx.close()


async def _login_in(ctx, url: str, user: str, password: str, timeout_ms: int):
    """Une SEULE authentification, dont l'état est réutilisé par tous les onglets.

    Ce n'est pas une optimisation : `src/dashboard/utils/throttle.py` limite les
    tentatives de connexion à **30 par 900 s et par IP**, et depuis la migration 122 ce
    seau est PARTAGÉ entre les instances. Une rampe qui se reconnecterait à chaque palier
    mesurerait le limiteur.
    """
    page = await ctx.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    await _settle(page, timeout_ms)
    # ⚠️ Les champs sont désignés par leur RÔLE, pas par leur position — correctif du
    # 2026-09-17. La version d'avant faisait `page.locator("input").nth(0)` et `.nth(1)`,
    # en supposant que les deux premiers `input` de la page étaient les identifiants.
    # Le sélecteur de langue (🇫🇷 FR / 🇬🇧 EN) est fait de DEUX boutons radio, rendus
    # AVANT le formulaire : `nth(0)` tombait donc sur un radio, et Playwright échouait
    # sur « waiting for element to be visible, enabled and editable ».
    #
    # Le mode authentifié était cassé depuis l'ajout du sélecteur, sans que personne ne
    # le sache : c'est le mode qu'on n'exerce presque jamais. Un sélecteur POSITIONNEL
    # se casse dès qu'on ajoute un élément au-dessus ; un sélecteur SÉMANTIQUE survit à
    # la mise en page.
    await page.get_by_role("textbox").first.fill(user, timeout=timeout_ms)
    await page.get_by_role("textbox").nth(1).fill(password, timeout=timeout_ms)
    await page.get_by_role("button", name="Se connecter").first.click(timeout=timeout_ms)
    await page.wait_for_timeout(4000)
    # ⚠️ On rend le CONTEXTE, pas un `storage_state()`. Correctif du 2026-09-17, et il
    # ferme un défaut qui rendait le mode authentifié SILENCIEUSEMENT faux.
    #
    # `storage_state()` ne capturait pas le cookie de session `music_dashboard` — seuls
    # `_streamlit_xsrf` et `cf_clearance` y étaient. Les onglets ouverts avec cet état
    # repartaient donc ANONYMES, affichaient la page de connexion, et cliquaient « Pas
    # encore de compte ? Créez-en un » : une page PUBLIQUE, que la couture de métriques
    # n'observe pas (elle vit après `require_login()`).
    #
    # Prouvé : 402 clics « authentifiés » ont produit 10 reruns serveur — les 10 de la
    # connexion elle-même — et 20 clics ciblés en ont produit ZÉRO. La courbe ×17,13
    # publiée comme authentifiée était en fait anonyme.
    #
    # N onglets dans UN contexte, c'est exactement ce que fait le navigateur d'un vrai
    # utilisateur, et ça n'a aucun état à sérialiser.
    # ⚠️ On rend la PAGE, et on ne la ferme surtout pas. Mesuré le 2026-09-17 : fermer
    # l'onglet de connexion puis en ouvrir un neuf perd la session — le nouvel onglet
    # réaffiche le formulaire. L'authentification ne vit pas dans un cookie du bocal
    # (`music_dashboard` n'y est jamais), elle vit dans la session WebSocket de CET
    # onglet. Le mesurer ailleurs, c'est mesurer un autre chemin.
    if not await _is_authenticated(page, timeout_ms):
        await page.close()
        return None
    return page


async def _is_authenticated(page, timeout_ms: int) -> bool:
    """La page montre-t-elle l'application, ou encore le formulaire ?

    ⚠️ `_settle()` rend la main AVANT que Streamlit ait peint le corps : une première
    sonde écrite le 2026-09-17 a répondu « authentifié » sur une page vide, puis
    « non authentifié » huit secondes plus tard sur la même session. On attend donc que
    l'un des deux signaux soit franc, plutôt que de lire à l'instant le plus commode.
    """
    await page.wait_for_timeout(6000)
    try:
        body = await page.inner_text("body", timeout=timeout_ms)
    except Exception:  # noqa: BLE001
        return False
    return "Se connecter" not in body


def _pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1)))))
    return ordered[k]


def _write_level(out_dir: Path | None, row: dict) -> None:
    """Écrit le palier DÈS qu'il est fini.

    Deux passes sur quatre sont mortes en emportant toute la série. Un fichier par palier
    survit à l'interruption — et la série partielle vaut infiniment mieux que rien.
    """
    if out_dir is None:
        return
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"level-{row['tabs']:03d}.json").write_text(
            json.dumps(row, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"  ⚠ palier {row['tabs']} non écrit ({type(exc).__name__}) — "
              "la mesure continue, mais elle ne survivra pas à une interruption")


def _print_level(row: dict) -> None:
    o, d = row["outcomes"], row["durations_ms"]
    p50 = _pct(d, 50)
    print(f"  {row['tabs']:3d} onglet(s) → p50 {p50:7.0f} ms   "
          f"max {max(d) if d else float('nan'):7.0f} ms   "
          f"censure {row['censored_pct']:5.1f} %")
    échecs = {k: v for k, v in o.items() if k != "ok" and v}
    if échecs:
        print("      échecs : " + "  ".join(f"{k}={v}" for k, v in échecs.items())
              + f"   (serveur = never_finished : {o['never_finished']})")
    print(f"      navigateur {row['browser_rss_mb']:.0f} Mo · "
          f"dispo {row['available_mb']:.0f} Mo · "
          f"connexion {row['connection_states']}")


async def _run(args) -> int:
    from playwright.async_api import async_playwright

    levels = [int(x) for x in args.levels.split(",") if x.strip()]
    out_dir = Path(args.out) if args.out else None
    print(f"▶ {args.url}   paliers {levels}   {args.reps} clic(s) par onglet et par palier")
    print(f"  interaction : {args.selector}")
    if out_dir:
        print(f"  relevés écrits au fil de l'eau dans {out_dir}/")
    print()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        creds = None
        try:
            if args.user:
                print("  authentification unique (état réutilisé par tous les onglets)…")
                creds = (args.user, args.password)

            rows: list[dict] = []
            for n in levels:
                # Le client peut se saturer AVANT le serveur, et c'est ce qui a produit un
                # compte de pertes non monotone. On vérifie à CHAQUE palier, pas une fois
                # au début — et on s'arrête plutôt que de publier un chiffre du client.
                avail = _available_mb()
                if avail and avail < args.min_free_mb and not args.force_busy:
                    print(f"  ⛔ arrêt avant le palier {n} : {avail:.0f} Mo disponibles "
                          f"(plancher {args.min_free_mb}). Au-delà, les « reruns perdus » "
                          "décrivent CE navigateur, pas le serveur.\n"
                          f"     Les {len(rows)} palier(s) déjà mesurés restent valables.")
                    break

                row = await _level(browser, args.url, n, args.reps,
                                   args.selector, args.timeout * 1000, creds)
                _write_level(out_dir, row)
                rows.append(row)

                if not row["durations_ms"]:
                    _print_level(row)
                    print(f"  ❌ palier {n} : AUCUN rerun n'a abouti. Les compteurs "
                          "ci-dessus disent lequel des quatre chemins a échoué — un "
                          "tableau vide vaut mieux qu'un tableau faux.")
                    break
                _print_level(row)

            if not rows or not any(r["durations_ms"] for r in rows):
                print("\n❌ rien de mesurable. Ne rien publier est le résultat.")
                return 1

            print()
            print("| onglets | p50 (ms) | p95 (ms) | max (ms) | censure | serveur "
                  "(never_finished) | client (click_failed) | p50 / p50(1) |")
            print("|---|---|---|---|---|---|---|---|")
            base = None
            censored_high = False
            for r in rows:
                d = r["durations_ms"]
                if not d:
                    continue
                p50, p95 = _pct(d, 50), _pct(d, 95)
                base = base or p50
                if r["censored_pct"] > 20:
                    censored_high = True
                mark = " ⚠" if r["censored_pct"] > 20 else ""
                print(f"| {r['tabs']} | {p50:.0f} | {p95:.0f} | {max(d):.0f} | "
                      f"{r['censored_pct']:.0f} %{mark} | {r['outcomes']['never_finished']} "
                      f"| {r['outcomes']['click_failed']} | **×{p50 / base:.2f}** |")
            print()
            print("La colonne qui compte est la DERNIÈRE. Un processus unique sérialise "
                  "les reruns :\nsi p50 croît proportionnellement à N, la contention est "
                  "totale ; s'il reste plat,\nle service absorbe la concurrence. Le réseau "
                  "est dans la valeur absolue, pas dans\nle rapport.")
            if censored_high:
                print()
                print("⚠️  CENSURE > 20 % sur au moins un palier (marqué ⚠). Le p50 n'y "
                      "décrit que les reruns\n    ABOUTIS : il SOUS-ESTIME la dégradation, "
                      "et le rapport ×N y est une BORNE\n    INFÉRIEURE, jamais une mesure. "
                      "Lire la colonne `never_finished` d'abord — c'est la\n    seule des "
                      "quatre causes d'échec qui parle du serveur.")
            print()
            print("Croiser avec l'histogramme SERVEUR, qui ne dépend pas de ce client :\n"
                  "  histogram_quantile(0.95, sum by (le, page) "
                  "(rate(streamlytics_rerun_duration_seconds_bucket[5m])))")
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
    parser.add_argument("--out", default=None,
                        help="dossier où écrire un JSON PAR PALIER, au fil de l'eau")
    parser.add_argument("--min-free-mb", type=float, default=800.0,
                        help="plancher de RAM libre ; en dessous, le palier est refusé")
    parser.add_argument("--force-busy", action="store_true",
                        help="mesurer même si la machine est occupée (les temps y sont du bruit)")
    args = parser.parse_args()

    # Le verdict porte sur la CHARGE, pas sur un compte de processus présents.
    # Seuils : 50 % d'un cœur en moyenne sur 1 min, ou 80 % d'un cœur consommés par
    # les processus qui ont déjà faussé une mesure ici (pytest, audit_runner,
    # playwright, chromium). En dessous, la machine est inactive et la mesure vaut.
    mesure = _local_load()
    heavy = _heavy_local_processes()
    if mesure is None:
        # On ne SAIT pas. Refuser est la direction prudente : le seul cas où `ps`
        # expire est celui d'une machine chargée, c'est-à-dire celui où le verdict
        # aurait été « non ». Répondre « autorisée » ici serait se tromper
        # exactement quand ça compte.
        print("❌ charge locale ILLISIBLE (`ps` ou /proc/loadavg a expiré). Ce n'est "
              "pas une machine inactive : c'est une machine dont on ne sait rien, et "
              "un `ps` qui met plus de dix secondes est déjà un symptôme.\n"
              "   Attendre, ou --force-busy en sachant ce qu'on lit.")
        return 1 if not args.force_busy else 0
    load_ratio, heavy_cpu = mesure
    if (load_ratio > 0.50 or heavy_cpu > 80.0) and not args.force_busy:
        print(f"❌ machine occupée : charge {load_ratio:.2f}/cœur, "
              f"{heavy_cpu:.0f} % de CPU sur "
              f"{'?' if heavy is None else heavy} processus lourds. "
              "Une mesure prise sous charge auto-infligée a déjà coûté un facteur "
              "12,8 à ce dépôt.\n"
              "   Attendre, ou --force-busy en sachant ce qu'on lit.")
        return 1
    print(f"▶ machine : charge {load_ratio:.2f}/cœur, {heavy_cpu:.0f} % de CPU lourd "
          f"({'?' if heavy is None else heavy} processus repérés) — mesure autorisée")
    if args.user and not args.password:
        print("❌ --user sans --password")
        return 1
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
