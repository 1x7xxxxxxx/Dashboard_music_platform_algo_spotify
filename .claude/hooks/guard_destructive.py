#!/usr/bin/env python3
"""
Hook PreToolUse — Guard against destructive Bash commands.

Intercepts Bash tool calls before execution.
- BLOCKING (exit 2): truly irreversible operations that should never run silently
- ADVISORY (exit 0): risky operations that print a warning but are allowed through

Always exits 0 for non-Bash tools and safe commands.

---
rex:
  - date: 2026-04-24
    issue: "Guards SQLite-specific post-migration PG + aucun équivalent DROP SCHEMA / dropdb / alembic destructive downgrade"
    fix: "Retiré rm sensor_data.db + PRAGMA journal_mode; ajouté block DROP SCHEMA + dropdb + ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADE=1; warn alembic downgrade"
    severity: warn
---
"""
import json
import re
import shlex
import subprocess
import sys


# ── Patterns ──────────────────────────────────────────────────────────────────

# Blocking: exit 2 — Claude must explain and get explicit confirmation
_BLOCK_PATTERNS: list[tuple[str, str]] = [
    ("git push --force",        "Force push overwrites remote history — use 'git push' instead"),
    ("git push -f ",            "Force push overwrites remote history — use 'git push' instead"),
    ("git reset --hard",        "Hard reset discards all uncommitted changes permanently"),
    ("git checkout -- .",       "Discards all uncommitted changes in working directory"),
    ("git restore .",           "Discards all uncommitted changes in working directory"),
    ("git clean -f",            "Permanently deletes untracked files"),
    ("docker system prune",     "Removes ALL unused Docker data including named volumes"),
    # `rm -rf /` etait compare en SOUS-CHAINE : il bloquait donc `rm -rf
    # /tmp/scratch`, l'idiome le plus courant et le plus inoffensif. Mesure le
    # 2026-07-30 sur le banc : 8 cellules sur 12 de la variante `arch` sur Opus
    # ont ete bloquees par ce garde, parce qu'Opus construit ses reproductions
    # dans des dossiers jetables (9 cellules sur 12, contre 1 sur 12 pour
    # Sonnet). Le garde cense proteger la racine interdisait le travail.
    #
    # Il devient une expression reguliere : la racine elle-meme, ou un chemin
    # systeme. `/tmp`, `/var/tmp` et tout chemin relatif passent.
    ("DROP TABLE",              "Irreversible PG/SQL table deletion"),
    ("DROP DATABASE",           "Irreversible database deletion"),
    ("DROP SCHEMA",             "Irreversible PG schema deletion (CASCADE loses all tables, alembic_version row, and dependent objects)"),
    ("dropdb ",                 "Drops an entire PostgreSQL database — irreversible"),
    # ── Repo policy: the pre-commit chain is the secret scanner ──────────
    ("git commit --no-verify",   "Skipping pre-commit hooks bypasses secret scanning"),
    ("git commit -n ",           "Skipping pre-commit hooks bypasses secret scanning"),
]

# Regex tier — the seven gates ARCH Ch.17 prescribes. These genuinely need
# regex: the literal-substring tier below cannot express them. A recursive
# delete as root does not contain the literal used by the substring list, a
# double space or a swapped flag order evades a literal match entirely, and a
# download piped into a shell has arbitrary text between the two halves.
#
# Threat model (ARCH p.164): these guard against ACCIDENTS caused by the model
# or by the developer through it. They are not a boundary against an adversary
# who controls the prompt.
_BLOCK_REGEX: list[tuple[str, str]] = [
    (r"curl\s+[^|]*\|\s*(sudo\s+)?(ba|z|k)?sh",
     "Piping a download into a shell executes unreviewed remote code"),
    (r"wget\s+[^|]*\|\s*(sudo\s+)?(ba|z|k)?sh",
     "Piping a download into a shell executes unreviewed remote code"),
    (r"\bsudo\s+rm\b",
     "Recursive delete as root — verify the path outside Claude Code"),
    (r"\brm\s+-[a-z]*[rf][a-z]*\s+(/|~|\$HOME)(\s|/|$)",
     "Recursive delete of a root or home path — catastrophic"),
    # Les chemins SYSTEME, nommes un par un. Ils etaient couverts jusqu'au
    # 2026-07-30 par la sous-chaine `"rm -rf /"` de `_BLOCK_PATTERNS` — qui
    # bloquait du meme coup `rm -rf /tmp/scratch`, l'idiome le plus courant et le
    # plus inoffensif. Mesure sur le banc : 8 cellules sur 12 de la variante
    # `arch` sur Opus bloquees par ce garde, parce qu'Opus construit ses
    # reproductions dans des dossiers jetables (9 sur 12, contre 1 sur 12 pour
    # Sonnet). Le garde cense proteger la racine interdisait le travail.
    #
    # `/tmp`, `/var/tmp` et tout chemin relatif passent maintenant — avec un
    # avertissement, qui reste dans `_WARN_PATTERNS`.
    (r"\brm\s+(-\S+\s+)*/(etc|usr|bin|sbin|lib|lib64|boot|dev|proc|sys|root"
     r"|home|srv|opt)(/|\s|$)",
     "Recursive delete of a system path — catastrophic"),
    (r"\brm\s+(-\S+\s+)*/var/(?!tmp)",
     "Recursive delete under /var — catastrophic"),
    (r"\bmkfs\.",
     "Filesystem creation destroys every byte on the target device"),
    (r"\bdd\b[^\n]*\bof=/dev/",
     "Block-device write destroys the existing filesystem"),
    (r"\bchmod\s+(-[a-zA-Z]+\s+)*777\b",
     "World-writable permissions — never correct on a real path"),
    (r":\s*\(\s*\)\s*\{[^}]*\|[^}]*&[^}]*\}\s*;?\s*:",
     "Fork bomb — exhausts the process table"),
]

