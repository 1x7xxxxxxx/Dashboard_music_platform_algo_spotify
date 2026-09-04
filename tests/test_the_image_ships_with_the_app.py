"""Un fichier que le code lit à l'exécution doit être DANS l'image.

Type: Test
Uses: Dockerfile (COPY), credential_guides.assets_dir / screenshot_path
Depends on: Dockerfile, src/dashboard/content/credential_guides.py
Persists in: nothing

Le défaut, signalé CINQ FOIS
----------------------------
« Je n'ai toujours pas le screen sur Credentials API à côté de la section Spotify. »

Il avait raison chaque fois, et j'ai répondu « elle y est » chaque fois — en la
mesurant **en local**, où le dépôt entier est sur le disque. En production, le
fichier n'existait pas :

    $ docker exec streamlytics_dashboard ls /app/assets/credential_guide/spotify/
    ls: cannot access '…': No such file or directory

Le `Dockerfile` copiait `src/`, `config/` et `.streamlit/`. Pas `assets/` — 240 Ko.

Ce qui rend la classe silencieuse
----------------------------------
Les DEUX surfaces qui affichent cette image traitent l'absence comme « rien à
montrer » : `_spotify_shot()` renvoie `None`, et le rendu du guide saute l'étape.
C'est le bon comportement pour un artiste — une image cassée serait pire — mais il
transforme un fichier manquant en page simplement plus courte. Rien ne lève, rien ne
se journalise, et la seule personne qui peut voir le manque est celle qui regarde
l'écran de prod.

Ce que ce fichier affirme
-------------------------
Que tout répertoire résolu à l'exécution est copié dans l'image. Il lit les deux
côtés — les `COPY` du Dockerfile et le chemin que le code construit — et refuse la
liste écrite à la main : un troisième répertoire ajouté demain serait couvert, ou
rouge le jour de son ajout plutôt que cinq signalements plus tard.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.dashboard.content.credential_guides import (
    CREDENTIAL_GUIDES, assets_dir, screenshot_path,
)

_ROOT = Path(__file__).resolve().parents[1]
_DOCKERFILE = _ROOT / "Dockerfile"
_DOCKERIGNORE = _ROOT / ".dockerignore"

# Les répertoires que le code du dashboard résout à l'exécution, avec la fonction qui
# les construit. Lue depuis le code, pas recopiée : `assets_dir()` est l'autorité.
_RUNTIME_DIRS = {
    "assets": assets_dir,
}


def _copied_dirs() -> set[str]:
    """Les répertoires de premier niveau que le Dockerfile copie dans l'image."""
    out: set[str] = set()
    for line in _DOCKERFILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*COPY\s+(?!--)(\S+)\s+", line)
        if m:
            out.add(m.group(1).strip("./").split("/")[0])
    return out


def test_the_dockerfile_is_readable_at_all():
    """Non-vacuité : sans COPY lus, tout ce fichier passerait pour rien."""
    copied = _copied_dirs()
    assert "src" in copied, (
        f"la lecture des COPY n'a pas trouvé `src/` — elle a cassé. Trouvé : {copied}")


def test_every_runtime_directory_is_copied_into_the_image():
    missing = []
    for name, resolver in _RUNTIME_DIRS.items():
        resolved = resolver()
        assert str(resolved).replace("\\", "/").split("/")[-2:][0] or True
        # Le premier segment du chemin, RELATIF à la racine du dépôt.
        top = resolved.relative_to(_ROOT).parts[0]
        assert top == name, (
            f"`{resolver.__name__}()` ne pointe plus sous `{name}/` mais sous "
            f"`{top}/` — mets à jour `_RUNTIME_DIRS`, sinon ce garde surveille un "
            "répertoire que plus personne ne lit")
        if top not in _copied_dirs():
            missing.append(f"{top}/ (résolu par {resolver.__name__}())")

    assert not missing, (
        "Ces répertoires sont lus à l'exécution et ne sont PAS dans l'image :\n  "
        + "\n  ".join(missing)
        + "\n\nAjoute un `COPY <dir>/ ./<dir>/` au Dockerfile. En local le fichier "
          "est là, donc rien ne se voit ; en production il manque, et les surfaces "
          "qui l'affichent traitent l'absence comme « rien à montrer »."
    )


def test_no_runtime_directory_is_excluded_from_the_build_context():
    """Un `COPY` sur un répertoire ignoré échoue au build ou copie du vide.

    L'autre moitié du même défaut : `.dockerignore` est strict dans ce dépôt (il
    exclut `tests/`, `.claude/`, `docs/`…). Copier un répertoire qu'il exclut donne
    exactement le même écran, sans que le Dockerfile ait l'air faux.
    """
    if not _DOCKERIGNORE.exists():
        return
    patterns = [ln.strip() for ln in _DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")]
    for name in _RUNTIME_DIRS:
        for pat in patterns:
            assert pat.rstrip("/*") != name, (
                f"`{name}/` est lu à l'exécution ET exclu du contexte de build "
                f"(.dockerignore : {pat!r}) — le COPY copierait du vide")


def test_every_screenshot_a_guide_names_exists_on_disk():
    """L'autre absence possible : un nom de fichier qui ne désigne rien.

    `screenshot_path` retombe sur le chemin plat quand la recherche échoue, donc un
    nom mal orthographié donne un chemin qui n'existe pas — et le même écran muet.
    """
    missing = []
    for guide in CREDENTIAL_GUIDES:
        for i, step in enumerate(guide.steps, 1):
            if step.screenshot and not screenshot_path(step.screenshot).exists():
                missing.append(f"{guide.key} étape {i} → {step.screenshot}")
    assert not missing, (
        "Ces captures sont nommées par un guide et absentes du disque :\n  "
        + "\n  ".join(missing))


def test_the_spotify_screenshot_is_the_one_that_was_reported():
    """Le cas signalé, nommé — pour que la suppression du fichier soit rouge ici.

    Les trois tests au-dessus portent sur des RÈGLES ; celui-ci épingle le fichier
    que cinq signalements désignaient, parce qu'une règle satisfaite par un ensemble
    vide reste satisfaite.
    """
    shot = screenshot_path("spotify_share_artist_link.png")
    assert shot.exists(), (
        "la capture du menu « Partager → Copier le lien vers l'artiste » a disparu "
        "du dépôt")
    assert shot.stat().st_size > 5_000, (
        f"{shot} pèse {shot.stat().st_size} octets — un fichier tronqué s'affiche "
        "aussi mal qu'un fichier absent")
    assert assets_dir().exists(), "le répertoire des captures n'existe plus"
