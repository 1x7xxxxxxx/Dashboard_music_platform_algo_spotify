PART2 = """
<section class="newpage">
  <h2>3 · Les couches bronze, argent et or</h2>
  <p class="lead">Une frontière, pas un stockage. Les trois couches ne sont pas trois
    copies des données : ce sont trois niveaux de <em>sens</em>, et deux d'entre eux sont
    calculés à la lecture.</p>

  <mermaid>
flowchart TB
  subgraph B["BRONZE — ce que la source a dit"]
    direction LR
    B1["Compteurs par vidéo<br/>relevés bruts, cumulés"]
    B2["Lignes du fichier déposé<br/>quantités du jour"]
    B3["Export de période<br/>un total, deux bornes"]
  end
  subgraph S["ARGENT — une ligne par entité et par jour"]
    direction LR
    S1["Écart quotidien<br/>par vidéo, par titre"]
    S2["Quantité du jour<br/>dédoublonnée"]
    S3["Période laissée<br/>à son grain"]
  end
  subgraph G["OR — une définition par métrique"]
    direction LR
    G1["Total par plateforme"]
    G2["Série pour la figure"]
    G3["Revenu mensuel"]
  end
  B1 -->|"écart sur le max<br/>déjà vu, par entité"| S1
  B2 -->|"un seul relevé<br/>par jour et par titre"| S2
  B3 -->|"périodes imbriquées<br/>jamais sommées à l'aveugle"| S3
  S1 & S2 --> G1
  S1 & S2 --> G2
  S3 --> G1
  G1 --> U1["Accueil · API<br/>PDF · e-mails"]
  G2 --> U1
  G3 --> U1
  </mermaid>

  <div class="box key">
    <div class="lbl">La règle qui rend la frontière tenable</div>
    <p>Une définition n'entre en couche or que si elle <strong>retire au moins deux
      endroits qui la recopiaient</strong>. Sans ce seuil, une couche sémantique devient
      une indirection de plus ; avec lui, chaque ajout supprime plus de code qu'il n'en
      crée.</p>
  </div>

  <h3>L'exemple qui a motivé la couche : le total de vues YouTube</h3>
  <p>Avant, la règle « le total est la somme des compteurs par vidéo » était correcte et
    <strong>recopiée à quatre endroits</strong>. Deux copies ont dérivé vers le compteur
    global de la chaîne. Le même artiste lisait donc deux nombres différents au même
    instant.</p>

  <mermaid>
flowchart LR
  subgraph AV["AVANT — quatre copies, deux dérives"]
    direction TB
    X1["Compteur de CHAÎNE"] --> Y1["Rétrospective<br/>120 627"]
    X1 --> Y2["Rapport PDF<br/>120 627"]
    X2["Somme par vidéo"] --> Y3["Accueil<br/>118 219"]
    X2 --> Y4["API<br/>118 219"]
  end
  subgraph AP["APRÈS — une définition"]
    direction TB
    Z1["COUCHE OR<br/>somme des compteurs<br/>par vidéo"] --> W1["Rétrospective"]
    Z1 --> W2["Rapport PDF"]
    Z1 --> W3["Accueil"]
    Z1 --> W4["API"]
  end
  AV ==> AP
  </mermaid>
  <div class="caption">Le compteur de chaîne n'a pas disparu : il reste lisible sur la page
    YouTube, où il est étiqueté comme tel et ne côtoie aucun chiffre qui le contredit.</div>

  <div class="box warn">
    <div class="lbl">Pourquoi le compteur de chaîne était faux</div>
    <p>Il avance par paliers et porte des vidéos qui ne sont plus celles de l'artiste —
      privées, supprimées, agrégats internes. Mesuré sur onze jours : il est resté figé,
      puis a sauté de <strong>+360 en une nuit</strong>, quand l'outil officiel de la
      plateforme annonçait <strong>64 vues</strong> sur toute la période.</p>
  </div>

  <h3>La matrice couche × plateforme</h3>
  <p>Ce que chaque plateforme apporte à chaque couche, et ce qu'elle n'apporte pas.</p>
  <table>
    <thead><tr>
      <th style="width:19%">Plateforme</th><th style="width:11%">Nature</th>
      <th style="width:24%"><span class="pill b">BRONZE</span></th>
      <th style="width:23%"><span class="pill s">ARGENT</span></th>
      <th style="width:23%"><span class="pill g">OR</span></th>
    </tr></thead>
    <tbody>
      <tr><td><strong>Spotify for Artists</strong></td><td>quotidien</td>
        <td>lignes du fichier déposé</td><td>un relevé par jour et par titre</td>
        <td>total · série</td></tr>
      <tr><td><strong>YouTube</strong></td><td>cumulé</td>
        <td>compteur par vidéo</td><td>écart quotidien par vidéo</td>
        <td>total · série</td></tr>
      <tr><td><strong>SoundCloud</strong></td><td>cumulé</td>
        <td>compteur par titre</td><td>écart quotidien par titre</td>
        <td>total · série</td></tr>
      <tr><td><strong>Apple Music</strong></td><td>période</td>
        <td>export daté par son nom</td><td>périodes non chevauchantes</td>
        <td>total annuel <em>seulement</em></td></tr>
      <tr><td><strong>Instagram</strong></td><td>état</td>
        <td>relevé d'abonnés</td><td>écart entre deux relevés</td>
        <td>— <em>un état ne s'additionne pas</em></td></tr>
      <tr><td><strong>Spotify (API)</strong></td><td>état</td>
        <td>popularité, catalogue</td><td>historique de popularité</td>
        <td>— <em>indice, pas volume</em></td></tr>
      <tr><td><strong>Meta Ads</strong></td><td>quotidien</td>
        <td>26 tables de ventilation</td><td>dépense et impressions du jour</td>
        <td>dépense mensuelle</td></tr>
      <tr><td><strong>Distributeurs · droits</strong></td><td>période</td>
        <td>lignes de vente</td><td>agrégat mensuel</td>
        <td>revenu mensuel unifié</td></tr>
    </tbody>
  </table>

  <div class="box">
    <div class="lbl">Deux absences volontaires en couche or</div>
    <p>Les <strong>abonnés Instagram</strong> et la <strong>popularité Spotify</strong>
      sont des <em>états</em>, pas des flux : on ne les additionne pas sur une période, on
      regarde de combien ils ont bougé. Leur donner une case « total » aurait été le même
      défaut que d'additionner un compteur cumulé.</p>
  </div>
</section>
"""