# Advisory: exit 0 — prints warning but allows through
_WARN_PATTERNS: list[tuple[str, str]] = [
    ("rm -rf",              "Recursive delete — verify path before proceeding"),
    ("DELETE FROM",         "SQL delete — ensure WHERE clause is present"),
    ("git stash drop",      "Permanently discards stashed changes"),
    ("docker volume rm",    "Removes a Docker volume — data may be lost"),
    ("truncate",            "Truncates file content — verify target path"),
    ("pkill",               "Kills processes — verify target process name"),
    # ── Repo-specific warnings ──────────
    # Alembic and /admin/purge warnings lived here until 2026-08-21. Neither
    # could fire in this repo: ADR-002 rejects Alembic (migrations are plain
    # .sql files) and there is no purge endpoint. A guard that cannot fire is
    # not neutral — it is read as coverage that does not exist.
    ("make migrate",     "Applies EVERY migrations/*.sql against the live database. A migration ahead of its deployed code has already broken collection here "
                          "(class `migration-ahead-of-its-code`, 2026-08-20) — deploy the code first"),
    ("init_db.sql",       "init_db.sql is the fresh-install schema — piping it at a populated database is not idempotent"),
    ("--build",           "Rebuilds the image. Dockerfiles COPY src/ at build time, so a pull without it leaves stale code running (prod incident 2026-06-14)"),
]


# ── Le geste qui efface du travail sans le nommer ─────────────────────────────
#
# `git checkout -- .` et `git restore .` sont bloqués plus haut. La forme qui coûte
# vraiment n'est pas celle-là : c'est **`git checkout -- <un fichier>`**, qui a l'air
# chirurgical. Mesuré DEUX fois dans la séance du 2026-09-10, sur le même geste — défaire
# une mutation de test. La première fois il a détruit un correctif et deux clés i18n ; la
# seconde, la conversion de deux figures et l'élargissement d'un cliquet. Entre les deux
# j'avais ÉCRIT la leçon en mémoire, ce qui n'a rien empêché : une leçon en prose ne
# retient pas un geste réflexe.
#
# Un blocage sec serait faux. Sur un fichier non modifié ce geste est un no-op légitime,
# et c'est l'usage courant. Le garde interroge donc l'état RÉEL du dépôt et ne bloque que
# s'il y a quelque chose à perdre — en nommant quoi. C'est la différence entre un garde
# qu'on contourne et un garde qui apprend quelque chose.
#
# `git stash` fait le même travail sans rien jeter : c'est ce que le message propose.

# ⚠️ **`--` EST OPTIONNEL, et l'exiger a coûté un fichier le 2026-09-18.** Le motif
# d'origine demandait `checkout … -- <chemins>`. La forme que les mains écrivent
# réellement est `git checkout <fichier>`, sans séparateur — c'est celle qui a effacé
# `tests/test_dag_fleet_isolation.py` ce soir-là, en plein milieu d'une séance, après
# une mutation. Sondé ensuite, six orthographes :
#
#     git checkout <fichier>            NON VU  ← le geste qui a détruit le travail
#     git checkout HEAD <fichier>       NON VU
#     git checkout -- <fichier>         vu
#     git restore <fichier>             vu
#     git checkout main                 non vu  (et c'est correct)
#     git checkout -b <branche>         non vu  (et c'est correct)
#
# C'est la TROISIÈME orthographe du même geste, et `test_git_restore_is_the_same_gesture`
# existait déjà avec pour docstring « deux orthographes, un seul effet — en garder une
# seule serait la portée du défaut ». Le garde avait donc nommé sa propre classe et s'y
# est fait prendre : un garde écrit sur la FORME (`--`) et non sur la PROPRIÉTÉ (un
# rétablissement git visant un chemin qui porte du travail non commité).
#
# Rendre `--` optionnel ne crée pas de faux positif, parce que le verdict ne vient PAS
# du motif : `_paths_that_would_lose_work` écarte les drapeaux, puis interroge
# `git status --porcelain -- <chemin>`. `git checkout main` produit donc un chemin qui
# n'existe pas, aucune perte, aucun blocage. Un changement de branche ne devient bloqué
# que s'il existe un fichier SALE portant le nom de la branche — cas où git lui-même
# exige `--` pour lever l'ambiguïté.
_RESTORE_RE = re.compile(
    r"\bgit\s+(?:-C\s+\S+\s+)*"
    r"(?:checkout(?:\s+(?:HEAD|@|[0-9a-f]{7,40}))?\s+(?:--\s+)?|restore\s+)"
    r"(?P<paths>.+)")


def _paths_that_would_lose_work(command: str) -> list[str]:
    """Les chemins visés par un rétablissement git qui portent du travail non commité.

    Rend une liste vide dès que la question ne se pose pas : pas de correspondance, pas
    de dépôt git, chemin propre. Ne lève JAMAIS — ce hook s'exécute avant chaque appel
    Bash, et une exception ici bloquerait tout le travail au lieu d'un seul geste.
    """
    try:
        losses: list[str] = []
        # Une commande composée porte souvent le geste dans un seul de ses segments.
        for segment in re.split(r"&&|\|\||;|\n", command):
            m = _RESTORE_RE.search(segment)
            if not m:
                continue
            # LE GESTE DOIT ÊTRE LA COMMANDE, pas une mention dans une phrase.
            #
            # Ce filtre manquait, et le garde bloquait toute commande dont le TEXTE
            # contenait le geste — y compris `echo` d'une phrase qui l'explique, ou
            # un heredoc qui documente le garde lui-même. Trois commandes bloquées
            # d'affilée le 2026-09-12 en écrivant la classe d'erreur du hook voisin.
            #
            # Et le mode d'échec est pire qu'un simple faux positif : les jetons de
            # la phrase deviennent des chemins passés à `git status`, et l'un d'eux
            # peut être `:` — en syntaxe de pathspec git, cela désigne TOUS les
            # fichiers. Une phrase en prose faisait donc croire au garde que le
            # dépôt entier allait être écrasé.
            try:
                head = shlex.split(segment)
            except ValueError:
                head = segment.split()
            if not any(t.rsplit("/", 1)[-1] == "git" for t in head[:3]):
                continue
            raw = m.group("paths")
            # `--staged` et `--source` ne touchent pas l'arbre de travail.
            if "--staged" in raw or "--source" in raw:
                continue
            try:
                paths = [a for a in shlex.split(raw) if not a.startswith("-")]
            except ValueError:
                paths = raw.split()
            for path in paths:
                out = subprocess.run(
                    ["git", "status", "--porcelain", "--", path],
                    capture_output=True, text=True, timeout=10)
                if out.returncode != 0:
                    continue
                for line in out.stdout.splitlines():
                    if line.startswith("??"):
                        continue  # non suivi : ce geste ne le touche pas
                    # Colonne 2 = arbre de travail. C'est elle qui serait écrasée.
                    if len(line) > 3 and line[1] in "MD":
                        losses.append(line[3:].strip())
        return sorted(set(losses))
    except Exception:  # noqa: BLE001 — un garde qui lève bloquerait chaque commande
        return []


