"""Un service derive ne peut pas fabriquer son propre artefact.

Error class `a-replica-that-builds-its-own-image`.

Type: Sub
Uses: yaml, pathlib
Triggers: pytest
Depends on: deploy/docker-compose.replica.yml
Persists in: —

Le defaut, mesure en PRODUCTION le 2026-09-17
---------------------------------------------
`deploy/docker-compose.replica.yml` derive `dashboard2` de `dashboard` par `extends`.
`extends` reprend AUSSI la cle `build:` — donc Docker Compose fabrique une image a un
nom derive du nom de SERVICE, `streamlytics-dashboard2`, distincte de celle du primaire.
Et `docker compose up -d` ne reconstruit pas une image dont le tag existe deja.

Ce que la prod a rendu ce jour-la :

    primaire : streamlytics-dashboard  construite 2026-09-16 18:51
               CMD python3 -m src.dashboard.serve
    replique : streamlytics-dashboard2 construite 2026-09-16 12:02
               CMD streamlit run src/dashboard/app.py

Sept heures et un commit d'ecart (e70a83f, celui qui a introduit `serve.py`), aucun
avertissement. Derriere le repartiteur Caddy, la moitie des visiteurs aurait recu un
binaire d'un AUTRE COMMIT.

⚠️ Le symptome a ete chanceux : l'ancienne CMD ne demarre pas l'exportateur, donc la
cible Prometheus est sortie `connection refused` et j'ai cherche. Une image perimee qui
sert correctement du HTTP n'aurait rien allume du tout.

Mutation record — 2026-09-17, deux mutations EXECUTEES et vues rouges :

  * la ligne `image:` retiree de `deploy/docker-compose.replica.yml` — c'est-a-dire
    l'etat REEL de la production ce matin-la, pas une mutation inventee → exit 1 sur
    `test_every_extended_service_pins_the_image_it_replicates` ; 0 apres remise en etat.
  * `image: streamlytics-dashboard2`, qui satisfait la LETTRE du garde precedent tout
    en reintroduisant exactement le tag que compose aurait fabrique seul → exit 1 sur
    `test_a_pinned_image_is_not_named_after_the_derived_service` ; 0 apres.

⚠️ La seconde mutation a d'abord passe au VERT. La version initiale du second test
comparait l'image a celle du service PARENT, et `docker-compose.yml` est gitignore par
construction : la comparaison sortait par `continue`, donc le test etait vide tout en
etant vert. C'est la mutation qui l'a montre — la relecture ne l'avait pas vu. Voir la
classe `un-controle-qui-ne-peut-jamais-passer`.

Ce que ce garde exige
---------------------
Tout service defini par `extends` epingle une `image:` EXPLICITE. C'est la seule forme
qui rende la divergence structurellement impossible : deux services qui nomment le meme
tag ne peuvent pas servir deux artefacts. Reconstruire ne suffit pas — c'est un geste
qu'il faut penser a refaire, et ce defaut est ne d'un geste qu'on a oublie.
"""

import pathlib

import yaml

_ROOT = pathlib.Path(__file__).resolve().parents[1]


class _ComposeLoader(yaml.SafeLoader):
    """`safe_load` refuse les tags de Compose — et refuser n'est pas lire.

    `ports: !override` est une directive de fusion propre a Compose >= 2.24, que la
    replique utilise pour ne PAS heriter du port du primaire. `yaml.safe_load` leve
    `ConstructorError` dessus, ce qui ferait echouer ce garde pour une raison qui n'a
    rien a voir avec ce qu'il mesure. On ignore le tag et on garde la valeur.
    """


def _drop_tag(loader: yaml.Loader, suffix: str, node: yaml.Node):
    """Construire le noeud SOUS le tag, jamais le noeud lui-meme.

    `construct_object(node)` reprendrait le meme noeud tague et boucle —
    `found unconstructable recursive node`. On dispatche sur la forme du noeud.
    """
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return loader.construct_scalar(node)


