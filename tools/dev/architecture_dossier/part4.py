PART4 = """
<section class="newpage">
  <h2>6 · Les six défauts rencontrés, et comment ils sont tenus</h2>
  <p class="lead">Chacun a été mesuré, corrigé, doté d'un garde, et le garde a été vu
    <strong>échouer</strong> avant d'être gardé. Un test qu'on n'a jamais vu rouge ne
    prouve rien.</p>

  <h3>6.1 · La fenêtre élargie à son seau</h3>
  <div class="stats">
    <div class="stat bad"><div class="v">×2,7</div><div class="k">dessiné contre mesuré,
      sur « 12 mois · par année »</div></div>
    <div class="stat"><div class="v">8 490</div><div class="k">écoutes réellement dans la fenêtre</div></div>
    <div class="stat bad"><div class="v">23 251</div><div class="k">écoutes tracées</div></div>
  </div>
  <mermaid>
flowchart TB
  subgraph AV["AVANT"]
    A1["Période demandée<br/>11 sept. 2025 → 10 sept. 2026"] --> A2["Borne ramenée au<br/>1ᵉʳ janvier 2025"]
    A2 --> A3["Le seau « 2025 » embarque<br/>TOUTE l'année 2025"]
    A3 --> A4["23 251 tracées<br/>huit mois non demandés"]
  end
  subgraph AP["APRÈS"]
    B1["Période demandée<br/>11 sept. 2025 → 10 sept. 2026"] --> B2["Les lignes sont DÉCOUPÉES<br/>avant d'être sommées"]
    B2 --> B3["Le seau de bord ne porte<br/>que ses jours utiles"]
    B3 --> B4["8 490 tracées"]
  end
  </mermaid>
  <div class="box ok"><div class="lbl">Le garde</div>
    <p>Un invariant sans seuil : <strong>la figure ne peut pas dessiner plus que ce que la
      fenêtre contient</strong>. Il est vérifié sur toutes les combinaisons de période et
      de pas — le produit cartésien des menus, qui est le véritable espace de rendu et
      n'était couvert que par un point.</p></div>

  <h3>6.2 · Le prédicat symétrique pour une vérité qui ne l'est pas</h3>
  <p>« Avant la première mesure » et « après la dernière » étaient traités du même
    argument. Ils ne sont pas symétriques : avant, la plateforme n'existait pas dans nos
    données et zéro est vrai ; après, elle existe toujours — c'est nous qui avons cessé de
    regarder.</p>
  <mermaid>
flowchart LR
  subgraph AV["AVANT — la bande retombe"]
    direction TB
    C1["Jours 1-5 : mesurés"] --> C2["10 · 20 · 30 · 40 · 50"]
    C3["Jours 6-20 : NON mesurés"] --> C4["0 · 0 · 0 … 0"]
    C2 --> C5["Lecture de l'artiste :<br/>« j'ai tout perdu »"]
    C4 --> C5
  end
  subgraph AP["APRÈS — la bande s'arrête"]
    direction TB
    D1["Jours 1-5 : mesurés"] --> D2["10 · 20 · 30 · 40 · 50"]
    D3["Jours 6-20 : inconnus"] --> D4["la courbe s'interrompt<br/>et la note le compte"]
    D2 --> D5["Lecture de l'artiste :<br/>« on a arrêté de mesurer »"]
    D4 --> D5
  end
  </mermaid>

  <h3>6.3 · Un verdict tiré d'une valeur que personne n'a lue</h3>
  <div class="box warn"><div class="lbl">Le cas le plus grave du dossier</div>
    <p>Sur une base injoignable, le rapport <strong>payant</strong> imprimait
      « Rentable ». Trois couches se couvraient l'une l'autre : la lecture échouée
      rendait zéro, le zéro devenait un net nul, et le net nul passait le test « supérieur
      ou égal à zéro ».</p></div>
  <mermaid>
flowchart LR
  subgraph AP["APRÈS"]
    direction LR
    A2["Base<br/>injoignable"] --> B2["Lecture échouée,<br/>et elle le DIT"] --> C2["Revenu inconnu<br/>Dépense inconnue"] --> D2{"Les deux côtés<br/>connus ?"}
    D2 -->|"non"| E2["Chiffres indisponibles.<br/>Ce n'est pas un résultat nul."]
  end
  subgraph AV["AVANT"]
    direction LR
    A["Base<br/>injoignable"] --> B["Lecture échouée,<br/>en silence"] --> C["Revenu 0<br/>Dépense 0"] --> D{"Net ≥ 0 ?"}
    D -->|"oui"| E["RENTABLE<br/>sur le rapport payant"]
  end
  </mermaid>
  <div class="box ok"><div class="lbl">Ce qui a changé structurellement</div>
    <p>Trois états au lieu de deux : <strong>mesuré</strong>, <strong>rien mesuré</strong>,
      <strong>pas lisible</strong>. Sans le troisième, une panne emprunte le texte d'une
      absence légitime. Et ce défaut a été trouvé par une <em>revue de conception lancée
      avant l'écriture du correctif</em> : la correction prévue ne touchait pas la surface
      qui recalculait son propre verdict.</p></div>

  <h3>6.4 · Le zéro fabriqué, envoyé par e-mail</h3>
  <p>Un artiste sans données recevait « 0 écoute cette semaine », « 0,00 € dépensés » et
    « taux de clic : 0,00 % ». Le dernier est arithmétiquement impossible : sans
    impression, le taux n'est pas nul, il est indéfini.</p>
  <mermaid>
flowchart LR
  A["Aucune donnée<br/>pour ce locataire"] --> B{"La requête<br/>remplit-elle le vide ?"}
  B -->|"AVANT — oui"| C["0"] --> D["« 0 écoute cette semaine »<br/>une affirmation"]
  B -->|"APRÈS — non"| E["inconnu"] --> F["« N/A »<br/>une absence"]
  </mermaid>
  <div class="box"><div class="lbl">Le détail qui rend le correctif possible</div>
    <p>Refuser d'inventer un zéro fait apparaître des valeurs vides dans un gabarit qui ne
      les acceptait pas — et un correctif honnête se serait alors payé d'un e-mail non
      envoyé. Un formateur dédié rend « N/A » plutôt que de faire échouer l'envoi.</p></div>

  <h3>6.5 · Une page qui lit une table que personne ne remplit</h3>
  <mermaid>
flowchart LR
  A["Page de qualité"] -->|"AVANT"| B["Table quasi vide<br/>2 lignes"]
  B --> C["Panneau vide,<br/>sans explication"]
  D["Registre réellement écrit<br/>à chaque collecte<br/>2 196 lignes"] -.->|"ignoré"| A
  A2["Page de qualité"] -->|"APRÈS"| D2["Registre réellement écrit"]
  D2 --> C2["Cinq chaînes,<br/>leurs volumes et leurs durées"]
  </mermaid>
  <div class="box warn"><div class="lbl">Ce que ce cas apprend</div>
    <p>Le défaut n'était pas ignoré : il était <strong>documenté depuis trois mois</strong>,
      et la seule action visible qu'il avait déclenchée était de <em>faire taire le
      détecteur qui le signalait</em>. Rendre un détecteur muet n'est pas fermer ce qu'il
      signalait.</p></div>

  <h3>6.6 · Une règle recopiée est une règle qui divergera</h3>
  <mermaid>
flowchart TB
  A["Une règle correcte,<br/>écrite quatre fois"] --> B["Copie 1 — reste juste"]
  A --> C["Copie 2 — reste juste"]
  A --> D["Copie 3 — DÉRIVE"]
  A --> E["Copie 4 — DÉRIVE"]
  D & E --> F["Deux nombres différents<br/>pour le même artiste,<br/>au même instant"]
  F ==> G["Une seule définition,<br/>en couche or"]
  </mermaid>
  <div class="box key"><div class="lbl">Le chiffre qui justifie la couche</div>
    <p>La duplication mesurée dans le dépôt : la même règle de filtrage écrite dans
      <strong>35 fichiers</strong>, une même requête de prédiction recopiée dans
      <strong>15</strong>, et six définitions concurrentes d'un même indicateur
      publicitaire. Une couche conformée se justifie par le <strong>désaccord</strong>, pas
      par le volume de données.</p></div>
</section>
"""
