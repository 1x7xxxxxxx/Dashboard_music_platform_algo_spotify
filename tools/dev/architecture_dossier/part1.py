PART1 = """
<section class="cover">
  <div class="kicker">Dossier d'architecture · 10 septembre 2026</div>
  <h1>Architecture et qualité<br>des données</h1>
  <div class="sub">Comment streaMLytics collecte huit plateformes qui ne parlent pas la
    même langue, pourquoi les chiffres se contredisaient, et ce qui les tient
    désormais d'accord.</div>
  <div class="band">
    <i style="background:#2a78d6"></i><i style="background:#1baf7a"></i>
    <i style="background:#eb6834"></i><i style="background:#eda100"></i>
  </div>
  <div class="meta">Couches bronze / argent / or · six classes de défaut cataloguées ·
    4 810 contrôles automatiques</div>
</section>

<section class="newpage toc">
  <h2>Ce que ce document contient</h2>
  <ol>
    <li>L'architecture, en une page
      <span class="d">Les quatre étages, de l'API externe à l'écran de l'artiste.</span></li>
    <li>Le problème que ce système doit résoudre
      <span class="d">Huit sources, trois natures de donnée, quatre horloges.</span></li>
    <li>Les couches bronze, argent et or
      <span class="d">Le schéma, un exemple chiffré de bout en bout, et la matrice
        couche × plateforme.</span></li>
    <li>Une fiche par plateforme
      <span class="d">Ce que chacune rend vraiment, et le piège qui lui est propre.</span></li>
    <li>Les traitements programmés
      <span class="d">Treize chaînes, leur cadence, et l'entonnoir d'alerte du soir.</span></li>
    <li>Les six défauts rencontrés, et comment ils sont tenus
      <span class="d">Un schéma par défaut : ce qui se passait, ce qui se passe.</span></li>
    <li>Les cinq piliers de la qualité, et le sixième
      <span class="d">Valider ce qu'on collecte ne suffit pas : il faut valider ce qu'on
        calcule.</span></li>
    <li>La boucle de correction
      <span class="d">Mesurer, critiquer avant d'écrire, garder, muter, cataloguer.</span></li>
    <li>Suggestions
      <span class="d">Ce que je ferais ensuite, et ce que je ne ferais pas.</span></li>
  </ol>
</section>

<section class="newpage">
  <h2>1 · L'architecture, en une page</h2>
  <p class="lead">Quatre étages. Chacun a une responsabilité unique, et le passage d'un
    étage au suivant est une frontière qu'on peut faire respecter.</p>

  <mermaid>
flowchart TB
  subgraph EXT["Sources externes"]
    direction LR
    A1["API<br/>Spotify · YouTube<br/>SoundCloud · Instagram · Meta"]
    A2["Fichiers déposés<br/>Spotify for Artists · Apple<br/>distributeurs · droits"]
    A3["Saisie manuelle<br/>compléments non exposés<br/>par les API"]
  end
  subgraph ING["Collecte — treize chaînes programmées"]
    B1["Collecteurs<br/>une plateforme chacun"]
    B2["Lecteurs de fichiers<br/>déclenchés au dépôt"]
  end
  subgraph STO["Base de données"]
    direction LR
    C1["BRONZE<br/>64 tables · tel que reçu"]
    C2["ARGENT<br/>une ligne par entité et par jour"]
    C3["OR<br/>une définition par métrique"]
  end
  subgraph SUR["Surfaces"]
    direction LR
    D1["Tableau de bord"]
    D2["API"]
    D3["Rapport PDF"]
    D4["E-mails"]
  end
  A1 --> B1 --> C1
  A2 --> B2 --> C1
  A3 --> C1
  C1 --> C2 --> C3
  C3 --> D1 & D2 & D3 & D4
  C1 -.->|"interdit"| D1
  </mermaid>
  <div class="caption">La flèche en pointillé est la règle centrale du dossier : aucune
    surface ne lit le bronze directement.</div>

  <div class="stats">
    <div class="stat"><div class="v">8</div><div class="k">plateformes intégrées</div></div>
    <div class="stat"><div class="v">95</div><div class="k">tables, dont 64 de bronze</div></div>
    <div class="stat"><div class="v">13</div><div class="k">chaînes programmées</div></div>
    <div class="stat good"><div class="v">4 810</div><div class="k">contrôles automatiques</div></div>
  </div>

  <div class="box">
    <div class="lbl">Ce que l'architecture n'a pas</div>
    <p>Pas d'entrepôt séparé, pas de format colonne, pas de moteur analytique dédié, pas
      d'outil de transformation externe. La base applicative pèse quelques dizaines de
      mégaoctets et son agrégat le plus lourd s'exécute en moins de vingt millisecondes.
      Chacun de ces composants a été examiné et écarté avec un seuil chiffré qui, le jour
      où il sera franchi, rouvrira la question tout seul.</p>
  </div>
</section>

<section class="newpage">
  <h2>2 · Le problème que ce système doit résoudre</h2>
  <p class="lead">Les huit sources ne rendent pas la même chose. Les confondre est la
    cause commune de presque tous les défauts de ce dossier.</p>

  <h3>Trois natures de donnée</h3>
  <mermaid>
flowchart LR
  subgraph N1["QUOTIDIEN"]
    P1["« 412 écoutes<br/>le 3 mars »"]
  end
  subgraph N2["CUMULÉ"]
    P2["« 118 219 vues<br/>depuis toujours »"]
  end
  subgraph N3["TOTAL DE PÉRIODE"]
    P3["« 900 écoutes<br/>entre janvier et<br/>décembre 2024 »"]
  end
  P1 -->|"se somme<br/>directement"| R1["Total d'une période"]
  P2 -->|"écart entre<br/>deux relevés"| R1
  P3 -->|"ne se découpe<br/>PAS"| R1
  </mermaid>
  <div class="caption">Mettre ces trois formes sur le même axe sans conversion produit des
    chiffres faux d'un facteur dix à cent.</div>

  <div class="box warn">
    <div class="lbl">Ce que ça a coûté, mesuré</div>
    <p>Une courbe additionnait un compteur cumulé et une quantité quotidienne :
      <strong>23 560</strong> écoutes annoncées pour un maximum réel de
      <strong>1 605</strong> par jour. Un autre jour, un sous-titre a annoncé
      <strong>16 568 594</strong> écoutes à un artiste qui en avait
      <strong>163 102</strong> — facteur 89 — parce qu'il additionnait des cumuls au lieu
      de quantités.</p>
  </div>

  <h3>Quatre horloges</h3>
  <p>La date d'une ligne ne vient pas du même endroit selon la source, et rien ne le
    déclarait — c'était la septième cause de l'audit. Chaque colonne de date dit
    désormais laquelle de ces quatre horloges l'a produite, et une seule d'entre elles
    porte un <em>instant</em> : les trois autres portent un jour calendaire, qu'aucune
    conversion de fuseau ne doit toucher.</p>
  <table>
    <thead><tr><th>Série</th><th>D'où vient sa date</th><th>Fuseau</th></tr></thead>
    <tbody>
      <tr><td>Spotify for Artists</td><td>colonne du fichier déposé</td><td>fuseau de publication de Spotify</td></tr>
      <tr><td>YouTube · SoundCloud · Instagram</td><td>heure de notre collecte</td><td>UTC</td></tr>
      <tr><td>Apple Music</td><td>nom du fichier exporté</td><td>fuseau de publication d'Apple</td></tr>
      <tr><td>Les bornes choisies par l'artiste</td><td>horloge du serveur d'affichage</td><td>heure locale</td></tr>
    </tbody>
  </table>
  <p class="tight">Une même colonne en porte même deux : les lignes écrites avant un
    changement de format sont des jours calendaires, celles d'après des instants UTC, et
    elles cohabitent dans la table. Mesuré : sur l'ère actuelle, <strong>zéro</strong>
    ligne YouTube change de jour selon le fuseau retenu — les collectes atterrissent à
    10 h UTC, loin de toute frontière. Le risque n'est donc pas de laisser ces dates
    tranquilles, c'est de les convertir sans distinguer les deux natures.</p>
</section>
"""
