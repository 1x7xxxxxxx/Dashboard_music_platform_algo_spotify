"""Un secret ne monte jamais dans une couche d'image.

Type: Guard
Uses: Dockerfile, Dockerfile.api, Dockerfile.airflow, .dockerignore
Depends on: rien à l'exécution — il lit deux fichiers texte
Persists in: nothing

Le défaut, trouvé le 2026-09-22 en préparant la connexion Google
--------------------------------------------------------------
`.streamlit/secrets.toml` était dans `.gitignore` (ligne 15) et **pas** dans
`.dockerignore`. Or le `Dockerfile` porte `COPY .streamlit/ ./.streamlit/`. Le jour
où ce fichier existe sur la machine de build — c'est-à-dire le jour où la connexion
Google est configurée en local — le `client_secret` et le `cookie_secret` partent
dans une couche d'image.

Une couche d'image ne s'efface pas : la supprimer dans une couche suivante laisse le
contenu lisible dans la précédente. Et quiconque peut tirer l'image peut la lire.

**Le piège est la demi-protection.** `.env`, `.env.local` et `config/config.yaml`
étaient tous les trois exclus des DEUX côtés, sous un commentaire qui dit « Never
bake credentials into images ». Le quatrième porteur de secret ne l'était que d'un
côté, et être protégé du dépôt git donne exactement l'impression d'être protégé de
l'image. C'est la même forme que la classe
`a-coherence-checked-in-only-one-direction`.

Ce que ce garde N'EST PAS
-------------------------
Ce n'est pas `test_the_image_ships_with_the_app.py`. Celui-là vérifie l'autre moitié
— que les répertoires de runtime SONT copiés et ne sont PAS exclus. Les deux gardes
regardent le même couple de fichiers et défendent des propriétés opposées ; les
fusionner rendrait l'une des deux invisible.

⚠️ Portée déclarée, et ce qu'elle NE couvre pas. Le garde LIT `.gitignore` et
retient les lignes portant `secret`, `.env` ou `credential` — il ne tient aucune
liste à la main, parce qu'une liste recopiée pourrit : `.gitignore` gagnerait un
porteur, le garde l'ignorerait, et il resterait vert sur le défaut qu'il existe pour
attraper.

Lui échappent donc : un secret dans un fichier au nom anodin (`config/prod.toml`),
et un secret qui ne serait dans AUCUN des deux fichiers. Le premier est assumé —
deviner depuis un nom produit des faux positifs sur tout ce qui contient « key » ou
« token ». Le second est couvert ailleurs, par `detect-secrets` en pré-commit.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DOCKERIGNORE = _ROOT / ".dockerignore"

#: Ce qui fait d'une ligne de `.gitignore` un PORTEUR DE SECRET. Trois mots, et le
#: choix est étroit à dessein : deviner depuis un nom de fichier produit des faux
#: positifs sur tout ce qui contient « key » ou « token ».
_MOTS_DE_SECRET = re.compile(r"secret|\.env|credential", re.I)

_DOCKERFILES = ("Dockerfile", "Dockerfile.api", "Dockerfile.airflow")


def _motifs(fichier: Path) -> set[str]:
    """Les motifs déclarés, commentaires, vides et RÉ-INCLUSIONS retirés.

    ⚠️ Une ligne `!quelque-chose` n'exclut rien — elle RE-INCLUT. `!.env.example`
    dit « ce gabarit-là voyage », c'est l'inverse d'un secret. La compter comme un
    porteur exigerait de l'exclure, donc d'exclure un fichier qui doit voyager.
    """
    return {
        ligne.strip().lstrip("/")
        for ligne in fichier.read_text(encoding="utf-8").splitlines()
        if ligne.strip()
        and not ligne.lstrip().startswith("#")
        and not ligne.lstrip().startswith("!")
    }


def _porteurs_de_secret() -> set[str]:
    """Ce que `.gitignore` traite comme un secret. LUE, jamais recopiée.

    La liste vivait à la main dans ce fichier au premier jet, le 2026-09-22. Elle
    aurait pourri comme toute copie : `.gitignore` gagne un porteur, le garde ne le
    sait pas, et il reste vert sur le défaut qu'il existe pour attraper. C'est la
    classe « un catalogue recopié », que ce dépôt a payée quatre fois.
    """
    return {m for m in _motifs(_ROOT / ".gitignore")
            if _MOTS_DE_SECRET.search(m) and not m.endswith("/")}


def test_the_gitignore_still_names_some_secrets() -> None:
    """NON-VACUITÉ. Sans lui, un `.gitignore` vidé rendrait zéro paramètre au test
    ci-dessous : zéro échec, et un garde qui ne garde plus rien en silence.
    """
    porteurs = _porteurs_de_secret()
    assert len(porteurs) >= 4, (
        f"seulement {len(porteurs)} porteur(s) de secret trouvé(s) dans "
        f"`.gitignore` : {sorted(porteurs)}. Soit la section « secrets » a été "
        "vidée, soit le motif de détection ne la reconnaît plus — dans les deux "
        "cas le test de couverture ci-dessous ne vérifie plus rien.")


@pytest.mark.parametrize("porteur", sorted(_porteurs_de_secret()))
def test_every_secret_the_repo_hides_is_also_kept_out_of_the_build_context(
        porteur: str) -> None:
    """Les DEUX frontières, pas une.

    `.gitignore` protège le dépôt git. `.dockerignore` protège le contexte de
    build. Ce sont deux surfaces distinctes, et un porteur gardé d'un seul côté
    donne exactement l'impression d'être gardé — c'est ainsi que
    `.streamlit/secrets.toml` a vécu protégé à moitié jusqu'au 2026-09-22, sous un
    `COPY .streamlit/` qui l'aurait gravé dans une couche d'image.

    Le sens est à sens unique : `.dockerignore` a le droit d'exclure davantage
    (caches, environnements, artefacts). Ce qu'il n'a pas le droit de faire, c'est
    d'en exclure MOINS sur un secret.
    """
    docker = _motifs(_DOCKERIGNORE)
    assert porteur in docker, (
        f"`.gitignore` cache `{porteur}` et `.dockerignore` ne l'exclut pas. Il "
        "entre donc dans le contexte de build, et n'importe quel `COPY` qui "
        "l'englobe le grave dans une couche d'image — d'où il ne s'efface plus, et "
        "que quiconque tire l'image peut lire. Ajoute la MÊME ligne à "
        "`.dockerignore`.")


def test_the_dockerfiles_still_copy_something_at_all() -> None:
    """Le garde suppose que des `COPY` existent. S'ils disparaissaient, il
    défendrait une propriété sans objet tout en restant vert — un garde vacant.
    """
    total = 0
    for nom in _DOCKERFILES:
        f = _ROOT / nom
        if not f.exists():
            continue
        total += len(re.findall(r"^\s*COPY\s", f.read_text(encoding="utf-8"), re.M))
    assert total >= 3, (
        f"seulement {total} instruction(s) COPY dans {_DOCKERFILES} : soit les "
        "images ne copient plus rien, soit les fichiers ont été renommés. Dans les "
        "deux cas, le garde ci-dessus ne protège plus ce qu'il croit protéger."
    )


def test_a_secret_kept_out_of_the_image_is_mounted_into_the_container():
    """The other half: excluded from the image AND never delivered = a feature that
    silently never switches on. Found 2026-09-23 — the runbook said `secrets.toml`
    "is mounted in production", and no service mounted it: the Google button would
    have stayed hidden in production with no error anywhere."""
    import yaml
    compose = yaml.safe_load((_ROOT / "docker-compose.example.yml").read_text())
    volumes = compose["services"]["dashboard"].get("volumes", [])
    targets = {str(v).split(":")[1] for v in volumes if ":" in str(v)}
    assert "/app/.streamlit" in targets or "/app/.streamlit/secrets.toml" in targets, (
        "`.streamlit/secrets.toml` is excluded from the image (.dockerignore) but the "
        "`dashboard` service mounts neither it nor `.streamlit/` — Streamlit will never "
        f"see it in production. Mounted: {sorted(targets)}")