# ── `git clean`, le frère que le garde du rétablissement ne voyait pas ────────
#
# Mesuré le 2026-09-18 en balayant la FAMILLE du geste plutôt que son verbe : sur neuf
# façons d'écraser du travail non commité, cinq étaient bloquées et quatre passaient.
# `git clean -fd` est celle qui appartient sans discussion à la classe — elle supprime
# les fichiers NON SUIVIS, qui ne sont ni dans un commit, ni dans un stash, ni dans le
# reflog. Un test qu'on vient d'écrire et pas encore ajouté est exactement cela.
#
# ⚠️ Le garde du rétablissement ne pouvait pas l'attraper : il ignore délibérément les
# lignes `??` de `git status`, parce qu'un `checkout -- <fichier>` ne touche pas un
# fichier non suivi. `clean` ne touche QUE ceux-là. Deux gestes, une cause, des
# prédicats exactement complémentaires.
_CLEAN_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)*clean\b(?P<flags>[^&|;\n]*)")


def _untracked_that_clean_would_delete(command: str) -> list[str]:
    """Les fichiers non suivis qu'un `git clean` de cette commande supprimerait.

    Vide dès que la question ne se pose pas : pas de `clean`, pas de `-f` (git refuse
    alors tout seul), `--dry-run`/`-n` (il ne supprime rien), rien d'non suivi.
    Ne lève JAMAIS, pour la même raison que son voisin.
    """
    try:
        for segment in re.split(r"&&|\|\||;|\n", command):
            m = _CLEAN_RE.search(segment)
            if not m:
                continue
            try:
                head = shlex.split(segment)
            except ValueError:
                head = segment.split()
            if not any(t.rsplit("/", 1)[-1] == "git" for t in head[:3]):
                continue
            flags = m.group("flags")
            # `-n` peut vivre DANS un groupe de drapeaux courts : `git clean -fdn`
            # porte `-f` et `-n`, et git répond « Would remove ». Chercher un
            # `-n` isolé le ratait, et le garde bloquait la commande même que
            # son message propose pour voir ce qui partirait.
            if re.search(r"(?:^|\s)(?:-\w*n\b|--dry-run\b)", flags):
                continue
            if not re.search(r"(?:^|\s)-\w*f", flags):
                continue  # sans `-f`, git refuse de lui-même
            out = subprocess.run(["git", "status", "--porcelain"],
                                 capture_output=True, text=True, timeout=10)
            if out.returncode != 0:
                continue
            return sorted({ligne[3:].strip() for ligne in out.stdout.splitlines()
                           if ligne.startswith("??")})
        return []
    except Exception:  # noqa: BLE001 — un garde qui lève bloquerait chaque commande
        return []


# ── Le geste qui se tue lui-même, et emporte la suite de la ligne ─────────────
#
# `pkill -f "<motif>"` compare le motif à la ligne de commande de CHAQUE processus —
# y compris celle du shell qui l'exécute, puisqu'elle CONTIENT le motif. Le shell se
# suicide donc systématiquement, sort en 144, et **tout ce qui suit sur la ligne ne
# part jamais**.
#
# Mesuré TROIS fois dans la séance du 2026-09-12, à chaque fois avec le même dégât :
# la commande d'après — celle qui relançait la suite, celle qui écrivait le script,
# celle qui listait ce qui restait — n'a pas tourné, et le shell a rendu un code
# d'erreur qui ressemblait à un échec de la cible. Deux fois j'ai cru que le kill
# avait raté ; il avait réussi, c'est moi qui étais mort.
#
# Le garde ne bloque PAS un `pkill -f` seul en fin de ligne : là, se tuer après avoir
# tué est sans conséquence. Il bloque quand quelque chose suit, parce que c'est
# exactement le cas où le silence coûte.
#
# La forme sûre ne passe pas par un motif qui se contient lui-même :
#     ps -eo pid,cmd | grep "[p]ytest tests/" | awk '{print $1}' \
#       | while read p; do kill "$p"; done
# Le crochet `[p]` fait que la ligne du shell ne correspond plus au motif cherché.

_PKILL_RE = re.compile(r"\bpkill\s+(?:-\w+\s+)*-\w*f\w*\s+(?P<pat>\S+)")

