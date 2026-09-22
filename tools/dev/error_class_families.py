#!/usr/bin/env python3
"""Regrouper les 287 classes d'erreur en familles, sans toucher à une seule entrée.

Type: Utility
Uses: re — rien d'autre. Pas de base, pas d'import de `src/`.
Triggers: `make error-families`, CI step 8
Depends on: .claude/dev-docs/error-classes.md
Persists in: .claude/dev-docs/error-class-families.md

Why this exists
---------------
287 classes, zéro famille. À ce volume le catalogue cesse d'être consultable : on
n'y cherche plus « ai-je déjà vu cette forme ? », on y cherche un nom qu'on a en
tête. Un défaut de la même famille se re-découvre donc de zéro — c'est arrivé le
2026-09-12 avec `two-generations-of-rows-in-one-fact-table`, dont la leçon était
écrite depuis des semaines dans un commentaire et dans une classe voisine.

Une famille n'est PAS un mot-clef
---------------------------------
Chaque famille porte une **question** — celle qu'on se pose devant du code, pas
celle qui décrit le bug après coup. C'est la question qui a de la valeur : elle se
pose avant que le défaut existe. Le classement se fait par une règle explicite,
écrite à côté de la famille, et **la règle est publiée dans le document** pour
qu'un lecteur puisse contester un rattachement sans lire ce script.

Ce que ce document ne fait pas
-------------------------------
Il ne modifie aucune des 287 entrées. Pas de champ `family:`, pas de
réécriture — le catalogue est append-only et le restera. Si cette taxonomie tient
six semaines, la question d'un champ se posera ; pas avant.

Une classe qui ne tombe dans aucune famille est **listée et comptée**, et ce
compte est un cliquet : il ne peut que baisser. Une taxonomie qui laisse un tiers
du catalogue dehors décrit une opinion, pas le catalogue.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".claude" / "dev-docs" / "error-classes.md"
DOC = ROOT / ".claude" / "dev-docs" / "error-class-families.md"

# (slug, la QUESTION qu'on se pose devant le code, motif sur l'id + le symptôme)
#
# L'ORDRE COMPTE : une classe rejoint la PREMIÈRE famille qui la retient, et les
# familles les plus spécifiques viennent d'abord. Sans ça « deux surfaces, deux
# nombres » avalerait la moitié du catalogue.
FAMILIES: list[tuple[str, str, str]] = [
    ("le-locataire",
     "Cette lecture, cette écriture, cette jointure nomment-elles leur locataire — "
     "toutes, et pas seulement la première ?",
     # ⚠️ PAS le mot « locataire » nu. C'est le mot que ce dépôt emploie pour dire
     # « client », et il apparaît dans la moitié des symptômes — la famille en
     # capturait 37 et volait leurs membres aux suivantes. Le cas qui l'a montré :
     # `two-definitions-that-must-coincide-are-never-compared` atterrissait ici
     # parce que son symptôme dit « pour le même locataire », alors que son sujet
     # est deux définitions qui divergent.
     #
     # On garde donc les formes qui parlent VRAIMENT de tenance : un identifiant,
     # ou une tournure où le locataire est le sujet du défaut.
     r"tenant|artist[_-]id|saas_artist|multitenant|fleet|canary|sandbox|"
     r"deux locataires|par locataire|du locataire|son locataire|le locataire|"
     r"d'un locataire|leur locataire|chaque locataire|un locataire|"
     r"locataires? multi|aux locataires"),

    ("un-cumul-pris-pour-un-quotidien",
     "Cette colonne est-elle une quantité du jour ou un compteur qui ne redescend "
     "pas ? Et si c'est un compteur, la fenêtre est-elle `niveau(fin) − niveau(début)` ?",
     r"cumulative|counter|compteur|delta|lifetime|two-generations|snapshot"),

    ("un-travail-qui-n-arrive-nulle-part",
     "Ce résultat atteint-il quelqu'un ? Ce code est-il appelé par quelque chose "
     "qu'un humain peut déclencher ?",
     r"never-sent|not-alerted|never-read|nothing-happens|nothing-routes|"
     r"nobody-call|never-hit|not-when-it-is-needed|nobody-writes|"
     # `metric-registered-twice-kills-the-import`, ajoutée le 2026-09-16 : le cas
     # limite de cette famille — le travail n'arrive nulle part parce que le module
     # n'a jamais fini de se charger. Rien ne s'affiche du tout.
     # `thrown-away`, ajouté le 2026-09-20 avec
     # `a-confirmation-thrown-away-by-the-rerun-that-follows-it`. Le motif est écrit
     # sur le SORT du résultat (« jeté »), pas sur `rerun`, qui est le mécanisme d'UNE
     # surface : la question de la famille — « ce résultat atteint-il quelqu'un ? » —
     # se pose identiquement pour un message que la page écrase et pour un fichier
     # qu'un second passage réécrit. Mesuré avant l'ajout : le motif ne déplace aucune
     # classe déjà classée, il ne fait que retirer celle-ci des orphelines.
     # `no-mechanism`, ajouté le 2026-09-22 avec
     # `a-promise-with-no-mechanism-behind-it`. Le motif est écrit sur l'ABSENCE de
     # destinataire du travail, comme `thrown-away` l'est sur son sort : une
     # récompense calculée, écrite en base, affichée à l'écran, et qu'aucun code
     # n'applique jamais ne « va » nulle part — c'est la question de la famille, mot
     # pour mot. Vérifié avant l'ajout : le motif ne déplace aucune classe déjà
     # classée, il retire seulement celle-ci des orphelines.
     r"no-mechanism|"
     r"rebuilt-per-rerun|thrown-away|unwired|debranch|not-reached|orphan|"
     r"registered-twice-kills-the-import|"
     # `an-identifier-that-is-referenced-but-never-declared`, ajoutee le 2026-09-16 :
     # meme famille vue depuis la REFERENCE plutot que depuis le code. Un panneau
     # Grafana qui cite un `uid` que personne ne declare n'atteint jamais sa source ;
     # `config-path-dangling` est le meme motif sur un chemin de fichier. Le motif est
     # ecrit sur le LIEN (« referenced-but-never-declared », « dangling ») et non sur
     # le mot « identifier », qui aurait ramasse des classes sans rapport.
     r"referenced-but-never-declared|dangling|nothing-ever|never-evaluat|jamais évalué"),

    ("un-nombre-affirmé-qui-n-a-pas-été-mesuré",
     "Ce chiffre a-t-il été mesuré, ou construit ? Le lecteur peut-il distinguer "
     "« zéro » de « on ne sait pas » ?",
     # `command-wrapper-that-returns-a-plausible-wrong-measurement`, ajoutée le
     # 2026-09-17 : un réécriveur qui rend un chiffre CONSTRUIT là où on croit
     # lire une mesure pose exactement la question de cette famille.
     r"plausible-wrong-measurement|wrong-measurement|"
     r"unmeasured|claimed-not-measured|outranks-the-measurement|nan-written|"
     r"rendered-as-health|sums-the-display|discarded-in-silence|"
     r"erases-every-other|past-the-end-of-its-evidence|renders-nothing|"
     # `wins-a-desc-ranking`, ajouté le 2026-09-13. La famille portait déjà
     # `outranks-the-measurement` et `renders-nothing` : un groupe VIDE qui
     # devance la mesure dans un classement décroissant est littéralement les
     # deux à la fois — la surface affiche « — » alors que le chiffre existe.
     # `taken-before-the-writer-ran`, ajouté le 2026-09-16. La famille demandait
     # « ce chiffre a-t-il été MESURÉ ? » et supposait que la réponse oui suffit.
     # Elle ne suffit pas : un chiffre peut être mesuré, exact à la seconde où il
     # est pris, et faux comme réponse à la question posée — parce qu'il a été pris
     # AVANT l'évènement qu'il prétend décrire. « La suite écrit-elle dans cette
     # table ? → 0 » était une vraie mesure, et une fausse réponse.
     r"named-like-a-final-one|imput|estimat|wins-a-desc-ranking|"
     r"taken-before-the-writer-ran|"
     # `carried-across-instruments`, ajouté le 2026-09-16 à côté du précédent : l'un
     # dit qu'une mesure peut être prise au mauvais INSTANT, l'autre avec le mauvais
     # INSTRUMENT. Les deux produisent un chiffre juste et une réponse fausse.
     r"carried-across-instruments|"
     # `chosen-by-a-proxy-for-the-cost`, ajouté le 2026-09-16, troisième de la même
     # série. Les deux précédents disent qu'une mesure peut être prise au mauvais
     # INSTANT ou avec le mauvais INSTRUMENT. Celui-ci dit qu'on peut ne pas mesurer
     # du tout et énumérer ce qui se COMPTE à la place — R118 a choisi sa population
     # par nombre de widgets faute d'instrument, et les trois pages les plus chères
     # n'avaient aucun widget. Le motif est écrit sur le SUBSTITUT (`proxy`), pas sur
     # « population », qui ramasserait des classes sans rapport.
     r"chosen-by-a-proxy|ignores-the-floor"),

    ("le-message-parle-au-mauvais-lecteur",
     "Cette phrase s'adresse-t-elle à qui la lira — et nomme-t-elle un geste que "
     "ce lecteur-là peut faire ?",
     r"assumes-a-shell|assumes-visibility|by-direction-not-by-name|"
     r"wrong-advice|blames-the-most-common|names-an-action|"
     r"flattened-for-the-narrowest|without-naming-the-reason|leaves-no-trace|"
     # `becomes-the-word-` est entré le 2026-09-12 : `title=None` fait écrire
     # « undefined » en toutes lettres au-dessus de la figure. Un mot de moteur de
     # rendu montré à un artiste est exactement la question de cette famille — à
     # qui cette phrase s'adresse-t-elle, et nomme-t-elle un geste ? — même si
     # personne ne l'a écrite volontairement.
     r"announces-a-field|instruction-|-instruction|speaks-its-own-plumbing|"
     r"addressed-to|reader|becomes-the-word-|undefined"),

    ("un-état-qui-déborde-de-sa-portée",
     "Cet état vit-il exactement le temps de ce qui l'a créé — ni plus, ni pour "
     "quelqu'un d'autre ?",
     # `outlives-its-pull-request`, ajouté le 2026-09-13 : une branche qui
     # survit à la PR qui l'a créée est le cas d'école de cette question — un
     # état qui ne vit pas le temps de ce qui l'a produit. 26 d'un coup, et le
     # propriétaire a fini par demander s'il allait perdre du travail.
     r"outlives-the-visit|outlives-its-pull-request|"
     r"written-after-instantiation|per-worker|"
     r"namespaced-by-another|connection|closes-a-connection|"
     r"only-inside-a-session|loses-the-race|first-row|session|cache|"
     # `named-after-an-environment-variable`, ajouté le 2026-09-17. Une variable de
     # `make` qui porte un nom POSIX prend la valeur du SHELL : c'est un état créé
     # ailleurs qui déborde dans la portée de la cible, et la cible s'exécute avec
     # une option que personne n'a donnée. La question de la famille — « cet état
     # vit-il exactement le temps de ce qui l'a créé, ni plus, ni pour quelqu'un
     # d'autre ? » — est exactement celle qu'il fallait poser devant `$(USER)`.
     r"named-after-an-environment|environment-variable|"
     r"state-file|leak"),

    ("deux-surfaces-deux-nombres",
     "Ce nombre a-t-il une seule définition, ou chaque surface refait-elle le calcul ?",
     # `span-read-from|étendue|sélecteur de période` : la même question — « de quoi
     # dispose-t-on ? » — posée à DEUX relations différentes. Le sélecteur lit la
     # table, la figure lit la vue, et ils ne s'accordent pas. C'est la même forme
     # qu'un total recalculé deux fois, au niveau d'une ÉTENDUE plutôt que d'une
     # somme ; élargi le 2026-09-14 plutôt que d'ajouter un motif par cas.
     r"metric-computed-outside|outside-the-metrics|two-|divergen|recopi|restated|"
     r"duplicat|escapes-every-sql-guard|drift|desync|hand-synced|"
     r"span-read-from|étendue|sélecteur de période"),

    ("une-erreur-avalée-devient-une-absence",
     "Ce `except` distingue-t-il « rien à lire » de « on n'a pas pu lire » — et "
     "l'utilisateur voit-il la différence ?",
     r"silent|swallow|avalée|absence|silencieu|renders?-as-a-measurement|"
     r"empty-bracket|no-op|returns-none|degrade|logged-as-success|"
     # `read-that-failed`, ajouté le 2026-09-12 : la classe atterrissait dans
     # « une configuration qui diverge de la prod » à cause du mot `prod` dans son
     # symptôme. Un motif qui ne nomme pas la forme la laisse au premier venu.
     # `read-through-a-filtering`, ajouté le 2026-09-13. La forme est la même à
     # un étage au-dessus : un `git commit` avorté, son message d'abandon avalé,
     # et le `git push` suivant qui rend `ok`. La question de la famille s'y
     # applique mot pour mot — ce « ok » veut-il dire « ça a marché » ou « il ne
     # s'est rien passé » ?
     # `fallback-that-answers-the-whole-question`, ajoutée le 2026-09-17. La forme
     # est la même avec une conséquence de plus : le `except` n'avale pas l'erreur
     # pour rendre RIEN, il l'avale pour rendre l'ensemble NON FILTRÉ — la fenêtre
     # « dernières 24 h » devenait tout l'historique. La question de la famille
     # tient mot pour mot : ce chiffre veut-il dire « voici les 24 h » ou « je n'ai
     # pas pu les calculer » ? Un repli qui fabrique un nombre est la version la
     # plus coûteuse de cette famille, parce qu'il ne ressemble pas à une panne.
     r"outside-its-condition|read-that-failed|failed-read|except.*number|"
     r"read-through-a-filtering|fallback"),

    ("un-garde-qui-ne-garde-pas",
     "Ce garde a-t-il déjà été VU rouge sur le défaut qu'il vise — et sa portée "
     "contient-elle ce défaut ?",
     # `gate|porte` ajoutés le 2026-09-16 : une PORTE de CI est un garde, et la
     # classe `a-gate-that-repairs-what-it-judges` — une barrière bloquante qui
     # corrige la dérive avant de la regarder — pose exactement la question de cette
     # famille. Le motif ne parlait que de `guard`, pas de la forme « porte ».
     # `skips-instead-of-refusing` et `rollback-wider-than-the-failure`, ajoutés le
     # 2026-09-16. Les deux sont les DEUX MOITIÉS d'une même porte de déploiement :
     # celle qui décide si une vérification a lieu, et celle qui répare quand elle
     # est rouge. La première passait son tour en silence sur un service inconnu ; la
     # seconde réparait plus large que la panne. Une porte dont le remède déborde est
     # aussi peu gardée qu'une porte qui ne regarde pas — la question de la famille
     # (« sa portée contient-elle ce défaut ? ») est la bonne dans les deux cas, à
     # ceci près qu'ici la portée est trop LARGE, pas trop étroite.
     # `substitution|s'exécute|accent grave` ajoutés le 2026-09-18 : une chaîne de
     # DESCRIPTION dont le shell exécute le contenu appartient à cette famille,
     # au même titre que `a-kill-pattern-that-matches-its-own-shell` et
     # `a-verdict-swallowed-by-the-pipe-that-abbreviated-it`, qui y sont déjà.
     # La question de la famille — « le garde couvre-t-il ce défaut ? » — vaut
     # ici parce que le geste qui VÉRIFIE devient le geste qui AGIT.
     r"guard|gate|porte|cliquet|ratchet|signature|probe|predicate|vacuous|mutation|"
     r"substitution|s'exécute|accent grave|"
     # `correct-because-there-is-only-one-of-it`, ajoutee le 2026-09-16 : c'est la
     # classe GENERIQUE dont trois autres du jour sont des instances. Son garde est un
     # registre qui MET EN QUESTION plutot qu'il ne refuse — la forme de garde que
     # cette famille reconnait.
     r"test-|suite|assert|blind|skips-instead-of-refusing|only-one-of-it|"
     # `fallback-that-runs` ajouté le 2026-09-16. Un `A || B` est un GARDE : B est la
     # protection qu'on croit avoir posée. Elle ne se déclenche pas sur « ai-je obtenu
     # ce que je voulais » mais sur le code de sortie de A — donc une première branche
     # qui réussit MAL la neutralise, et une qui échoue la fait agir quand on ne le
     # voulait pas. La question de la famille — « sa portée contient-elle ce défaut ? »
     # — est exactement celle qu'on aurait dû poser au repli.
     r"rollback-wider-than-the-failure|fallback-that-runs"),

    ("un-document-qui-affirme-un-état-périmé",
     "Ce qui est écrit là est-il régénéré, ou recopié une fois puis oublié ?",
     r"stale|périmé|obsolete|doc|readme|roadmap|comment|caption|note|prose|"
     r"generated|index|diagram|map|guide|runbook|lags-its-source|"
     # `telemetry-table-that-nothing-ever-purges`, ajoutée le 2026-09-16. La famille
     # demande « est-ce régénéré, ou écrit une fois puis oublié ? » — une table de
     # journal sans rétention est exactement cela : un document qui s'accumule
     # parce que personne n'a tranché ce qu'il advient de ses vieilles lignes.
     r"hand-written-list|telemetry-table-that-nothing-ever-purges|proc[ée]dure|playbook|runbook|instruction"),

    ("un-contrôle-qui-ne-peut-jamais-passer",
     "Où ce contrôle s'exécute-t-il — la machine où il tourne a-t-elle ce qu'il "
     "lui faut pour réussir un jour ?",
     r"never-pass|env-independent|host-env|container|reachab|unreachable|"
     r"not-wired|orphan|dead-code|no-caller|unrun|install|"
     r"shares-the-fate|unstated-import-path|below-detection"),

    ("un-coût-payé-sans-contrepartie",
     "Ce travail est-il payé par quelqu'un — temps de CI, premier écran, attention "
     "du lecteur — et lui rend-il quelque chose ?",
     # `drags-a-view-behind-it` est entré le 2026-09-12 : un module partagé qui
     # importe une vue fait payer un chargement de page entière à tous ses
     # appelants pour ce qu'un seul y lit. C'est exactement la question de la
     # famille — qui paie, et pour quoi — et le motif ne la voyait pas parce qu'il
     # ne nommait que des coûts de CI. Un coût de PREMIER ÉCRAN est le même sujet.
     r"runs-twice|concurrency-group|overload|competing-for-one-decision|"
     r"costs-more-than|waste|duplicate-run|too-many|drags-a-.*-behind|"
     r"paid-by|first-render|"
     # `recomputes-what-its-caller` et `memo-field-written` ajoutees le
     # 2026-09-17 : deux formes du meme paiement sans contrepartie — refaire
     # un travail dont le resultat est deja la. La question de la famille
     # (« qu'est-ce qu'on paie, et qu'est-ce qu'on recoit ? ») est
     # exactement celle qu'aucun des deux sites ne s'etait posee.
     r"recomputes-what-its-caller|memo-field-written"),

    ("un-seuil-écrit-d-instinct",
     "Ce seuil vient-il de la distribution réelle, ou d'une intuition ? Le test "
     "épingle-t-il la réalité ou la constante ?",
     r"threshold|seuil|min[_-]|floor|ceiling|limit|budget|quota|window|"
     r"magic-number|hardcoded"),

    ("une-écriture-qui-écrase",
     "Cette écriture peut-elle détruire ce qu'un autre vient d'écrire — et le "
     "saurait-on ?",
     r"overwrit|écrase|clobber|upsert|conflict|restore|delete|drop|purge|"
     r"lost|data-loss|resurrect|rotation"),

    ("le-temps-et-l-horloge",
     "Cette date est-elle celle de l'événement ou celle de la collecte ? Et dans "
     "quel fuseau ?",
     r"date|time|clock|tz|utc|timezone|fresh|schedule|cron|window-applied|"
     r"day|month|period"),

    ("la-frontière-avec-le-dehors",
     "Ce que ce code envoie dehors — un mail, une requête, un paiement, un "
     "secret — est-il ce qu'on croit, et vers qui ?",
     r"secret|token|credential|auth|jwt|mail|smtp|http|webhook|stripe|payment|"
     r"url|cors|redact|external|api-|fstring-identifier|string-substitution|"
     r"untrusted|privileged|access-gate|is-not-an-identity|"
     r"rendered-to-the-visitor|bare-except|containment"),

    ("une-configuration-qui-diverge-de-la-prod",
     "Ce que le dépôt déclare est-il ce que la production exécute ?",
     r"prod|deploy|schema-drift|migration|image|docker|compose|pin|lock|"
     # `majeure` et `valeur par défaut` ajoutés le 2026-09-16 : la famille demande
     # « ce que le dépôt DÉCLARE est-il ce qui s'exécute ? », et une option héritée
     # d'un défaut amont n'est déclarée nulle part — c'est la forme la plus discrète
     # de la divergence, celle qui ne casse rien et rend une garantie fausse.
     # Motif ÉTROIT à dessein : `default` seul balaierait la moitié du catalogue.
     r"requirements|manifest|ddl|init_db|version|montée de majeure|"
     # `reload-that-does-not-reload`, ajoutée le 2026-09-16 : le fichier EST posé sur
     # la cible et le service l'a « rechargé » — mais le réglage n'est pas appliqué.
     # C'est une divergence entre ce que le dépôt déclare et ce que la production
     # exécute, sauf qu'ici les deux côtés semblent d'accord.
     # `bind-address-that-hides-the-service`, ajoutée le 2026-09-16 : le service
     # tourne, le conteneur est sain, et pourtant rien ne peut l'atteindre. Ce que
     # le dépôt DÉCLARE (« joignable sur ce port ») n'est pas ce que la production
     # exécute — la famille pose exactement cette question.
     r"valeur par défaut|majeure|reload-that-does-not-reload|"
     r"bind-address-that-hides-the-service"),
    (
        "l-instrument-ment-sur-ce-qu-il-mesure",
        "Ce que cet instrument AFFICHE est-il ce qu'il a mesuré ?",
        # ⚠️ Placée en DERNIER, et ce n'est pas un détail : le premier motif qui matche
        # gagne, donc une famille posée plus haut volerait des classes à celles qui la
        # précèdent et ferait bouger des comptes sans qu'aucune classe ne change. Ici,
        # elle ne peut capter que ce qui tombait déjà dehors. Mesuré le 2026-09-17 :
        # 5 orphelins avant, 3 après, aucune autre famille touchée.
        #
        # La question qu'elle pose n'était posée par aucune autre. Les familles
        # existantes interrogent des documents, des gardes, des seuils, des silences —
        # jamais l'INSTRUMENT DE MESURE lui-même. Or une cible `up` qui ne mesure rien,
        # une jauge qui rend 0 parce qu'elle ne sait pas, un label dont la cardinalité
        # suit le trafic : ce sont des instruments qui décrivent autre chose que ce
        # qu'ils prétendent, et c'est une question distincte de « ce document est-il à
        # jour ».
        r"metric|gauge|jauge|scrape|exporter|prometheus|grafana|observab|instrument"
        r"|telemetr|measuring-nothing|histogram|cardinalit",
    ),
]

_ID = re.compile(r"^## ([a-z0-9][a-z0-9-]+)$", re.M)


def _entries() -> list[tuple[str, str]]:
    """(class-id, texte de l'entrée) dans l'ordre du catalogue."""
    text = SOURCE.read_text(encoding="utf-8")
    marks = [(m.group(1), m.start(), m.end()) for m in _ID.finditer(text)]
    out = []
    for i, (cid, _, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        out.append((cid, text[end:stop]))
    return out


def _cell(text: str) -> str:
    """Un symptôme rendu sûr pour une cellule de tableau Markdown.

    Écrit hors f-string : ruff cible Python 3.11 ici, où un backslash dans une
    f-string est une erreur de syntaxe.
    """
    return text[:150].replace("|", "\\|")


def _one_line(body: str, field: str) -> str:
    m = re.search(rf"^- {field}: (.+)$", body, re.M)
    return m.group(1).strip() if m else ""


def classify() -> tuple[dict[str, list[tuple[str, str]]], list[tuple[str, str]]]:
    buckets: dict[str, list[tuple[str, str]]] = {slug: [] for slug, _, _ in FAMILIES}
    orphans: list[tuple[str, str]] = []
    for cid, body in _entries():
        # Le SYMPTÔME entre dans le texte classé, pas la cause : la cause nomme
        # des fichiers, et un chemin ferait tomber toute une famille dans une
        # autre le jour d'un renommage.
        hay = f"{cid} {_one_line(body, 'symptom')}".lower()
        for slug, _, pattern in FAMILIES:
            if re.search(pattern, hay):
                buckets[slug].append((cid, _one_line(body, "symptom")))
                break
        else:
            orphans.append((cid, _one_line(body, "symptom")))
    return buckets, orphans


def _recurrence_by_class() -> dict:
    """Quelles classes ont RÉCIDIVÉ, lu depuis l'instantané de santé.

    ⚠️ Ajouté le 2026-09-17, et la raison est un défaut de méthode, pas un manque de
    confort. Les taux de récidive PAR FAMILLE — ceux qui décident de l'ordre de travail
    de R122 — venaient d'une analyse ponctuelle écrite en prose. Ils n'étaient donc pas
    rejouables, et ils se sont périmés : « 23,5 % » pour `la-frontière-avec-le-dehors`
    valait en réalité 22,2 % le jour où on l'a recalculé, le catalogue ayant grossi.
    Prioriser sur un chiffre figé, c'est prioriser sur le passé.

    Le signal est `history_additions` — une entrée d'historique postérieure au
    `first_seen`, c'est-à-dire une classe revenue après avoir été écrite. C'est la même
    définition que `ever_recurred_observed`, pour qu'un lecteur retrouve le même compte.

    Rend un dict VIDE si l'instantané est absent ou illisible, et la colonne le dit.
    """
    import json

    path = ROOT / ".claude" / "dev-docs" / "error-class-health.json"
    try:
        classes = json.loads(path.read_text(encoding="utf-8"))["classes"]
    except Exception:                                          # noqa: BLE001
        return {}
    return {cid: bool(c.get("history_additions")) for cid, c in classes.items()}


def render() -> str:
    buckets, orphans = classify()
    recurred = _recurrence_by_class()
    total = sum(len(v) for v in buckets.values()) + len(orphans)
    lines = [
        "# Familles de classes d'erreur",
        "",
        "<!-- GÉNÉRÉ par `tools/dev/error_class_families.py` — toute édition à la "
        "main est perdue à la prochaine exécution. `make error-families` -->",
        "",
        f"**{total} classes**, regroupées en **{len(FAMILIES)} familles** par une règle "
        "explicite, écrite sous chaque titre. Aucune entrée de "
        "`.claude/dev-docs/error-classes.md` n'est modifiée : le catalogue est "
        "append-only, cette taxonomie vit à côté.",
        "",
        "Une famille porte une **question**, pas un mot-clef. La question est ce qui "
        "a de la valeur : elle se pose devant du code, avant que le défaut existe. "
        "Une classe rejoint la **première** famille qui la retient — l'ordre va du "
        "plus spécifique au plus général, sinon « deux surfaces, deux nombres » "
        "avalerait la moitié du catalogue.",
        "",
        "⚠️ **La colonne `récidive` est ce qui décide de l'ordre de travail**, pas la "
        "colonne `classes`. Mesuré : la plus GROSSE famille récidive 3,5× moins que la "
        "plus douloureuse. Elle est calculée ici, à chaque régénération, précisément "
        "parce que les taux qui servaient à prioriser vivaient en prose et se sont "
        "périmés — un chiffre figé fait prioriser sur le passé.",
        "",
        "Le rattachement est mécanique et donc parfois discutable. La règle est "
        "publiée pour qu'on puisse le contester sans lire le script : si une classe "
        "est mal rangée, c'est le motif qu'on corrige, jamais l'entrée.",
        "",
        "| famille | classes | récidive | la question |",
        "|---|---|---|---|",
    ]
    for slug, question, _ in FAMILIES:
        ids = [c for c, _ in buckets[slug]]
        if recurred and ids:
            n = sum(1 for c in ids if recurred.get(c))
            rate = f"**{n}/{len(ids)}** · {100 * n / len(ids):.1f} %"
        else:
            rate = "— (instantané illisible)" if not recurred else "—"
        lines.append(
            f"| [{slug}](#{slug}) | {len(buckets[slug])} | {rate} | {question} |")
    lines += [f"| _sans famille_ | {len(orphans)} | — | — |", ""]

    for slug, question, pattern in FAMILIES:
        members = buckets[slug]
        lines += [
            f"## {slug}", "",
            f"**{question}**", "",
            f"Règle de rattachement : `{pattern}` sur l'identifiant et le symptôme. "
            f"{len(members)} classe(s).", "",
        ]
        if members:
            lines += ["| classe | symptôme |", "|---|---|"]
            lines += [f"| [`{c}`](error-classes.md#{c}) | {_cell(sym)} |"
                      for c, sym in members]
        else:
            lines.append("_Aucune classe. Une famille vide est un motif trop étroit, "
                         "pas une absence de défauts._")
        lines.append("")

    lines += [
        "## Sans famille", "",
        "Ces classes ne tombent dans aucun motif. **Ce compte est un cliquet : il ne "
        "peut que baisser.** Une taxonomie qui laisse un tiers du catalogue dehors "
        "décrit une opinion, pas le catalogue — et chaque classe qu'on range est une "
        "question qu'on a su formuler.", "",
    ]
    if orphans:
        lines += ["| classe | symptôme |", "|---|---|"]
        lines += [f"| [`{c}`](error-classes.md#{c}) | {_cell(sym)} |"
                  for c, sym in orphans]
    else:
        lines.append("_Aucune._")
    lines += [
        "",
        "## Les chiffres gelés", "",
        f"<!-- error-class-families: total={total} families={len(FAMILIES)} "
        f"orphans={len(orphans)} -->",
        "",
    ]
    body = "\n".join(lines).rstrip("\n") + "\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return body + f"\n<!-- error-class-families: sha256={digest} -->\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    fresh = render()
    if args.check:
        current = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
        if current == fresh:
            return 0
        diff = "".join(difflib.unified_diff(
            current.splitlines(keepends=True), fresh.splitlines(keepends=True),
            fromfile="sur le disque", tofile="ce que le catalogue dit", n=1))
        sys.stderr.write("`.claude/dev-docs/error-class-families.md` est périmé.\n"
                         "Remède : make error-families\n\n" + diff[:4000] + "\n")
        return 1
    DOC.write_text(fresh, encoding="utf-8")
    print(f"écrit : {DOC.relative_to(ROOT)} ({len(fresh.splitlines())} lignes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
