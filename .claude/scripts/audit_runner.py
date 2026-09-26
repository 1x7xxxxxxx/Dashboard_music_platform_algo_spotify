#!/usr/bin/env python3
"""
Error-class signature runner — single executable source of truth.

Parses every class in `.claude/dev-docs/error-classes.md`, extracts its
`signature` / `kind` / `status`, and runs each signature.cmd. The catalogue
contract: a signature exits NON-ZERO when the anti-pattern is present (a "hit").

This replaces the hand-synced grep recipes in the Makefile `audit:` target, so
a class added to the catalogue is swept automatically (no catalogue↔Makefile
drift). `kind: deterministic` classes are CI-safe (0 false positives) and may
block; `kind: heuristic` classes run nightly, non-blocking (manual triage).

Usage:
  audit_runner.py --deterministic   # only kind: deterministic; exit 1 on any hit (CI blocking)
  audit_runner.py [--all]           # every class; exit 1 on any hit (nightly; caller tolerates with || true)
  audit_runner.py --list            # list id · kind · status, no run

Type: Utility (Claude Code config)
Uses: error-classes.md, subprocess
Persists in: — (report to stdout + exit code)

---
rex:
  - date: 2026-06-13
    issue: "make audit hardcoded ~6 grep signatures while error-classes.md catalogued 21 → drift; new classes never swept"
    fix: "audit_runner.py parses error-classes.md signatures and runs them; Makefile + CI delegate to it (catalogue = single source of truth)"
    ref: "DEVLOG#2026-06-13-suite22"
    severity: warn
  - date: 2026-09-18
    issue: "run_signature returned hit = (returncode != 0), so rc=2 (sh syntax error), rc=127 (missing command) and rc=5 (pytest collected nothing — a signature pointing at a deleted test) all read as 'the class was touched'. A deterministic signature with an unterminated backtick blocked CI for a whole day while reporting a find."
    fix: "Three-state verdict: 0 clean, 1 hit, {2,5,126,127} or timeout BROKEN — reported in its own section with exit 2. Added --lint (sh -n, no <placeholder>, even backtick count) wired before --static in ci.yml; it found 3 unrunnable signatures out of 390 in 0.4 s."
    ref: "0d24560"
    severity: crit
  - date: 2026-09-18
    issue: "A class was written for every defect fixed — ~10 a day, 16 hand-held fields each, and 91% never recur. The catalogue grew faster than anyone could read it."
    fix: "--admission gate: a class introduced after the cutover must carry `admitted:` with a NUMBER — two dated recurrences, >=2 swept sites, or a named P1 production impact. Retroactive calibration on the 401 existing classes: 60 (15%) would have been admitted, so ~10/day becomes ~1.4/day."
    ref: "f47d1ec"
    severity: warn
---
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

# Best-effort usage telemetry (curator self-improvement loop). Defensive: a broken
# sidecar must never fail the audit / CI sweep.
try:
    from usage_telemetry import record as _telemetry_record
except Exception:  # noqa: BLE001 — telemetry is optional
    def _telemetry_record(*_a, **_k):
        return None

_REPO = Path(__file__).resolve().parents[2]            # .claude/scripts/ -> repo root
_CATALOGUE = _REPO / ".claude/dev-docs/error-classes.md"

# Documentation scaffolding sections that look like a class header but are not runnable.
_SKIP_IDS = {"class-id"}
_KEBAB = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def parse_all_headers(text: str) -> list[dict]:
    """Return one dict per class header (kebab id), signature-bearing OR NOT.

    {id, kind, status, signature|None}. Unlike the old parser this does NOT drop
    signature-less (prose) classes — the `--coverage` meta-guard needs to SEE them
    (a catalogued-but-un-swept class is the exact blind spot that let the 2026-07-07
    Alembic prose REX re-fire). The id is the FIRST token of the header, so a
    date/ADR suffix (`## foo (2026-07-11, ADR-047)`) no longer breaks kebab matching.
    """
    out = []
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = sec.splitlines()
        cid = (lines[0].strip().split() or [""])[0]      # first token → tolerate "(date, ADR)" suffix
        if cid.lower() in _SKIP_IDS or not _KEBAB.match(cid):
            continue
        body = "\n".join(lines[1:])
        # First backtick-delimited span after "- signature:"; tolerate trailing prose
        # after the closing backtick. Signatures never contain an internal backtick.
        # A `—` placeholder (no real command) counts as NO signature.
        sig = re.search(r"^- signature:\s*`([^`]+)`", body, flags=re.M)
        sig_val = sig.group(1).strip() if sig else None
        # LA LIGNE ENTIÈRE, pas seulement la capture — et c'est `--lint` qui la lit.
        #
        # La capture ci-dessus s'arrête au PREMIER accent grave fermant. Une ligne qui
        # en porte un nombre impair est donc tronquée en silence, et la commande
        # obtenue peut être syntaxiquement invalide tout en ayant l'air complète.
        # C'est ce qui a bloqué la CI le 2026-09-18 : la signature contenait un
        # accent grave à l'intérieur de son motif grep. Le compte se fait sur la ligne
        # brute, sinon on ne peut pas le voir.
        raw = re.search(r"^- signature:.*$", body, flags=re.M)
        if sig_val in ("—", "-", ""):
            sig_val = None
        kind = re.search(r"^- kind:\s*([\w-]+)", body, flags=re.M)
        status = re.search(r"^- status:\s*([\w-]+)", body, flags=re.M)
        out.append({
            "id": cid,
            "kind": (kind.group(1) if kind else ("heuristic" if sig_val else "")).lower(),
            "status": (status.group(1) if status else "open").lower(),
            "signature": sig_val,
            "signature_raw": raw.group(0) if raw else None,
            "first_seen": (re.search(r"^- first_seen:\s*(20\d\d-\d\d-\d\d)", body,
                                     flags=re.M) or [None, None])[1]
            if re.search(r"^- first_seen:\s*(20\d\d-\d\d-\d\d)", body, flags=re.M)
            else None,
            "admitted": _prose_field(body, "admitted"),
            "family": _prose_field(body, "family"),
            "severity": (re.search(r"^- severity:\s*(P\d)", body, flags=re.M) or [None, None])[1]
            if re.search(r"^- severity:\s*(P\d)", body, flags=re.M) else None,
            "guard": _prose_field(body, "guard"),
            "root_cause": _prose_field(body, "root_cause"),
            "long_term_fix": _prose_field(body, "long_term_fix"),
        })
    return out


_GUARD_PATH = re.compile(r"[\w./-]+\.(?:py|sh|yml|yaml)")


def unguarded_classes(headers: list[dict], severity: str) -> list[str]:
    """Classes of `severity` that NOTHING executes: no signature, and no guard file on disk.

    Added 2026-09-25 for the nightly P1 pass: a critical class guarded only by prose is
    guarded by memory. A `guard:` naming a file that no longer exists counts as no guard."""
    out = []
    for h in headers:
        if h.get("severity") != severity or h["signature"]:
            continue
        paths = _GUARD_PATH.findall(h.get("guard") or "")
        if not any((_REPO / p.split("::")[0]).exists() for p in paths):
            out.append(h["id"])
    return out


def _prose_field(body: str, name: str) -> str | None:
    """Value of a free-text `- <name>:` line, or None when absent/empty.

    A bare `—` is None: the schema uses it as "nothing to say here", and counting
    it as an answer would make the field-completeness check pass on the classes it
    exists to find. `— (the guard IS the fix)` is NOT bare — it is a real answer,
    and the commonest legitimate one for a class whose signature is the whole fix.
    """
    m = re.search(rf"^- {name}:\s*(.*)$", body, flags=re.M)
    if not m:
        return None
    val = m.group(1).strip()
    return None if val in ("", "—", "-", "<...>") else val


def parse_classes(text: str) -> list[dict]:
    """Runnable classes only (those carrying a real `- signature:` command)."""
    return [c for c in parse_all_headers(text) if c["signature"]]


_PLACEHOLDER = "__SET_IN_ENV_LOCAL__"


def _load_env_files() -> dict:
    """`.env` → `.env.local` → `.claude/audit_runner.env`, sans écraser l'environnement réel.

    Pourquoi c'est ici et pas dans le shell de l'appelant, 2026-08-04. Le
    balayage `--deterministic` a rendu **10 classes en rouge** dont 8 portées par
    des signatures pytest. Aucune n'était un défaut : le shell n'exportait pas les
    identifiants PG, `conftest` échouait au setup, et le runner comptait chaque
    erreur de connexion comme une occurrence de la classe. Le même test repasse
    vert avec `.env.local` chargé.

    C'est la pire panne possible pour ce fichier, parce qu'elle est SILENCIEUSE et
    qu'elle va dans le sens de l'alarme : le catalogue promet « deterministic =
    zéro faux positif, sûr pour bloquer la CI », et un rouge qu'on finit par
    ignorer ne garde plus rien. Un runner qui dépend d'un environnement doit le
    charger lui-même, ou refuser de conclure.

    `.claude/audit_runner.env` est la couche locale non versionnée : c'est là que
    vit une réécriture propre à la machine (`PG_HOST=127.0.0.1` quand `.env` vise
    le nom de service Docker `postgres`, injoignable depuis l'hôte).
    """
    env = dict(os.environ)
    # Les fichiers se superposent entre eux dans l'ordre, PUIS cèdent le pas à
    # l'environnement réel — ce que la docstring ci-dessus promet depuis le
    # 2026-08-04 et que le code ne faisait pas : `env[cle] = val` écrasait
    # `os.environ` sans condition.
    #
    # Conséquence mesurée le 2026-08-17 sur la CI de msdr : le job `guards`
    # exporte `PG_PASSWORD: msdr`, `.env` porte `__SET_IN_ENV_LOCAL__`, le
    # fichier gagnait, et le runner sortait en 2 — « environnement non résolu »
    # — en NOMMANT une variable que l'appelant avait pourtant renseignée. Le
    # garde des classes d'erreur était donc structurellement rouge en CI, et
    # `main` rouge depuis le 12 juillet. Un runner qui ignore l'environnement
    # qu'on lui donne ne peut pas être satisfait : il n'y a aucun geste qui le
    # rende vert, et un garde qu'on ne peut pas satisfaire finit ignoré.
    depuis_fichiers: dict[str, str] = {}
    for name in (".env", ".env.local", ".claude/audit_runner.env"):
        f = _REPO / name
        if not f.exists():
            continue
        for ligne in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, val = ligne.split("=", 1)
            cle, val = cle.strip(), val.strip().strip('"').strip("'")
            if cle and not cle.startswith("export "):
                depuis_fichiers[cle] = val
    for cle, val in depuis_fichiers.items():
        if cle not in os.environ:
            env[cle] = val
    return env


_ENV = None


def signature_env() -> dict:
    global _ENV
    if _ENV is None:
        _ENV = _load_env_files()
        restants = sorted(k for k, v in _ENV.items() if _PLACEHOLDER in v)
        if restants:
            print(f"❌ environnement non résolu — {', '.join(restants)} porte encore "
                  f"{_PLACEHOLDER}. Les signatures pytest rendraient des rouges qui ne "
                  f"sont pas des défauts. Renseigner `.env.local` (ou "
                  f"`.claude/audit_runner.env`) avant de conclure.", file=sys.stderr)
            sys.exit(2)
    return _ENV


# Les codes de sortie qui ne veulent PAS dire « la classe est touchée ».
#
# Mesuré le 2026-09-18, et c'est ce qui a rendu la CI rouge pendant trois heures.
# `hit = proc.returncode != 0` confond quatre choses très différentes :
#
#   rc=2   `/bin/sh` n'a pas su parser la signature — c'est le cas qui a bloqué la CI,
#          sur une signature portant un backtick non fermé et un `<placeholder>` ;
#          c'est aussi ce que rend `grep` quand il ne peut pas LIRE un fichier ;
#   rc=5   pytest : « no tests collected » — une signature qui pointe un test renommé
#          ou supprimé. Le garde a disparu, et le runner annonce un défaut ;
#   rc=126 trouvé mais non exécutable · rc=127 commande absente (un outil pas installé
#          sur ce poste, ou pas dans l'image du runner) ;
#   timeout une signature qui pend.
#
# Aucun de ces cinq n'est un défaut du PRODUIT. Les compter comme des touches fait
# exactement ce que ce dépôt reproche à une sonde : rendre un résultat PLAUSIBLE là où
# la bonne réponse est « je ne sais pas ». Ils remontent donc séparément, et avec un
# code de sortie distinct — 2, jamais 1.
_BROKEN_CODES = {2, 5, 126, 127}

CLEAN, HIT, BROKEN = "clean", "hit", "broken"


_SIGNATURE_WORKERS = 4   # the CI runner's vCPU count


def run_signature(sig: str) -> tuple[str, str]:
    """Run one signature from the repo root. Returns (verdict, output).

    `verdict` vaut `CLEAN` (rien trouvé), `HIT` (la classe est touchée) ou `BROKEN`
    (la signature n'a pas pu rendre de verdict — voir `_BROKEN_CODES`).
    """
    try:
        proc = subprocess.run(
            sig, shell=True, cwd=_REPO, env=signature_env(),
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return BROKEN, "la signature a dépassé 300 s sans rendre de verdict"
    out = (proc.stdout + proc.stderr).strip()
    if proc.returncode == 0:
        return CLEAN, out
    if proc.returncode in _BROKEN_CODES:
        return BROKEN, f"exit {proc.returncode} — {out}"
    return HIT, out


def _venv_python() -> str:
    """Path to the project interpreter, resolved from the MAIN worktree.

    Every signature names `python/.venv/bin/python`, but `python/.venv` is
    gitignored — so a linked worktree (the engineering loop runs its Fix phase in
    one) has no interpreter at that path. The signature then either errors out or
    silently falls back to the system python, which cannot import ~21 of the test
    modules; either way the guard reports something unrelated to the code.

    `--git-common-dir` points at the shared .git of the main worktree, whose
    parent is the main checkout, which is where the venv actually lives.
    """
    local = _REPO / "python" / ".venv" / "bin" / "python"
    if local.exists():
        return str(local)
    try:
        common = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                                cwd=_REPO, capture_output=True, text=True,
                                timeout=30, check=True).stdout.strip()
        main_root = (_REPO / common).resolve().parent
        candidate = main_root / "python" / ".venv" / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    except (subprocess.SubprocessError, OSError):
        pass
    return sys.executable          # last resort; loud because the run will fail visibly


_SHELL_OPS = re.compile(r"[|;&><]|\$\(")


def pytest_targets(sig: str) -> list[str] | None:
    """Node-ids a *simple* pytest signature targets, or None if it is not batchable.

    Conservative on purpose: anything carrying a shell operator keeps its own
    subprocess. Measured on this catalogue: 40/40 pytest signatures are simple,
    resolving to 42 unique node-ids across 32 files.
    """
    if "pytest" not in sig or _SHELL_OPS.search(sig):
        return None
    try:
        toks = shlex.split(sig)
    except ValueError:
        return None
    if "pytest" not in toks:
        return None
    after = toks[toks.index("pytest") + 1:]
    targets = [t for t in after if not t.startswith("-") and ".py" in t]
    return targets or None


def _failed_nodes(output: str) -> set[str]:
    """Node-ids pytest reported as FAILED or ERROR in its short summary."""
    return set(re.findall(r"^(?:FAILED|ERROR)\s+(\S+?)(?:\s+-.*)?$", output, re.M))


def run_batched(classes: list[dict]) -> tuple[dict[str, tuple[bool, str]], list[dict]]:
    """Run every batchable pytest class in ONE pytest invocation.

    40 separate invocations pay pytest startup and collection 40 times; on a 9p
    mount that was ~7 s each before a single assertion ran. One invocation over
    the union of node-ids pays it once (measured: 45.7 s of collection for the
    whole set).

    Returns ({class_id: (hit, output)}, [classes to run individually]).
    Falls back wholesale when pytest reports anything other than pass/fail —
    a collection error cannot be attributed to one class, and guessing would be
    worse than being slow.
    """
    targets: dict[str, list[str]] = {}
    rest: list[dict] = []
    for c in classes:
        t = pytest_targets(c["signature"])
        if t:
            targets[c["id"]] = t
        else:
            rest.append(c)

    if len(targets) < 2:
        return {}, classes

    union = sorted({t for ts in targets.values() for t in ts})
    print(f"▶ batching {len(targets)} pytest signature(s) → 1 invocation "
          f"({len(union)} node-ids)\n")
    proc = subprocess.run(
        [_venv_python(), "-m", "pytest", *union, "-q", "--tb=no", "-rfE"],
        cwd=_REPO, env=signature_env(), capture_output=True, text=True, timeout=1800,
    )
    out = proc.stdout + proc.stderr
    if proc.returncode not in (0, 1):
        print(f"  batch inconclusive (pytest exit {proc.returncode}) — "
              f"falling back to one run per signature")
        return {}, classes

    failed = _failed_nodes(out)
    results: dict[str, tuple[bool, str]] = {}
    for cid, ts in targets.items():
        hit_nodes = [f for f in failed
                     if any(f == t or f.startswith(t + "::") for t in ts)]
        detail = "\n".join(hit_nodes) if hit_nodes else ""
        results[cid] = (bool(hit_nodes), detail)
    return results, rest


_OPTOUT_KINDS = {"manual", "runtime-manual"}  # acknowledged as intentionally NOT auto-swept


_PLACEHOLDER_IN_SIG = re.compile(r"<[a-z_][a-z0-9_ -]*>", re.I)


def _lint(headers: list[dict]) -> int:
    """Une signature doit pouvoir S'EXÉCUTER avant de pouvoir juger quoi que ce soit.

    Né le 2026-09-18, d'une matinée entière de CI rouge. La signature de
    `a-backtick-in-a-shell-string-is-executed` était un GABARIT — un `<script>` à
    remplacer et un backtick non fermé. `/bin/sh` rendait « Syntax error: Unterminated
    quoted string » et un code 2, que `run_signature` lisait comme « la classe est
    touchée ». Une porte bloquante était donc rouge à cause de sa propre syntaxe, et le
    message annonçait « ces touches sont réelles ».

    Trois contrôles, tous mécaniques :

    * `sh -n` — la commande parse-t-elle ?
    * aucun `<placeholder>` — une signature qu'il faut compléter à la main n'est pas
      exécutable, quelle que soit la qualité de sa prose ;
    * un nombre PAIR d'accents graves sur la ligne `- signature:` — c'est ce qui a
      fait tronquer la capture du parseur au mauvais endroit, et la classe
      `a-backtick-in-a-shell-string-is-executed` existe précisément pour dire que
      l'accent grave est un opérateur, pas une décoration.
    """
    fautes: list[tuple[str, str]] = []
    for h in headers:
        sig = (h.get("signature") or "").strip()
        if not sig:
            continue
        cid = h["id"]
        if h.get("signature_raw") and h["signature_raw"].count("`") % 2:
            fautes.append((cid, "nombre IMPAIR d'accents graves sur la ligne `- signature:`"))
        placeholder = _PLACEHOLDER_IN_SIG.search(sig)
        if placeholder:
            fautes.append((cid, f"porte le gabarit {placeholder.group(0)} — "
                                "à compléter à la main, donc non exécutable"))
            continue
        proc = subprocess.run(["sh", "-n", "-c", sig], capture_output=True, text=True)
        if proc.returncode != 0:
            fautes.append((cid, f"`sh -n` refuse : {proc.stderr.strip()[:90]}"))

    print(f"▶ lint: {sum(1 for h in headers if (h.get('signature') or '').strip())} "
          f"signature(s) examinée(s)")
    if not fautes:
        print("✅ toutes les signatures s'exécutent")
        return 0
    for cid, why in fautes:
        print(f"  ⊘  {cid}\n       {why}")
    print(f"\n⊘ {len(fautes)} signature(s) ne peuvent pas rendre de verdict.\n"
          "  Une porte bloquante rouge à cause de sa propre syntaxe n'est pas une porte.")
    return 2

def _coverage(headers: list[dict]) -> int:
    """Meta-guard: every catalogued class must be GUARDED (has a runnable `- signature:`) OR
    carry an explicit opt-out `- kind:` ∈ {manual (needs host access), runtime-manual (no static
    footprint)}. A class with NEITHER (prose with no kind, or a kind that implies auto-sweep like
    `deterministic` but no signature) is UNGUARDED — the catalogue silently accreting un-swept
    prose is the structural blind spot. Exit 1 on any unguarded class."""
    unguarded = [h for h in headers if h["signature"] is None and h["kind"] not in _OPTOUT_KINDS]
    guarded = [h for h in headers if h["signature"]]
    optout = [h for h in headers if h["signature"] is None and h["kind"] in _OPTOUT_KINDS]
    total = len(headers)
    pct = (100 * len(guarded) // total) if total else 0
    print(f"▶ coverage: {total} classes — {len(guarded)} guarded ({pct}%) · "
          f"{len(optout)} manual/runtime opt-out · {len(unguarded)} UNGUARDED")
    if unguarded:
        print("\n❌ UNGUARDED classes (add a `- signature:` OR `- kind: runtime-manual`):")
        for h in unguarded:
            print(f"      {h['id']}  [kind={h['kind'] or '∅'}/{h['status']}]")
        return 1
    print("\n✅ coverage complete — every class is guarded or explicitly runtime-manual")
    return 0



# ── LE BILLET D'ADMISSION ────────────────────────────────────────────────────
#
# Trois formes, et chacune est un NOMBRE, pas un jugement :
#
#   recurrence:<date1>,<date2>   le défaut est daté DEUX fois. Une fois est un
#                                accident, deux fois est une classe.
#   sites:<N>  avec N ≥ 2        un balayage a trouvé au moins deux sites VIVANTS.
#                                Un balayage muet, ou une simple relance du garde,
#                                n'est pas un billet.
#   p1:<impact production>       un dommage constaté en production.
_ADMISSION = re.compile(
    r"^\s*(?:recurrence:20\d\d-\d\d-\d\d,\s*20\d\d-\d\d-\d\d"
    r"|sites:(\d+)"
    r"|p1:\S.*)\s*$")
_ADMISSION_SINCE = re.compile(r"^<!-- admission-since: (20\d\d-\d\d-\d\d) -->$", re.M)


def _admission_since() -> str | None:
    m = _ADMISSION_SINCE.search(_CATALOGUE.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def _admission_verdict(billet: str | None) -> str | None:
    """None si le billet est valide, sinon la raison du refus."""
    if not billet:
        return "aucun champ `- admitted:`"
    m = _ADMISSION.match(billet.strip())
    if not m:
        return (f"billet illisible : {billet.strip()[:60]!r}. Formes acceptées : "
                "`recurrence:<date>,<date>` · `sites:<N≥2>` · `p1:<impact>`")
    if m.group(1) is not None and int(m.group(1)) < 2:
        return (f"`sites:{m.group(1)}` — un seul site est un cas isolé, pas une "
                "classe. Le seuil est 2, et c'est le seul qui se tienne sans "
                "statistique : un défaut présent à deux endroits n'est pas unique "
                "par définition.")
    return None


def _sweep_verdict(headers: list[dict]) -> int:
    """Un `siblings:` qui dit `swept:` doit porter un VERDICT lisible.

    Pourquoi une PORTE, alors qu'un compteur existe déjà
    -----------------------------------------------------
    `make error-health` compte les faux balayages APRÈS coup. Il en a compté **97** le
    2026-09-17 — c'est-à-dire 97 classes dont le `siblings:` disait « j'ai relancé le
    garde, il est vert », ce qui prouve que le prédicat de CE garde ne trouve rien,
    jamais qu'il n'y a rien. Mesuré trois fois la nuit du 17 au 18 : **un garde vert sur
    8 sites vivants**.

    Les 97 ont été balayées (R137, closes le 2026-09-18, 310 défauts réels trouvés). Un
    compteur remis à zéro ne dit rien sur le prochain : **rien n'empêchait d'en écrire un
    98ᵉ**, et le compteur ne l'aurait signalé qu'au prochain `make error-health`, dans le
    meilleur des cas quelques commits plus tard.

    Pourquoi les prédicats sont IMPORTÉS et non recopiés
    -----------------------------------------------------
    Une porte qui recopierait `_RERUN` et `_swept_sites` serait une **seconde définition
    de la même grandeur**, et ce dépôt a mesuré ce que ça coûte : c'est la classe
    `trigger-threshold-split`, dont le balayage du 2026-09-18 a trouvé **quatre barèmes
    pour « une source n'a pas collecté récemment »** et **18 écarts réels** tombant là où
    une surface alerte et l'autre non. La porte et le compteur doivent dire la même chose
    **par construction**, pas par relecture.

    Ce que la porte refuse, et ce qu'elle laisse passer
    ----------------------------------------------------
    Elle refuse deux formes, et deux seulement :

    * un `swept:` dont la prose est une RELANCE de garde ;
    * un `swept:` sans compte lisible en gras (`**N site(s) vivant(s)**` / `**0 site
      vivant**`).

    Elle NE refuse PAS l'absence de `swept:` — une classe jamais balayée est un trou
    déclaré, compté par `siblings_never_swept`, pas une faute d'écriture. Et elle ne juge
    pas le CHIFFRE : un balayage peut légitimement rendre 0.

    ⚠️ **L'exemption est VIDE depuis le 2026-09-22, et c'est un état, pas un oubli.**
    Elle portait deux classes à verdict délibérément non concluant. Les deux ont été
    tranchées ce jour-là, et la même cause les expliquait toutes les deux : **leur
    prédicat cherchait une FORME là où la classe parle d'une PROPRIÉTÉ.**

      * `a-fallback-that-runs-when-the-first-branch-succeeded` — sept mots (`push`,
        `commit`, …) à droite d'un `||`. Refait sur « le repli AGIT-il ? » : 91 bruts,
        90 écartés, **1 site vivant** — et l'ancien motif l'avait VU puis écarté comme
        faux positif de `commit` dans `pre-commit`. Il avait raison sur le site et tort
        sur la raison.
      * `a-guard-satisfied-by-the-collapse-it-should-catch` — `assert not …`. Refait sur
        « cette assertion est-elle VRAIE sur un écran vide ? » : 26 bruts, 11 fonctions
        écartées, **2 sites vivants**, prouvés par un témoin — les deux restaient vertes
        avec la surface stérilisée, une fonction ancrée du même fichier rougissait.

    Garder l'exemption après coup aurait autorisé en silence un futur balayage muet sur
    ces deux noms exactement. Y remettre une classe reste possible ; c'est une décision
    qui s'écrit, et le compteur `sites_unknown` la rendra visible de toute façon.
    """
    import sys as _sys
    _sys.path.insert(0, str(_REPO / "tools" / "dev"))
    try:
        from error_class_health import (  # noqa: PLC0415
            _blocks, _field, _swept_by_rerunning_the_guard, _swept_sites)
    except ImportError as exc:      # pragma: no cover - le générateur doit être là
        print(f"▶ sweep-verdict: `tools/dev/error_class_health.py` illisible ({exc}).\n"
              "   La porte IMPORTE ses prédicats du compteur, à dessein : les recopier "
              "produirait deux définitions de la même grandeur.")
        return 1
    finally:
        _sys.path.pop(0)

    # ⚠️ Le champ `siblings` est lu par `_blocks`/`_field` du GÉNÉRATEUR, pas par
    # `parse_all_headers` de ce fichier — qui ne l'extrait pas. Première écriture de
    # cette porte : elle lisait `h.get("siblings")` sur les en-têtes locaux, donc
    # **toujours vide**, et elle sortait 0 en annonçant « 0 balayage déclaré » sur un
    # catalogue qui en porte 402. Verte parce qu'elle ne voyait RIEN — le mode
    # d'aveuglement que ce dépôt appelle un garde vacant, et que seule l'exécution a
    # révélé : ni ruff ni la lecture ne pouvaient le dire.
    blocs = _blocks((_REPO / ".claude" / "dev-docs" / "error-classes.md")
                    .read_text(encoding="utf-8"))

    #: VIDE au 2026-09-22 — les deux exemptions d'origine ont été tranchées. Voir la
    #: docstring : une classe n'y entre que par une décision écrite.
    non_concluants: set[str] = set()

    relances, muets, total = [], [], 0
    perimees = []                         # exemptions qui n'exemptent plus rien
    for cle, corps in blocs.items():
        champ = (_field(corps, "siblings") or "").strip()
        if not champ.startswith("swept:"):
            continue                      # jamais balayée : un trou déclaré, pas une faute
        total += 1
        if cle in non_concluants:
            # ⚠️ UNE EXEMPTION SE VÉRIFIE, elle ne se croit pas. Ajouté le 2026-09-22,
            # après avoir tranché les deux classes qu'elle portait : la liste serait
            # restée et aurait autorisé en silence un balayage muet sur ces deux noms
            # exactement. Une exemption dont le motif a disparu est un garde désarmé
            # dont personne ne sait qu'il l'est.
            if _swept_sites(champ) is not None:
                perimees.append(cle)
            continue
        if _swept_by_rerunning_the_guard(champ):
            relances.append(cle)
        elif _swept_sites(champ) is None:
            muets.append(cle)

    inconnues = sorted(non_concluants - set(blocs))

    if total == 0:
        print("▶ sweep-verdict: **0 balayage déclaré** dans le catalogue.\n"
              "   Ce n'est pas un succès : le catalogue en porte des centaines. La\n"
              "   lecture a raté sa cible, et cette porte serait verte sur n'importe\n"
              "   quoi. Vérifier `_blocks`/`_field` du générateur.")
        return 1

    if perimees or inconnues:
        print(f"❌ {len(perimees) + len(inconnues)} exemption(s) périmée(s) dans "
              "`non_concluants` :")
        for c in perimees:
            print(f"   {c} — porte désormais un compte LISIBLE, l'exemption ne sert plus")
        for c in inconnues:
            print(f"   {c} — cette classe n'existe plus dans le catalogue")
        print("   Les retirer de `non_concluants`. Une exemption qui n'exempte plus rien")
        print("   est un garde désarmé dont personne ne sait qu'il l'est : elle autorise")
        print("   en silence un futur balayage muet sur ce nom exactement.")
        return 1

    if not relances and not muets:
        print(f"▶ sweep-verdict: {total} balayage(s) déclaré(s), "
              f"{len(non_concluants)} non concluant(s) assumé(s)")
        print("✅ tout `swept:` porte un verdict lisible")
        return 0

    if relances:
        print(f"❌ {len(relances)} balayage(s) ne sont qu'une RELANCE du garde :")
        for c in sorted(relances):
            print(f"   {c}")
        print("   Un garde vert prouve que SON prédicat ne trouve rien, jamais qu'il n'y")
        print("   a rien. Mesuré trois fois la nuit du 17 au 18 : un garde vert sur")
        print("   8 sites vivants. Balayer la PROPRIÉTÉ, pas relancer la forme.")
    if muets:
        print(f"❌ {len(muets)} balayage(s) sans verdict lisible :")
        for c in sorted(muets):
            print(f"   {c}")
        print("   Écrire **N site(s) vivant(s)** ou **0 site vivant** EN GRAS — c'est la")
        print("   forme que `_swept_sites` lit. Une prose qui parle de sites sans les")
        print("   compter est exactement ce que `sites_unknown` existe pour rendre")
        print("   visible. Si le verdict est vraiment non concluant, le dire et")
        print("   l'inscrire dans `non_concluants` — c'est une décision, pas un oubli.")
    return 1


def _family_slugs() -> frozenset:
    """The 18 family slugs, from the generator that renders them (one source)."""
    import importlib.util
    path = Path(__file__).resolve().parents[2] / "tools" / "dev" / "error_class_families.py"
    spec = importlib.util.spec_from_file_location("error_class_families_slugs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SLUGS


def undeclared_families(headers: list[dict], slugs: frozenset) -> list[tuple[str, str]]:
    """`(id, reason)` for every class whose `family:` is absent or not a family. Pure.

    R180 (2026-09-26): the family was GUESSED by a regex on the id — 213 of 418 classes
    matched two or more families and the first hit won in silence. It is now declared on
    every entry, and this keeps it that way: a class belongs to a family, or it is not in
    the catalogue.
    """
    out = []
    for h in headers:
        fam = (h.get("family") or "").strip()
        if not fam:
            out.append((h["id"], "aucun champ `- family:`"))
        elif fam not in slugs:
            out.append((h["id"], f"`family: {fam}` n'est pas l'une des familles"))
    return out


def _admission(headers: list[dict]) -> int:
    """Une classe NEUVE doit dire pourquoi elle mérite d'exister.

    Pourquoi ce garde, et pourquoi maintenant. Le catalogue a grossi de **365
    classes en sept semaines** — 234 pour le seul mois de septembre 2026, soit
    ~10 par jour. Chacune coûte 15 champs tenus à la main. Et la mesure dit que
    **91 % ne récidivent jamais** : on paie l'écriture d'une classe pour un
    évènement qui n'arrivera pas.

    Étalonné rétroactivement sur les 402 classes existantes :

        récidivé au moins une fois   37  (9 %)
        balayage à ≥ 1 site          38  (9 %)
        balayage à ≥ 2 sites         21  (5 %)
        ADMISES (récidive OU ≥2)     52  (13 %)

    La règle aurait retenu **1 classe sur 8** — de ~10/jour à ~1,3/jour.

    ⚠️ Ce seuil n'est PAS justifié par une corrélation. Le verdict de balayage
    sépare fortement dans les données (0,505 contre 0,112, intervalles disjoints),
    et c'est un leurre : sur les 37 classes à ≥1 site, le balayage précède la
    récidive **0 fois**, la suit 2 fois, et tombe le MÊME JOUR 12 fois. C'est la
    signature de « ça a récidivé, j'ai balayé, j'ai écrit les deux lignes dans le
    même commit ». Rétrospectif, donc inutilisable comme prédicteur.

    Le seuil tient sur un argument de DÉCISION : un défaut présent à deux endroits
    n'est pas un cas isolé, par définition, sans avoir besoin d'une statistique.
    Les classes antérieures à la bascule sont acquises — on ne réécrit pas
    l'histoire, on arrête d'en produire au même rythme.
    """
    # ALL classes, not only the new ones — deliberate (code-critic, 2026-09-26, asked why):
    # every one of the 418 carries a family since R180, so an old class losing it is an edit
    # that broke the catalogue, and the matrix and the family document would silently
    # misfile it. Refusing the whole admission names it on the next commit.
    sans_famille = undeclared_families(headers, _family_slugs())
    if sans_famille:
        for cid, why in sans_famille[:20]:
            print(f"  ⊘  {cid}\n       {why}")
        print(f"\n⊘ {len(sans_famille)} classe(s) sans famille déclarée — une classe entre "
              "comme instance d'une des familles de `error-family-rules.md`, ou pas du tout.")
        return 2
    since = _admission_since()
    if since is None:
        print("▶ admission: aucune date de bascule posée — rien à exiger.\n"
              "   Poser `<!-- admission-since: AAAA-MM-JJ -->` en tête du catalogue.")
        return 0

    neuves = [h for h in headers if (h.get("first_seen") or "") >= since]
    fautives = [(h["id"], _admission_verdict(h.get("admitted")))
                for h in neuves]
    fautives = [(cid, why) for cid, why in fautives if why]

    print(f"▶ admission: bascule au {since} — {len(neuves)} classe(s) neuve(s), "
          f"{len(neuves) - len(fautives)} avec un billet valide")
    if not fautives:
        print("✅ toute classe écrite depuis la bascule justifie son existence")
        return 0
    for cid, why in fautives:
        print(f"  ⊘  {cid}\n       {why}")
    print(f"\n⊘ {len(fautives)} classe(s) neuve(s) sans billet d'admission.\n"
          "  Un défaut corrigé produit un TEST par défaut. Il produit une CLASSE "
          "seulement quand il est daté deux fois, présent à deux endroits, ou qu'il "
          "a causé un dommage en production.")
    return 2

def _fields(headers: list[dict], strict: bool = False) -> int:
    """Schema completeness: does every class say WHY it happened and WHAT ends it?

    Why this is a separate gate from `--coverage`, and not folded into it.
    `--coverage` asks "is this class swept?" — a question about the signature.
    This asks "is this class UNDERSTOOD?" — a question about the two fields the
    signature cannot answer. They fail independently and are fixed by different
    work, so one exit code for both would hide whichever came second.

    Why it exists at all (found 2026-08-03, on the n8n deployment). `/capitalise`
    writes `root_cause` and `long_term_fix`; the catalogue shipped in the payload
    declared neither in its per-class schema; and `--coverage` checked only for a
    signature. So the producer wrote two fields nothing read, into a file whose
    own schema did not list them — and every class in the target repo had 0 of 2,
    while the sweep still reported 9/9 guarded. A field no command checks is not
    filled. This is that command.

    `long_term_fix` is the one that carries the weight: a signature says the class
    is *detectable*, only the fix says it can *stop happening*. `— (the guard IS
    the fix)` is a legitimate answer; a blank is not an answer.

    CLIQUET, 2026-08-04. Cette porte sortait 1 sur 72 classes sur 72 depuis le jour
    où elle a été écrite, et tout le monde avait acté de l'ignorer : un garde
    rouge en permanence ne rapporte plus rien — c'est la règle « mesurer l'EFFET »
    retournée contre le garde lui-même. Elle devient donc un cliquet : elle échoue
    quand la dette GRANDIT (une classe neuve sans les deux champs), elle se
    resserre toute seule quand elle diminue, et `--strict` restitue l'exigence
    absolue pour le jour où le solde est fait. La dette héritée reste affichée à
    chaque passage — visible, comptée, mais elle ne masque plus une régression.
    """
    missing = [(h, [f for f in ("root_cause", "long_term_fix") if not h[f]])
               for h in headers]
    missing = [(h, f) for h, f in missing if f]
    total = len(headers)
    complete = total - len(missing)
    pct = (100 * complete // total) if total else 0
    print(f"▶ fields: {total} classes — {complete} complete ({pct}%) · "
          f"{len(missing)} incomplete")
    if not missing:
        _write_ratchet(0)
        print("\n✅ fields complete — every class states its root cause and its long-term fix")
        return 0

    for h, fields in missing:
        print(f"      {h['id']}  [manque: {', '.join(fields)}]")

    if strict:
        print("\n❌ --strict : toute classe doit porter les deux champs "
              "(`/capitalise` les écrit).")
        return 1

    dette = _read_ratchet()
    if dette is None:                       # premier passage : on gèle l'état du jour
        _write_ratchet(len(missing))
        print(f"\n⚙️  cliquet POSÉ à {len(missing)} — la dette ne pourra plus grandir.")
        return 0
    if len(missing) > dette:
        neuves = len(missing) - dette
        print(f"\n❌ la dette GRANDIT : {len(missing)} incomplètes contre un cliquet "
              f"à {dette} — {neuves} classe(s) écrite(s) sans `root_cause` ni "
              f"`long_term_fix`.\n   Une classe sans correctif long terme est une "
              f"classe dont personne n'a décidé la fin ; elle reviendra, et sa "
              f"signature le rapportera fidèlement.")
        return 1
    if len(missing) < dette:
        _write_ratchet(len(missing))
        print(f"\n✅ dette RÉSORBÉE : {dette} → {len(missing)}. Cliquet resserré — "
              f"il ne se desserrera pas.")
        return 0
    print(f"\n✅ dette stable à {dette} (héritée, antérieure au schéma) — aucune "
          f"classe neuve incomplète. `--fields --strict` pour exiger le solde.")
    return 0


# Le cliquet vit DANS le catalogue, pas dans ce script : c'est le catalogue qui
# porte la dette, et un dépôt qui retélécharge le runner ne doit pas récupérer la
# dette d'un autre. Écrit par le runner lui-même — un nombre que l'humain doit
# penser à baisser après un backfill est un nombre qui reste faux.
_RATCHET = re.compile(r"^<!-- fields-ratchet: (\d+) -->$", re.M)


def _read_ratchet() -> int | None:
    m = _RATCHET.search(_CATALOGUE.read_text(encoding="utf-8"))
    return int(m.group(1)) if m else None


def _write_ratchet(n: int) -> None:
    texte = _CATALOGUE.read_text(encoding="utf-8")
    ligne = f"<!-- fields-ratchet: {n} -->"
    if _RATCHET.search(texte):
        texte = _RATCHET.sub(ligne, texte, count=1)
    else:                                   # après le titre H1, avant tout le reste
        lignes = texte.split("\n")
        i = next((k + 1 for k, ligne_k in enumerate(lignes) if ligne_k.startswith("# ")), 0)
        lignes.insert(i, "\n" + ligne)
        texte = "\n".join(lignes)
    _CATALOGUE.write_text(texte, encoding="utf-8")


# File kinds that can only ever DESCRIBE a defect, and the comment markers that
# do the same job inside code. A hit landing on one of these is a hit on prose.
#
# ⚠️ An extension is NOT enough, and the first version of this guard got it
# wrong in the way it exists to prevent. It marked every `.md` hit as prose and
# went red on three repos over `.claude/commands/sprint.md` and
# `.claude/rules/rex-format.md` — which are CONFIGURATION. An unsubstituted
# `{{PLACEHOLDER}}` in a command file is a real defect, and the guard was calling
# it noise. In this fleet markdown is the language configuration is written in;
# only `.claude/dev-docs/` (the catalogue, the ROADMAP) and markdown OUTSIDE
# `.claude/` describe rather than act.
_PROSE_EXT = {".md", ".rst", ".txt", ".adoc", ".org"}
_MARKERS = {
    ".py": ("#",), ".sh": ("#",), ".bash": ("#",), ".rb": ("#",), ".pl": ("#",),
    ".yml": ("#",), ".yaml": ("#",), ".toml": ("#",), ".cfg": ("#",), ".ini": (";", "#"),
    ".js": ("//", "/*", "*"), ".ts": ("//", "/*", "*"), ".jsx": ("//", "/*", "*"),
    ".tsx": ("//", "/*", "*"), ".java": ("//", "/*", "*"), ".c": ("//", "/*", "*"),
    ".h": ("//", "/*", "*"), ".cpp": ("//", "/*", "*"), ".go": ("//",), ".rs": ("//",),
    ".sql": ("--",), ".lua": ("--",), ".hs": ("--",),
}
_GREP_LIKE = re.compile(r"\b(grep|rg|ack|ag)\b")
_HIT_LINE = re.compile(r"^(?P<path>[^:]+):(?P<num>\d+):(?P<body>.*)$")
# `-q`/`--quiet` prints nothing; `-c` prints counts. Either way the signature
# answers yes/no and refuses to say WHERE — see `_silent` below.
# Short flags CLUSTER: the fleet writes `-rqi`, not `-q -r -i`. Matching a
# cluster and testing membership is the only form that sees it.
_SHORT_CLUSTER = re.compile(r"(?<![\w-])-([a-zA-Z]+)(?![\w-])")
_LONG_SILENT = re.compile(r"--(quiet|silent|count)\b")


def _hit_is_prose(line: str) -> bool | None:
    """Does this hit land on text that merely DESCRIBES the defect?

    Two output shapes are understood, because both occur in the fleet:
      * `path:line:content` (plain grep) — the line itself is read;
      * a bare `path` (`grep -l`) — only the file kind can be judged, so a
        markdown hit is prose and a code hit is left undecided. Half an answer
        is still an answer; guessing the other half would not be.

    Returns None when nothing can be concluded. Unclassifiable is a distinct
    verdict from "fine", and it is reported as such.
    """
    line = line.strip()
    m = _HIT_LINE.match(line)
    if m:
        if _est_doc(m.group("path")):
            return True
        ext = Path(m.group("path")).suffix.lower()
        marqueurs = _MARKERS.get(ext)
        if not marqueurs:               # kind we cannot read: say so, do not guess
            return None
        body = m.group("body").strip()
        return any(body.startswith(mk) for mk in marqueurs)
    # `grep -l` — a path and nothing else. Only the file kind can be judged;
    # a config file hit stays undecided rather than being called noise.
    if line and ":" not in line:
        return True if _est_doc(line) else None
    return None


def _est_doc(chemin: str) -> bool:
    """Is this file DESCRIBING, as opposed to being the thing itself?

    Markdown is this fleet's configuration language, so the extension decides
    nothing on its own. Two places describe: `.claude/dev-docs/` — the catalogue
    and the ROADMAP, which talk *about* the work — and prose files outside
    `.claude/` entirely. Everything else under `.claude/` is an agent, a command
    or a rule: it acts, and a defect in it is a defect.
    """
    # `lstrip("./")` retire un JEU de caractères, donc il mange le point de
    # `.claude` et classe toute la configuration comme documentation. C'est le
    # défaut qui a fait rougir trois dépôts à tort.
    q = chemin.replace("\\", "/")
    while q.startswith("./"):
        q = q[2:]
    if Path(q).suffix.lower() not in _PROSE_EXT:
        return False
    return q.startswith(".claude/dev-docs/") or not q.startswith(".claude/")


def _silent(sig: str) -> bool:
    """Does this signature refuse, by construction, to say what it matched?

    `grep -q` exits 0/1 and prints nothing; `grep -c` prints a count. Both answer
    « is the class touched » and neither answers « on what ». That is not a
    detail: a class going red then becomes unreviewable — nobody can tell a real
    defect from a comment describing one without re-running the command by hand
    and re-deriving what it was supposed to mean.

    Found on the fleet, 2026-08-03: 6 classes across 5 repos, including the two
    that motivated this guard. Their signatures had been narrowed to code
    (`--include=*.py`), which was the right fix, and stayed silent, which keeps
    the fix unverifiable. Reported, never failed — a silent signature is a real
    guard, just one nobody can audit.
    """
    if not _GREP_LIKE.search(sig):
        return False
    if _LONG_SILENT.search(sig):
        return True
    return any(set(m.group(1)) & {"q", "c"} for m in _SHORT_CLUSTER.finditer(sig))


def _prose(classes: list[dict]) -> int:
    """Meta-guard: is a signature catching the DEFECT, or its own description?

    Why this exists (found 2026-08-03, on the n8n deployment). A `deterministic`
    class went red on the comments that explained its own fix. Writing about a
    defect made the guard fire — so the only way to keep CI green was to stop
    documenting, which is the opposite of what a catalogue is for.

    The damage is not one wrong verdict. A deterministic class is CI-blocking by
    contract; one that blocks on a comment teaches everyone that a red audit may
    be noise, and that lesson is applied to the other eight signatures too. This
    guard exists so the catalogue can say which is which, with evidence.

    It only judges signatures that HIT — a green one exposes nothing to classify
    — and only grep-family ones, whose output locates its matches. pytest
    signatures are reported as out of scope rather than silently counted as fine.

    Fails only when EVERY locatable hit of a class is prose: that signature is
    reporting nothing but talk about the defect. A mixed class is reported and
    not failed — it has caught something real, and narrowing it is a judgement
    call about which hits matter, not a verdict this guard can reach.
    """
    detm = [c for c in classes if c["kind"] == "deterministic"]
    scoped = [c for c in detm if _GREP_LIKE.search(c["signature"])]
    out_of_scope = [c for c in detm if c not in scoped]

    all_prose, mixed, unlocatable, muettes = [], [], [], []
    for c in scoped:
        verdict, output = run_signature(c["signature"])
        if verdict != HIT:
            # `BROKEN` n'est pas « pas de hit » : une signature qui ne sait pas
            # répondre ne dit rien sur la prose non plus. `--lint` la nomme.
            continue
        if _silent(c["signature"]):
            muettes.append(c["id"])
            continue
        verdicts = [_hit_is_prose(ln) for ln in output.splitlines()]
        placed = [v for v in verdicts if v is not None]
        if not placed:
            unlocatable.append(c["id"])
        elif all(placed):
            all_prose.append((c["id"], sum(placed), output.splitlines()[:3]))
        elif any(placed):
            mixed.append((c["id"], sum(placed), len(placed)))

    print(f"▶ prose: {len(detm)} deterministic — {len(scoped)} locatable (grep-family) · "
          f"{len(out_of_scope)} out of scope (pytest: their output locates nothing)")
    for cid, n, total in mixed:
        print(f"  ⚠  {cid}: {n}/{total} hits land on comments or docs — "
              f"narrow it to code, or say why those hits count")
    if muettes:
        print(f"  ⊘  SILENT and red — say yes/no, never where: {', '.join(muettes)}\n"
              f"     Drop -q/-c so the class can be triaged without re-deriving the command.")
    if unlocatable:
        print(f"  ?  unclassifiable output (not path:line:text): {', '.join(unlocatable)}")
    if all_prose:
        print("\n❌ signature(s) reporting ONLY prose — they fire on the text that "
              "DESCRIBES the defect, not on the defect:")
        for cid, n, sample in all_prose:
            print(f"      {cid}  ({n} hits, all prose)")
            for ln in sample:
                print(f"        {ln}")
        print("\n   A deterministic class blocks CI by contract. One that blocks on a "
              "comment\n   teaches that a red audit may be noise — and that lesson is "
              "applied to\n   the others. Read code, not text: `--include`, a language-aware "
              "matcher,\n   or at minimum exclude comment lines.")
        return 1
    print("\n✅ prose-clean — no deterministic signature fires on its own description")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Run error-class signatures from the catalogue")
    ap.add_argument("--deterministic", action="store_true",
                    help="Run only kind: deterministic classes; exit 1 on any hit (CI-safe)")
    ap.add_argument("--static", action="store_true",
                    help="Run deterministic classes whose signature is grep-only (no pytest) — "
                         "for the IPC daily sweep (no PG / test env)")
    ap.add_argument("--sweep-verdict", action="store_true",
                    help="Refuser un `swept:` sans verdict lisible, ou qui n'est qu'une "
                         "relance de garde")
    ap.add_argument("--admission", action="store_true",
                    help="Une classe NEUVE doit porter `- admitted:` (récidive/sites/p1)")
    ap.add_argument("--lint", action="store_true",
                    help="Vérifie que chaque signature s'EXÉCUTE (sh -n, pas de gabarit)")
    ap.add_argument("--coverage", action="store_true",
                    help="Meta-guard: fail if any class lacks a signature AND isn't runtime-manual")
    ap.add_argument("--fields", action="store_true",
                    help="Schema completeness (ratchet): fail when the count of classes "
                         "lacking root_cause/long_term_fix GROWS; self-tightens when it shrinks")
    ap.add_argument("--strict", action="store_true",
                    help="With --fields: drop the ratchet and fail on any incomplete class")
    ap.add_argument("--prose", action="store_true",
                    help="Meta-guard: fail if a deterministic signature fires only on comments/docs "
                         "— i.e. on the text that describes the defect instead of the defect")
    ap.add_argument("--all", action="store_true", help="Run every class (default)")
    ap.add_argument("--severity", metavar="P1",
                    help="Only the classes of this severity; ALSO fails on one that has no "
                         "executable guard (no signature, no existing guard file). Nightly: P1.")
    ap.add_argument("--known-unguarded", default="", metavar="ID,ID",
                    help="Frozen debt: unguarded classes already on the roadmap. A NEW one fails; "
                         "one of these that gains a guard must be removed from the list.")
    ap.add_argument("--list", action="store_true", help="List classes and exit")
    ap.add_argument("--no-batch", action="store_true",
                    help="Run each pytest signature in its own invocation (the pre-batching\n                         behaviour). Slower by ~10x; use it to attribute a suspicious batch result.")
    args = ap.parse_args()

    if not _CATALOGUE.exists():
        print(f"❌ catalogue not found: {_CATALOGUE}", file=sys.stderr)
        sys.exit(2)

    text = _CATALOGUE.read_text(encoding="utf-8")
    headers = parse_all_headers(text)
    classes = [c for c in headers if c["signature"]]
    if not headers:
        # « zero classe » et « fichier malforme » sont deux etats DIFFERENTS, et
        # les confondre casse la CI d'un depot neuf des le premier jour : le
        # catalogue y est vide par construction, ce qui n'est pas une erreur.
        # On les distingue par la presence du CONTRAT en tete du gabarit — un
        # fichier qui le porte est bien forme, il n'a simplement rien a dire
        # encore. Trouve le 2026-08-02 en testant la config assemblee sur un
        # depot vierge, avant de la recommander en CI.
        # Le gabarit existe en deux langues — `config-optimale/` en francais,
        # celui du payload en anglais. Ne reconnaitre que la sentinelle francaise
        # faisait sortir 2 (« fichier malforme ») sur un catalogue anglais vide,
        # c'est-a-dire exactement le cas que ce bloc existe pour ne pas confondre.
        if re.search(r"^## (Sch[ée]ma par classe|Per-class schema)", text, re.M):
            print("catalogue vide : 0 classe capitalisée pour l'instant. "
                  "Rien à vérifier, et ce n'est pas une erreur.")
            sys.exit(0)
        print("❌ no classes parsed — check error-classes.md format", file=sys.stderr)
        sys.exit(2)

    if args.admission:
        sys.exit(_admission(headers))

    if args.sweep_verdict:
        sys.exit(_sweep_verdict(headers))

    if args.lint:
        sys.exit(_lint(headers))

    if args.coverage:
        sys.exit(_coverage(headers))

    if args.fields:
        sys.exit(_fields(headers, args.strict))

    if args.prose:
        sys.exit(_prose(classes))

    if args.list:
        skipped = [h for h in headers if not h["signature"]]
        for c in classes:
            print(f"  {c['id']:<44} {c['kind']:<15} {c['status']}")
        print(f"\n{len(classes)} runnable classes "
              f"({sum(c['kind'] == 'deterministic' for c in classes)} deterministic) · "
              f"{len(skipped)} without a signature")
        if skipped:
            print("  no-signature (coverage-tracked): "
                  + ", ".join(f"{h['id']}[{h['kind'] or '∅'}]" for h in skipped))
        sys.exit(0)

    # kind: manual / runtime-manual = never auto-run (need host access, or no static footprint).
    if args.static:
        selected = [c for c in classes
                    if c["kind"] == "deterministic" and "pytest" not in c["signature"]]
        mode = "static"
    elif args.deterministic:
        selected = [c for c in classes if c["kind"] == "deterministic"]
        mode = "deterministic"
    else:
        selected = [c for c in classes if c["kind"] not in ("manual", "runtime-manual")]
        mode = "all"
    unguarded: list[str] = []
    if args.severity:
        selected = [c for c in selected if c.get("severity") == args.severity]
        unguarded = unguarded_classes(headers, args.severity)
        known = {x for x in args.known_unguarded.split(",") if x}
        healed = sorted(known - set(unguarded))
        if healed:   # the list may only shrink: a stale entry would hide a relapse
            print(f"⊘ --known-unguarded cite des classes désormais gardées : {', '.join(healed)} "
                  "— les retirer de la liste")
            sys.exit(1)
        if known:
            print(f"▶ dette figée ({len(known)}) : {', '.join(sorted(known))} — en roadmap, "
                  "tolérée tant qu'elle ne grossit pas\n")
        unguarded = [u for u in unguarded if u not in known]
        mode += f", severity {args.severity}"
    print(f"▶ audit_runner ({mode}): {len(selected)} signatures\n")

    batched: dict[str, tuple[bool, str]] = {}
    individual = selected
    if not args.no_batch:
        batched, individual = run_batched(selected)

    # The signatures are independent read-only checks: run them concurrently, report
    # them in catalogue order. In series, `--static` was the CI's critical path on
    # 2026-09-25 — 20 s of `gold_coverage.py --check` waited behind ~55 s of
    # `check_guards_are_env_independent.py`, which has its own workers.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=_SIGNATURE_WORKERS) as pool:
        pending = {c["id"]: pool.submit(run_signature, c["signature"])
                   for c in selected if c["id"] not in batched}
        verdicts = {cid: f.result() for cid, f in pending.items()}

    hits, broken = [], []
    for c in selected:
        if c["id"] in batched:
            was_hit, output = batched[c["id"]]
            verdict = HIT if was_hit else CLEAN
        else:
            verdict, output = verdicts[c["id"]]
        _telemetry_record("error_classes", c["id"], hit=(verdict == HIT))
        mark = {HIT: "⚠ HIT", BROKEN: "⊘ CASSÉE", CLEAN: "✅"}[verdict]
        print(f"  {mark}  {c['id']}  [{c['kind']}/{c['status']}]")
        if verdict in (HIT, BROKEN):
            (hits if verdict == HIT else broken).append(c["id"])
            for line in output.splitlines()[:6]:
                print(f"        {line}")

    # LES CASSÉES D'ABORD, ET AVEC LEUR PROPRE CODE DE SORTIE.
    #
    # Une signature qui ne sait pas rendre de verdict n'est pas un défaut du produit :
    # c'est un défaut de l'outillage, et le confondre avec une touche envoie chercher
    # un bug là où il n'y en a pas. Le 2026-09-18, une signature au backtick non fermé
    # a bloqué la CI toute une matinée sous l'étiquette « ces touches sont réelles ».
    if broken:
        print(f"\n⊘ {len(broken)} signature(s) n'ont pas pu rendre de verdict : "
              f"{', '.join(broken)}")
        print("  Ce n'est PAS une touche. Remède : `audit_runner.py --lint`, qui nomme "
              "le champ fautif.")
        sys.exit(2)
    if unguarded:
        print(f"\n⊘ {len(unguarded)} classe(s) {args.severity} sans AUCUN garde exécutable "
              f"(ni signature, ni fichier de garde existant) : {', '.join(unguarded)}")
        print("  Une classe critique que rien n'exécute n'est gardée que par la mémoire.")
        sys.exit(1)
    if hits:
        print(f"\n⚠ {len(hits)} class(es) with hits: {', '.join(hits)}")
        if args.deterministic or args.static:
            print("  (deterministic → CI-blocking: these are real, fix or re-triage the signature)")
        else:
            print("  (heuristic sweep → manual triage; nightly non-blocking)")
        sys.exit(1)
    print("\n✅ audit clean")
    sys.exit(0)


if __name__ == "__main__":
    main()