# ── La SONDE en lecture, ajoutee le 2026-09-16 ───────────────────────────────
#
# Le garde du dessous ne connaissait que `pkill`. La CAUSE n'est pourtant pas le verbe :
# c'est qu'un motif passe a un outil qui compare des lignes de commande se trouve
# LUI-MEME, parce que la ligne du shell qui le porte le contient par construction.
# `pgrep -f` a exactement la meme cause, et j'ai reproduit la classe TROIS FOIS le
# 2026-09-16 — sur une classe que ce depot avait deja ecrite le 2026-09-12, avec son
# hook. La portee du garde etait le defaut, pas la connaissance.
#
# La consequence differe et c'est ce qui l'a rendue invisible : `pkill` tue le shell
# (code 144, bruyant) ; `pgrep` dans un `until` rend toujours VRAI, donc la boucle ne
# sort jamais. Silencieuse, elle passe pour une attente normale — trois ont tourne des
# heures en surveillant des suites deja finies, et m'ont fait conclure quatre fois
# qu'une suite etait morte alors qu'elle tournait.
_PGREP_RE = re.compile(r"""\bpgrep\s+(?:-\w+\s+)*-\w*f\w*\s+(?P<pat>"[^"]*"|'[^']*'|\S+)""")


def _probe_would_find_its_own_shell(command: str) -> str | None:
    """Le motif d'un `pgrep -f` qui se contient lui-meme, ou None.

    Meme cause que `_pkill_would_kill_its_own_shell`, autre consequence : ici rien ne
    meurt, la boucle ne sort simplement jamais. C'est PIRE a diagnostiquer, parce qu'une
    attente qui dure ressemble a une attente normale.

    Un motif deja crante (`"[p]ytest"`) est la forme sure : verifie par execution le
    2026-09-16, `grep -c "[x]marker"` rend 0 alors que sa propre ligne porte le motif
    entre crochets.
    """
    try:
        for segment in re.split(r"&&|\|\||;|\n", _sans_heredocs(command)):
            m = _PGREP_RE.search(segment)
            if not m:
                continue
            try:
                head = shlex.split(segment)
            except ValueError:
                head = segment.split()
            if not any(t.lstrip("(").rsplit("/", 1)[-1] == "pgrep" for t in head[:3]):
                continue
            pattern = m.group("pat").strip("\"'")
            if "[" in pattern:
                # Crante : sur que si le texte n'apparait pas AILLEURS en clair sur la
                # ligne. Le 2026-09-22, `(pgrep -f "[s]treamlit run" && echo deja) ||
                # (nohup … streamlit run …)` a conclu « deja lance » sur sa propre
                # relance. Meme evaluation que `_grep_pattern_matches_its_own_line`.
                full = _sans_heredocs(command)
                at = full.find(pattern)
                rest = full[:at] + full[at + len(pattern):] if at >= 0 else full
                try:
                    if not re.search(pattern, rest):
                        continue
                except re.error:
                    continue
            return pattern
    except Exception:  # noqa: BLE001 — un garde qui leve bloquerait chaque commande
        return None
    return None


def _pkill_would_kill_its_own_shell(command: str) -> str | None:
    """Le motif d'un `pkill -f` suivi d'autre chose sur la même ligne, ou `None`.

    Ne lève jamais : ce hook précède chaque appel Bash, et une exception y bloquerait
    tout le travail au lieu d'un seul geste.
    """
    try:
        # ⚠️ `_sans_heredocs` MANQUAIT ICI, et seulement ici : les deux autres
        # détecteurs l'appliquaient déjà. Mesuré le 2026-09-16 — ce garde a bloqué la
        # commande qui ÉCRIVAIT la portée de sa propre classe, la prose citant `pkill -f`
        # dans un corps de heredoc. CLAUDE.md décrit exactement ce cas (« écrire SUR un
        # défaut déclenche le garde du défaut », trois commandes bloquées le
        # 2026-09-12) et le correctif n'avait été appliqué qu'à DEUX des trois lecteurs.
        # Un correctif qui ne balaie pas laisse la classe vivante à côté.
        segments = re.split(r"&&|\|\||;|\n", _sans_heredocs(command))
        for i, segment in enumerate(segments):
            m = _PKILL_RE.search(segment)
            if not m:
                continue
            # LE GESTE DOIT ÊTRE LA COMMANDE, pas un mot dans un argument.
            #
            # Sans ce filtre, le garde bloque toute MENTION du geste — le test qui
            # le vérifie, la documentation qui l'explique, l'édition du hook
            # lui-même. Il s'est bloqué ainsi à sa première utilisation, le
            # 2026-09-12, trois commandes d'affilée, et le correctif n'a pas pu
            # être écrit tant que la cause n'était pas comprise. C'est
            # `a-textual-guard-is-blind`, commis en écrivant le garde d'à côté.
            try:
                head = shlex.split(segment)
            except ValueError:
                head = segment.split()
            # `sudo`, `time`, `nohup`… peuvent précéder ; au-delà de trois jetons
            # ce n'est plus la commande de tête.
            if not any(t.rsplit("/", 1)[-1] == "pkill" for t in head[:3]):
                continue
            # Rien après ? Se tuer en dernier ne coûte rien.
            if not any(seg.strip() for seg in segments[i + 1:]):
                continue
            pattern = m.group("pat").strip("\"'")
            # Un motif qui ne peut pas se contenir lui-même (crochet à la grep) est
            # déjà la forme sûre — on ne crie pas dessus.
            if "[" in pattern:
                continue
            return pattern
    except Exception:  # noqa: BLE001 — un garde qui lève bloquerait chaque commande
        return None
    return None


# ── Le crochet ne suffit pas, ajoute le 2026-09-24 ───────────────────────────
#
# La forme sure que ce hook RECOMMANDE — `ps … | grep "[s]treamlit run app.py"` — m'a
# tue le shell le 2026-09-24, exit 144, sur cette ligne :
#
#     pid=$(ps -eo pid,args | grep "[s]treamlit run src/dashboard/app.py" | awk …);
#     kill $pid; sleep 2; nohup .venv/bin/streamlit run src/dashboard/app.py … &
#
# Le crochet empeche le motif de se trouver dans SA PROPRE ecriture. Il n'empeche pas
# qu'il se trouve AILLEURS sur la ligne : la relance portait le texte en clair, donc la
# ligne du shell correspondait, `kill` l'a tue, et la relance n'est jamais partie.
# La propriete n'est pas « le motif porte un crochet » : c'est « le motif correspond a
# la ligne de commande qui l'execute ». On l'evalue donc comme grep le ferait : sur la
# ligne entiere, privee de la seule ecriture du motif.
_GREP_PAT_RE = re.compile(r"""\bgrep\s+(?:-\w+\s+)*(?P<q>["'])(?P<pat>.+?)(?P=q)""")