_ComposeLoader.add_multi_constructor("!", _drop_tag)


def _load(path: pathlib.Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_ComposeLoader) or {}


def _compose_files() -> list[pathlib.Path]:
    """Tous les fichiers compose versionnes du depot.

    ⚠️ `docker-compose.yml` a la racine est gitignore par construction (c'est la source
    de derive que l'audit de parite existe pour attraper), donc il n'est pas toujours la.
    On balaie ce qui EST versionne, et on refuse de passer sur un ensemble vide.
    """
    found = sorted(_ROOT.glob("deploy/docker-compose*.yml")) + sorted(
        _ROOT.glob("docker-compose*.yml")
    )
    assert found, (
        "No compose file found at all. This guard covers container artifact drift; if "
        "the compose layout moved, point it at the new location instead of deleting it."
    )
    return found


def _services_that_extend() -> list[tuple[pathlib.Path, str, dict]]:
    out: list[tuple[pathlib.Path, str, dict]] = []
    for path in _compose_files():
        doc = _load(path)
        for name, body in (doc.get("services") or {}).items():
            if isinstance(body, dict) and "extends" in body:
                out.append((path, name, body))
    return out


def test_every_extended_service_pins_the_image_it_replicates():
    """Un service `extends` nomme l'image qu'il sert, il ne la fabrique pas.

    On lit la STRUCTURE YAML — la cle `image:` du service — et non le texte du fichier.
    La distinction compte ici : le fichier de la replique PARLE longuement de ce defaut
    en commentaire, et un garde textuel rougirait sur sa propre explication.
    """
    extended = _services_that_extend()
    assert extended, (
        "No service uses `extends` any more. That may be legitimate, but this guard "
        "then proves nothing — say so here rather than leaving a green no-op."
    )

    for path, name, body in extended:
        image = body.get("image")
        assert isinstance(image, str) and image.strip(), (
            f"{path.relative_to(_ROOT)}: service `{name}` is built by `extends` but "
            f"pins no explicit `image:`. `extends` carries `build:` over, so compose "
            f"tags the result after the SERVICE name — a different tag from the one it "
            f"replicates — and `up -d` reuses whatever already carries that tag. "
            f"Mesure du 2026-09-17 en prod : 7 h et un commit d'ecart entre le primaire "
            f"et sa replique, servis cote a cote derriere Caddy, sans un avertissement."
        )


def test_a_pinned_image_is_not_named_after_the_derived_service():
    """L'image epinglee ne porte pas le nom du service derive.

    Le premier garde accepterait `image: streamlytics-dashboard2` : la lettre est
    satisfaite, et rien n'est garde — c'est EXACTEMENT le tag que compose aurait
    fabrique tout seul, donc exactement le defaut du 2026-09-17 avec une ligne de plus.

    ⚠️ Ce garde a remplace une premiere version qui comparait l'image a celle du service
    PARENT. Elle passait sur la mutation : `docker-compose.yml` est gitignore par
    construction, donc la comparaison sortait par `continue` et le test etait VIDE tout
    en etant vert. Un garde qui ne peut pas echouer ressemble a un garde.

    La propriete retenue se verifie sur ce qui est VERSIONNE : le tag epingle ne doit
    pas etre derive du nom du service qui le porte. C'est la signature de l'artefact
    autonome, quel que soit le prefixe de projet.
    """
    for path, name, body in _services_that_extend():
        image = str(body.get("image", ""))
        tag = image.rsplit("/", 1)[-1].split(":", 1)[0]
        assert not tag.endswith(name), (
            f"{path.relative_to(_ROOT)}: `{name}` pins `{image}`, a tag derived from "
            f"its own service name — the very tag compose would have built by itself. "
            f"Pinning that changes nothing: the derived service still owns a separate "
            f"artifact, and `up -d` still serves whatever already carries the tag. "
            f"Name the image of the service it extends."
        )
