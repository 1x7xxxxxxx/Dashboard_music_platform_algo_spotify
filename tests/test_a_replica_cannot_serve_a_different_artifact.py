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

  * l'`image:` retiree de l'ANCRE `dashboard: &dashboard` de
    `docker-compose.example.yml` — l'etat exact du fichier avant ce commit, ou ni
    l'ancre ni `dashboard2` n'en portaient → exit 1 sur
    `test_services_sharing_a_build_share_the_image_they_produce` ; 0 apres.
  * `image: streamlytics-airflow-init` sur un seul des trois services airflow, qui
    satisfait « une image existe » tout en rouvrant la divergence → exit 1 sur le meme
    test. Idem en retirant la ligne d'un seul des trois.

⚠️ Une mutation a passe au VERT et c'etait JUSTE : retirer l'`image:` de `dashboard2`
seul ne casse rien, parce que la fusion `<<: *dashboard` propage celle de l'ancre. C'est
l'ancre qui porte le correctif. La ligne de `dashboard2` est gardee pour la lisibilite,
pas pour la garde — et le commentaire du fichier le dit desormais, au lieu de laisser
croire l'inverse.

⚠️ La seconde mutation a d'abord passe au VERT. La version initiale du second test
comparait l'image a celle du service PARENT, et `docker-compose.yml` est gitignore par
construction : la comparaison sortait par `continue`, donc le test etait vide tout en
etant vert. C'est la mutation qui l'a montre — la relecture ne l'avait pas vu. Voir la
classe `un-controle-qui-ne-peut-jamais-passer`.

⚠️ Le garde d'origine ne couvrait que `extends`, et un balayage des freres l'a pris
VERT sur une seconde instance vivante : `docker-compose.example.yml` — le fichier
copie tel quel en production — derive `dashboard2` par une fusion YAML
(`<<: *dashboard`), pas par `extends`. Meme classe, autre vecteur, garde aveugle.
C'est la portee du garde qui etait le defaut, pas la connaissance.

Ce que ce garde exige
---------------------
DEUX proprietes, parce qu'un seul vecteur ne couvre pas la classe :

1. **Meme `build:` ⇒ meme `image:`.** Deux services qui construisent depuis le meme
   contexte et le meme Dockerfile sont le meme artefact ; s'ils ne nomment pas le meme
   tag, Compose en fabrique deux, et rien ne les rapproche jamais. Cette propriete est
   AGNOSTIQUE du vecteur — elle attrape `extends`, la fusion YAML, et le copier-coller.
   Elle n'impose rien a un service dont le `build:` est unique : `api` n'a pas besoin
   d'une `image:` pour etre correct.
2. **Tout service defini par `extends` epingle une `image:` explicite** — la propriete 1
   ne peut pas l'attraper, parce que le `build:` du parent vit dans un AUTRE fichier,
   gitignore de surcroit.