def _a_kill_follows(segments: list[str]) -> int | None:
    """L'indice du premier segment dont la COMMANDE est `kill`/`pkill`, ou None."""
    for i, segment in enumerate(segments):
        try:
            head = shlex.split(segment)
        except ValueError:
            head = segment.split()
        if any(t.rsplit("/", 1)[-1] in ("kill", "pkill") for t in head[:3]):
            return i
        # `… | xargs kill` : le `|` ne coupe pas un segment, la tete est `ps`.
        if re.search(r"\|\s*xargs\s+(?:-\S+\s+)*kill\b", segment):
            return i
    return None


def _grep_pattern_matches_its_own_line(command: str) -> str | None:
    """Le motif d'un `grep` qui trouvera la ligne du shell, sur une ligne qui tue
    puis continue — ou None. Ne leve jamais."""
    try:
        text = _sans_heredocs(command)
        segments = [s for s in re.split(r"&&|\|\||;|\n", text)]
        k = _a_kill_follows(segments)
        if k is None or not any(s.strip() for s in segments[k + 1:]):
            return None
        for m in _GREP_PAT_RE.finditer(text):
            # Le danger n'existe que si grep lit la LISTE DES PROCESSUS : un grep sur
            # un fichier de log ne verra jamais la ligne du shell (faux positif mesure
            # le 2026-09-24 par le balayage de cette classe).
            amont = re.split(r"&&|\|\||;|\n|\$\(", text[:m.start()])[-1]
            if not re.search(r"(?:^|[\s'\"(])ps\s", amont):
                continue
            pattern = m.group("pat")
            rest = text[:m.start("pat")] + text[m.end("pat"):]
            try:
                if re.search(pattern, rest):
                    return pattern
            except re.error:
                continue
    except Exception:  # noqa: BLE001 — un garde qui leve bloquerait chaque commande
        return None
    return None


# ── Detection ─────────────────────────────────────────────────────────────────

# ── Un verdict avale par un tube, puis commite quand meme ────────────────────
#
# Mesure le 2026-09-17, sur cette ligne exacte :
#
#     pytest … -q 2>&1 | tail -3 && git add -A && git commit … && git push
#
# La suite etait ROUGE. `tail` a rendu 0, donc le `&&` a laisse passer, et le rouge
# est parti sur `main`. Le texte de l'echec etait a l'ecran, sous mes yeux, dans la
# sortie de la meme commande — ce n'est pas une erreur de lecture, c'est le shell qui
# a decide a ma place : **un tube rend le code du DERNIER etage**, jamais celui de
# l'etage qui portait le verdict.
#
# Pourquoi un garde et pas une note : c'est un idiome de frappe, pas un raisonnement.
# Il se retape par reflexe a chaque fois qu'on veut abreger une sortie longue, et ce
# depot a mesure trois fois qu'une note ne retient pas un reflexe.
# La TETE d'un etage, comparee a un ensemble : `python` et `python3` couvrent
# `python -m pytest`, dont la tete n'est pas `pytest`.
_VERIFIERS = frozenset({"pytest", "ruff", "mypy", "make", "python", "python3",
                       "audit_runner.py", "validate_rex.py"})


def _verdict_swallowed_by_a_pipe(command: str) -> str | None:
    """Un verdict tube dans un filtre, PUIS une livraison dans la meme chaine `&&`.

    Rend le segment de verification fautif, ou None.

    Ce qu'il ne bloque PAS, et c'est ce qui le rend tenable :
      * un verdict tube SANS livraison derriere — la forme de lecture normale ;
      * une livraison SANS verdict devant — un commit ordinaire ;
      * `set -o pipefail` ou `${PIPESTATUS`, qui reparent le code de sortie ;
      * un `;` a la place du `&&` : la livraison ne PRETEND alors rien du verdict.
    """
    texte = _sans_heredocs(command)
    if "pipefail" in texte or "PIPESTATUS" in texte:
        return None
    # ⚠️ **On decoupe des JETONS, jamais du texte.** La premiere version de ce garde
    # coupait la chaine sur `|` et `&&` avec une expression reguliere : elle s'est
    # bloquee elle-meme sur `echo "pytest | tail && git commit est un piege"`, ou les
    # trois marques vivent DANS un argument. C'est la classe deja nommee de ce depot,
    # `a-bash-hook-that-blocks-the-prose-about-the-gesture`, attrapee ici par son propre
    # cas de test. `shlex` garde une chaine citee en UN jeton, donc un operateur n'est
    # un operateur que s'il en est un.
    #
    # ⚠️ Et `shlex.split` NE SUFFIT PAS : il coupe sur les blancs, donc
    # `make test|tail -3&&git commit` lui rend `['make','test|tail','-3&&git',…]` et le
    # garde ne voyait AUCUN operateur — il passait au vert sur la forme sans espaces.
    # Trouve le 2026-09-17 en mutant : deux mutations sur trois sont d'abord passees
    # VERTES, et c'est ce vert-la qui a revele le trou. `punctuation_chars=True` fait de
    # `|`, `&&` et `;` des jetons a part entiere, sans toucher a ce qui est cite.
    try:
        analyseur = shlex.shlex(texte, posix=True, punctuation_chars=True)
        analyseur.whitespace_split = True
        jetons = list(analyseur)
    except ValueError:
        return None
    etapes: list[list[str]] = [[]]
    ops: list[str] = []
    for jeton in jetons:
        if jeton in ("|", "&&", "||", ";", "&", "|&"):
            ops.append(jeton)
            etapes.append([])
        else:
            etapes[-1].append(jeton)
    if "&&" not in ops:
        return None

    def _tete(argv: list[str]) -> str:
        i = 0
        while i < len(argv) and (argv[i].lower() in _PREFIXES_A_SAUTER or "=" in argv[i]):
            i += 1
        return argv[i].rsplit("/", 1)[-1].lower() if i < len(argv) else ""

    for i, argv in enumerate(etapes):
        if not argv or i >= len(ops) or ops[i] != "|":
            continue
        # L'etage qui porte le VERDICT est celui a GAUCHE du tube ; les suivants ne font
        # que filtrer. Un `| tee` conserve la sortie mais rend quand meme le code de
        # `tee` : aucun filtre n'est exempte, volontairement.
        if _tete(argv) not in _VERIFIERS:
            continue
        # Une LIVRAISON apres le tube, atteinte par un `&&` — donc qui PRETEND dependre
        # du verdict. Apres un `;` elle ne pretend rien, et n'est pas bloquee.
        #
        # ⚠️ On TRAVERSE les etages de filtrage. La premiere version s'arretait au
        # premier `ops[j-1] != "&&"`, donc au tube lui-meme : elle rendait None sur les
        # QUATRE cas qu'elle existe pour attraper. Un garde qui rate la forme reellement
        # tapee ne garde rien — trouve en jouant les cas, pas en relisant.
        vu_et = False
        for j in range(i + 1, len(etapes)):
            lien = ops[j - 1]
            if lien == "|" and not vu_et:
                continue          # encore un filtre du meme tube
            if lien != "&&":
                break             # `;` ou `||` : la livraison ne pretend plus rien
            vu_et = True
            tete = _tete(etapes[j])
            reste = etapes[j][1:] if etapes[j] else []
            if tete == "git" and reste and reste[0] in ("commit", "push", "tag"):
                return " ".join(argv)
            if tete == "gh" and reste[:2] in (["pr", "create"], ["release", "create"]):
                return " ".join(argv)
    return None



def _serial_full_suite(command: str) -> str | None:
    """Une suite COMPLÈTE lancée sans parallélisme. Rend le segment fautif, ou None.

    Ce n'est pas un geste destructeur — c'est un geste qui coûte QUINZE MINUTES, et que
    rien n'empêchait. Mesuré le 2026-09-16 : `pytest tests/ -q` en série rend 888, 921 et
    963 s sur ce poste ; `make test` pose `-n auto --dist loadgroup`. La forme nue a été
    lancée SIX FOIS dans une seule séance, parce que `CLAUDE.md` la documentait ainsi.

    Pourquoi un hook et pas la doc corrigée : la doc EST corrigée, et ce dépôt a mesuré
    trois fois qu'une note ne retient pas un geste réflexe — `checkout` deux fois le
    2026-09-10, `kill` trois fois le 2026-09-12, et l'édition-pendant-la-suite trois fois
    le 2026-09-16, la leçon étant écrite entre chaque.

    Ce qu'elle NE bloque PAS, et c'est ce qui la rend tenable :
      * un fichier ou une liste de fichiers (`pytest tests/test_x.py`) — le geste courant ;
      * tout ce qui porte déjà `-n` ;
      * `--store-durations`, qui doit tourner en SÉRIE à dessein (`make test-durations`).
    """
    for segment in re.split(r"(?:&&|\|\||\||;|\n)", _sans_heredocs(command)):
        segment = segment.strip()
        if not segment or segment.startswith("#"):
            continue
        try:
            argv = shlex.split(segment)
        except ValueError:
            continue
        # ⚠️ `timeout` et `nice` PRENNENT UN ARGUMENT, contrairement aux préfixes de
        # `_PREFIXES_A_SAUTER`. Sans ce traitement, `timeout 1700 … pytest tests/`
        # échappait au garde — et c'est exactement la forme que j'ai lancée six fois le
        # 2026-09-16. Un garde qui rate la forme réellement employée ne garde rien : la
        # liste de préfixes décrivait les gestes d'un AUTRE garde, pas ceux-ci.
        i = 0
        while i < len(argv):
            tete = argv[i].lower()
            if tete in _PREFIXES_A_SAUTER or "=" in argv[i]:
                i += 1
            elif tete in {"timeout", "nice", "ionice", "stdbuf", "taskset"}:
                i += 1
                while i < len(argv) and (argv[i].startswith("-")
                                         or argv[i].replace(".", "").rstrip("smhd").isdigit()):
                    i += 1
            else:
                break
        argv = argv[i:]
        if not argv:
            continue
        head = argv[0].lower()
        is_pytest = head.endswith("pytest") or (
            ("python" in head or head.endswith(".exe")) and "pytest" in argv[:4])
        if not is_pytest:
            continue
        # ⚠️ `rest` commence APRES le jeton `pytest`, jamais apres argv[0]. Sinon le
        # `-m` de `python -m pytest` est pris pour le `-m` de pytest (un filtre par
        # MARQUEUR) et toute la suite s'exempte elle-meme. Meme drapeau, deux sens,
        # deux programmes — et le garde a passe au vert sur son propre cas de test.
        try:
            rest = argv[argv.index("pytest") + 1:]
        except ValueError:
            rest = argv[1:]
        # L'ARBRE ENTIER, pas un fichier : l'argument est `tests` ou `tests/` tel quel.
        whole_tree = any(a.rstrip("/") == "tests" for a in rest if not a.startswith("-"))
        if not whole_tree:
            continue
        if any(a == "-n" or a.startswith("-n") or a.startswith("--numprocesses")
               for a in rest):
            continue
        # `--store-durations` doit tourner en SERIE a dessein (`make test-durations`).
        # `--collect-only` ne lance aucun test : quelques secondes, et c'est le geste
        # normal pour compter ou lister. Exempte apres que ce garde m'a bloque dessus —
        # un garde qui attrape un geste bon marche apprend a etre contourne.
        if "--store-durations" in rest or "--collect-only" in rest or "--co" in rest:
            continue
        # ⚠️ Une execution FILTREE n'est pas la suite complete. Ce garde m'a bloque le
        # 2026-09-16 sur `pytest tests/ -k "error_class or roadmap"` — une trentaine de
        # fichiers, pas 6 700 tests. C'est un defaut de PORTEE dans le garde lui-meme,
        # de la meme famille que celui qu'il documente : j'avais ecrit la regle sur la
        # CIBLE (`tests/`) au lieu de l'ecrire sur le GESTE (« lancer toute la suite »).
        # Trouve par le garde en me bloquant, ce qui est le seul moment ou ca ne coute
        # rien.
        if any(a in ("-k", "-m", "--lf", "--last-failed", "--ff", "--failed-first",
                     "--deselect") or a.startswith(("-k=", "-m=", "--deselect="))
               for a in rest):
            continue
        return segment
    return None