Epingler, et non reconstruire : reconstruire est un geste
qu'il faut penser a refaire, et ce defaut est ne d'un geste qu'on a oublie. Deux services
qui nomment le meme tag ne PEUVENT pas servir deux artefacts.
"""

import pathlib
import sys
import subprocess

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
    """Les fichiers compose VERSIONNES du depot — pas ceux qui trainent sur le disque.

    ⚠️ La premiere version globait le disque, et son verdict dependait d'un fichier
    NON SUIVI : `docker-compose.yml` a la racine, gitignore par construction, present
    sur ce poste et absent en CI. Le garde etait donc rouge ici et vert la-bas sur le
    meme commit — un garde dont la reponse depend de la machine n'est pas un garde.

    Ce que ca deplace, et il faut le dire : le fichier reellement execute en production
    est cette copie non suivie. Ce garde couvre son GABARIT — `docker-compose.example.yml`,
    que `.claude/dev-docs/deployment.md` fait copier tel quel sur le VPS. La derive
    entre le gabarit et la copie est un autre sujet, et elle a son propre outil
    (`make sync-check`).
    """
    tracked = subprocess.run(
        ["git", "ls-files", "docker-compose*.yml", "deploy/docker-compose*.yml"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    found = [_ROOT / rel for rel in sorted(tracked)]
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


def _services_with_build() -> list[tuple[pathlib.Path, str, dict]]:
    """Les services qui CONSTRUISENT, fusions YAML resolues.

    PyYAML resout `<<: *ancre` a la lecture, donc un service qui herite `build:` par
    fusion le porte dans le dict charge — exactement comme s'il l'avait ecrit. C'est ce
    qui rend cette propriete agnostique du vecteur.
    """
    out: list[tuple[pathlib.Path, str, dict]] = []
    for path in _compose_files():
        doc = _load(path)
        for name, body in (doc.get("services") or {}).items():
            if isinstance(body, dict) and body.get("build"):
                out.append((path, name, body))
    return out


def test_services_sharing_a_build_share_the_image_they_produce():
    """Meme contexte de construction ⇒ meme tag, sinon deux artefacts divergent.

    Trouve par un balayage des freres le 2026-09-17, APRES que le premier garde de ce
    fichier soit passe vert sur une instance vivante. Deux sites :

      * `dashboard` / `dashboard2` — la replique, derivee par fusion YAML ;
      * les trois services airflow — meme `Dockerfile.airflow`, trois tags derives des
        trois noms de service. `tools/deploy.sh` ne reconstruit que `api` et
        `dashboard`, donc reconstruire l'un des trois laissait les deux autres sur une
        image plus ancienne, sans que rien ne le dise.

    Un `build:` UNIQUE n'est pas concerne : exiger une `image:` partout produirait du
    bruit sans supprimer aucune divergence possible.
    """
    by_build: dict[tuple, list[tuple[pathlib.Path, str, object]]] = {}
    for path, name, body in _services_with_build():
        build = body["build"]
        key = (
            path.name,
            # repr: a `build: .` string and a `build: {context…}` dict in one file made
            # `sorted` raise TypeError — found by the self-proving test, 2026-09-26.
            repr(build if isinstance(build, str) else tuple(sorted(build.items()))),
        )
        by_build.setdefault(key, []).append((path, name, body.get("image")))

    for (file_name, _build), members in sorted(by_build.items()):
        if len(members) < 2:
            continue  # un seul service construit ainsi : rien ne peut diverger
        images = {img for _p, _n, img in members}
        assert len(images) == 1 and None not in images and "" not in images, (
            f"{file_name}: "
            + ", ".join(f"`{n}` -> {img!r}" for _p, n, img in members)
            + ". Ces services construisent depuis le MEME contexte, donc ils sont le "
            "meme artefact — mais ils ne nomment pas le meme tag. Compose en fabrique "
            "alors un par service, et `up -d` sert celui qui traine deja sous chaque "
            "nom. Mesure du 2026-09-17 : sept heures et un commit d'ecart entre le "
            "dashboard et sa replique, servis cote a cote derriere Caddy."
        )


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path, monkeypatch) -> None:
    """Non-vacuity on a FABRICATED compose file — the 2026-09-17 shapes, then the fix.

    The three checks above read the repo's compose files; the only way to know they can
    fail is to hand them the defect."""
    def run(compose: str) -> list[str]:
        f = tmp_path / "docker-compose.prod.yml"
        f.write_text(compose, encoding="utf-8")
        monkeypatch.setattr(sys.modules[__name__], "_compose_files", lambda: [f])
        monkeypatch.setattr(sys.modules[__name__], "_ROOT", tmp_path)
        failed = []
        for check in (test_every_extended_service_pins_the_image_it_replicates,
                      test_a_pinned_image_is_not_named_after_the_derived_service,
                      test_services_sharing_a_build_share_the_image_they_produce):
            try:
                check()
            except AssertionError:
                failed.append(check.__name__)
        return failed

    defect = ("services:\n"
              "  dashboard:\n    build: .\n"
              "  dashboard2:\n    extends: {service: dashboard}\n    build: .\n"
              "  scheduler:\n    build: {context: ., dockerfile: Dockerfile.airflow}\n"
              "  webserver:\n    build: {context: ., dockerfile: Dockerfile.airflow}\n")
    assert run(defect) == [test_every_extended_service_pins_the_image_it_replicates.__name__,
                           test_services_sharing_a_build_share_the_image_they_produce.__name__]
    self_named = defect.replace("    extends: {service: dashboard}\n",
                                "    extends: {service: dashboard}\n    image: app-dashboard2\n")
    assert test_a_pinned_image_is_not_named_after_the_derived_service.__name__ in run(self_named)
    fixed = ("services:\n"
             "  dashboard:\n    build: .\n    image: app-dashboard\n"
             "  dashboard2:\n    extends: {service: dashboard}\n    build: .\n    image: app-dashboard\n"
             "  scheduler:\n    build: {context: ., dockerfile: Dockerfile.airflow}\n    image: app-airflow\n"
             "  webserver:\n    build: {context: ., dockerfile: Dockerfile.airflow}\n    image: app-airflow\n")
    assert run(fixed) == [], "the corrected compose must pass all three checks"