def check_command(cmd: str) -> tuple[str, str] | None:
    """
    Returns (level, message) if the command matches a dangerous pattern.
    level is 'block' or 'warn'. Returns None if safe.
    """
    # Le verdict avale par un tube d'abord : il ne detruit rien et il ne coute pas de
    # temps — il fait LIVRER un rouge en croyant livrer un vert, ce qui est pire.
    avale = _verdict_swallowed_by_a_pipe(cmd)
    if avale:
        return ("block",
                f"`{avale}` est tube dans un filtre, et une LIVRAISON suit dans la meme "
                "chaine `&&`. Un tube rend le code du DERNIER etage : le verdict de "
                "cette verification est jete, et `&&` laissera passer meme si elle est "
                "ROUGE.\n"
                "   Arrive le 2026-09-17 sur ce depot : une suite rouge poussee sur "
                "`main`, le texte de l'echec affiche a l'ecran dans la meme sortie.\n"
                "   Formes sures :\n"
                "     • separer : lancer la verification, LIRE, puis commiter dans un "
                "second appel ;\n"
                "     • ou reparer le code de sortie : set -o pipefail; <cmd> | tail -3\n"
                "     • ou n'affirmer rien : remplacer `&&` par `;` devant la livraison.")

    # La suite en SÉRIE d'abord : elle ne détruit rien, elle vole quinze minutes, et
    # c'est le seul de ces gardes dont la forme sûre est plus COURTE à taper.
    serial = _serial_full_suite(cmd)
    if serial:
        return ("block",
                "cette commande lance la suite COMPLÈTE en SÉRIE — elle perd "
                "`-n auto --dist loadgroup`, que les cibles du Makefile posent. Mesuré "
                "le 2026-09-16 sur ce poste : 888, 921 et 963 s, soit ~15 min.\n"
                "Ce que tu veux est presque toujours l'une de ces trois :\n"
                "  make test-changed   # les tests atteignables depuis le diff — SECONDES\n"
                "  make test-fast      # tout sauf les documents\n"
                "  make test           # la barrière avant de livrer, drapeaux de la CI\n"
                "Un fichier précis n'est PAS bloqué : "
                "`.venv/bin/python -m pytest tests/test_x.py -q`.")

    # Le suicide de shell d'abord : il ne détruit pas de fichier, mais il fait
    # DISPARAÎTRE en silence tout ce qui suit, ce qui est plus dur à voir.
    probing = _probe_would_find_its_own_shell(cmd)
    if probing:
        return ("block",
                f"`pgrep -f {probing}` va se trouver LUI-MEME : la ligne de commande du "
                "shell qui l'execute contient ce motif, par construction.\n"
                "   Dans une boucle d'attente, il rend donc toujours vrai et la boucle "
                "NE SORT JAMAIS — silencieusement. Trois ont tourne des heures le "
                "2026-09-16 en surveillant des suites deja finies, et m'ont fait "
                "conclure QUATRE FOIS qu'une suite etait morte alors qu'elle tournait.\n"
                "   Formes sures :\n"
                "     • attendre une tache de fond : la notification arrive toute seule ;\n"
                f"     • sonder sans se contenir : ps -eo pid,args | grep \"[{probing[:1]}]{probing[1:]}\"\n"
                "     • ou lire l'etat ailleurs : tail -3 .pytest-last.log")

    suicidal = _pkill_would_kill_its_own_shell(cmd)
    if suicidal:
        return ("block",
                f"`pkill -f {suicidal}` va tuer le shell qui l'exécute : sa propre "
                "ligne de commande CONTIENT ce motif. Tout ce qui suit sur cette "
                "ligne ne partira jamais, et le shell sortira en 144 — un code qui "
                "ressemble à un échec de la cible. Arrivé trois fois le 2026-09-12.\n"
                "Forme sûre, où le motif ne se contient plus lui-même :\n"
                f"  ps -eo pid,cmd | grep \"[{suicidal[:1]}]{suicidal[1:]}\" "
                "| awk '{print $1}' | while read p; do kill \"$p\"; done")
    trouve = _grep_pattern_matches_its_own_line(cmd)
    if trouve:
        return ("block",
                f"`grep \"{trouve}\"` trouvera la ligne du shell qui l'execute : ce texte "
                "y figure AILLEURS, en clair — le crochet n'empeche que l'auto-"
                "correspondance de sa propre ecriture. Le `kill` qui suit tuera donc ce "
                "shell (exit 144) et la suite de la ligne ne partira pas. Arrive le "
                "2026-09-24 : une relance de Streamlit ecrite sur la meme ligne.\n"
                "Forme sure : tuer dans un appel, relancer dans le suivant — ou tuer par "
                "PID connu (celui d'une tache de fond).")
    # Puis le garde à ÉTAT. Il ne bloque que si du travail serait réellement perdu,
    # et son message peut NOMMER les fichiers — ce qu'aucun tier littéral ne peut faire.
    lost = _paths_that_would_lose_work(cmd)
    if lost:
        listing = ", ".join(lost[:6]) + (f" (+{len(lost) - 6})" if len(lost) > 6 else "")
        return ("block",
                "cette commande DÉTRUIRAIT du travail non commité : "
                f"{listing}. Ces modifications ne sont dans aucun commit ni aucun stash "
                "— rien ne les rendra. Si le but est de défaire une mutation de test, le "
                "geste sûr est `git stash && git stash drop`, ou commiter d'abord. Deux "
                "correctifs ont été perdus par cette commande le 2026-09-10, à quelques "
                "heures d'intervalle, sur ce même geste.")
    perdus = _untracked_that_clean_would_delete(cmd)
    if perdus:
        listing = ", ".join(perdus[:6]) + (f" (+{len(perdus) - 6})" if len(perdus) > 6 else "")
        return ("block",
                "ce `git clean` SUPPRIMERAIT des fichiers non suivis : "
                f"{listing}. Ils ne sont dans aucun commit, aucun stash, aucun reflog — "
                "rien ne les rendra. Un test ou un script qu'on vient d'écrire et pas "
                "encore `git add` est exactement dans ce cas. Si le but est de voir ce "
                "qui partirait : `git clean -nd`. Si c'est de le garder : `git add -A` "
                "d'abord, ou `git stash -u`.")
    # Regex tier next: it expresses the dangerous shapes the literal tier cannot.
    for pattern, message in _BLOCK_REGEX:
        if re.search(pattern, cmd, re.IGNORECASE):
            return ("block", message)
    for pattern, message in _BLOCK_PATTERNS:
        if _is_the_command_of_a_segment(cmd, pattern):
            return ("block", message)
    for pattern, message in _WARN_PATTERNS:
        if _is_the_command_of_a_segment(cmd, pattern):
            return ("warn", message)
    return None



# ── Le geste doit etre la COMMANDE de son segment, jamais un mot dans un argument ──
#
# Ce niveau comparait une SOUS-CHAINE sur la commande entiere :
# `if pattern.lower() in cmd_lower`. Il bloquait donc tout ce qui MENTIONNE le geste —
# un heredoc qui ecrit un script, un message de commit qui explique un correctif, une
# chaine Python entre guillemets.
#
# Mesure le 2026-09-16 : trois commandes bloquees d'affilee dans la meme seance, toutes
# en train d'ECRIRE ou de DOCUMENTER un retour arriere, aucune en train d'en faire un.
# Le depot avait deja nomme la classe (`a-bash-hook-that-blocks-the-prose-about-the-gesture`)
# et l'avait corrigee pour ses gardes A ETAT (`shlex.split` par segment, lignes 168 et
# 244) — mais pas pour le niveau litteral, qui est celui qu'on lit en premier.
#
# La question posee ici est structurelle : dans un segment de shell, les PREMIERS mots
# sont-ils exactement ceux du motif ? Le corps d'un heredoc appartient au segment du
# `cat`, dont l'argv commence par `cat` — il ne peut donc plus declencher.
_PREFIXES_A_SAUTER = {"sudo", "env", "nohup", "time", "command", "exec", "rtk", "proxy"}


def _sans_heredocs(command: str) -> str:
    """Retire le CORPS des heredocs — c'est de la donnee, jamais une commande.

    Sans ca, decouper sur les retours a la ligne transforme chaque ligne du corps en
    segment : `cat > x.sh <<EOF` suivi de `git reset --hard $before` faisait croire au
    garde qu'on lancait un retour arriere, alors qu'on ECRIVAIT un script qui en
    contient un. Mesure le 2026-09-16 : c'est le dernier des trois blocages de la
    seance, et le plus tenace.
    """
    lignes = command.split("\n")
    sortie, i = [], 0
    while i < len(lignes):
        ligne = lignes[i]
        sortie.append(ligne)
        m = re.search(r"<<-?\s*[\"\']?([A-Za-z_][A-Za-z0-9_]*)[\"\']?", ligne)
        i += 1
        if not m:
            continue
        delim = m.group(1)
        while i < len(lignes) and lignes[i].strip() != delim:
            i += 1                      # le corps est saute, pas analyse
        if i < len(lignes):
            i += 1                      # et le delimiteur de fin aussi
    return "\n".join(sortie)


def _is_the_command_of_a_segment(command: str, pattern: str) -> bool:
    """Le motif est-il la commande d'un segment, et non un mot dans un argument ?"""
    besoin = pattern.lower().split()
    if not besoin:
        return False
    for segment in re.split(r"(?:&&|\|\||\||;|\n)", _sans_heredocs(command)):
        segment = segment.strip()
        if not segment or segment.startswith("#"):
            continue
        try:
            argv = shlex.split(segment)
        except ValueError:          # guillemets non fermes : on retombe sur le texte,
            argv = segment.split()  # prudemment — mieux vaut un faux positif qu'un trou
        # `sudo git …`, `VAR=1 git …` : on saute ce qui precede la vraie commande
        i = 0
        while i < len(argv) and (argv[i].lower() in _PREFIXES_A_SAUTER or "=" in argv[i]):
            i += 1
        tete = [a.lower() for a in argv[i:i + len(besoin)]]
        if tete == besoin:
            return True
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    result = check_command(command)
    if result is None:
        sys.exit(0)

    level, message = result

    if level == "block":
        # stderr, PAS stdout : le contrat PreToolUse remonte stderr. Ecrit sur stdout,
        # ce bloc etait avale — l'outil rapportait « No stderr output » et l'appelant
        # voyait une porte fermee SANS raison. Meme defaut, meme correctif que
        # `pre_commit_scan.py` le 2026-09-16.
        print(
            f"🚫 BLOCKED — Destructive command detected:\n"
            f"   Command : {command[:120]}\n"
            f"   Reason  : {message}\n"
            f"   Action  : Explain the intent and request explicit user confirmation before retrying.",
            file=sys.stderr,
        )
        sys.exit(2)
    else:
        print(
            f"⚠️  WARNING — Risky command:\n"
            f"   Command : {command[:120]}\n"
            f"   Reason  : {message}\n"
            f"   Proceeding — verify this is intentional."
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
