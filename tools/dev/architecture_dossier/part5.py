PART5 = """
<section class="newpage">
  <h2>7 · Les cinq piliers de la qualité, et le sixième</h2>
  <p class="lead">La littérature en compte cinq. Quatre sont instrumentés ici. Tous
    regardent la <strong>source</strong> — et c'est exactement pour ça que le défaut le
    plus coûteux du dossier a pu passer.</p>

  <mermaid>
flowchart TB
  subgraph SRC["Ce qu'on COLLECTE — les quatre piliers instrumentés"]
    direction LR
    P1["FRAÎCHEUR<br/>la donnée est-elle<br/>arrivée à l'heure ?"]
    P2["VOLUME<br/>en bonne quantité ?"]
    P3["DISTRIBUTION<br/>les valeurs sont-elles<br/>plausibles ?"]
    P4["SCHÉMA<br/>la forme a-t-elle<br/>changé ?"]
  end
  subgraph OUT["Hors périmètre, assumé"]
    P5["LIGNAGE<br/>qui dépend de quoi"]
  end
  subgraph CALC["Ce qu'on CALCULE — le sixième, ajouté"]
    P6["ACCORD<br/>deux chemins vers le même<br/>nombre rendent-ils<br/>la même valeur ?"]
  end
  SRC --> X["Les tables brutes"]
  X --> CALC
  CALC --> Y["Les chiffres affichés"]
  </mermaid>

  <table>
    <thead><tr><th style="width:20%">Pilier</th><th style="width:16%">État</th><th>Ce qu'il regarde</th></tr></thead>
    <tbody>
      <tr><td><strong>Fraîcheur</strong></td><td>instrumenté</td>
        <td>Par locataire et par plateforme, en s'appuyant sur la date <em>portée par la
          donnée</em>, jamais sur l'heure d'écriture — une collecte peut écrire à l'heure
          des lignes vieilles de deux ans.</td></tr>
      <tr><td><strong>Volume</strong></td><td>instrumenté</td>
        <td>Les pics <em>et</em> les creux, ces derniers par locataire : une flotte en
          bonne santé masque un artiste muet.</td></tr>
      <tr><td><strong>Distribution</strong></td><td>instrumenté</td>
        <td>Dérive des variables du modèle, et retour à zéro d'un compteur cumulé —
          impossible par construction, donc détectable sans seuil.</td></tr>
      <tr><td><strong>Schéma</strong></td><td>instrumenté</td>
        <td>Comparaison quotidienne entre la forme déployée et la forme de référence.</td></tr>
      <tr><td><strong>Lignage</strong></td><td>hors périmètre</td>
        <td>Décision écrite, avec son déclencheur : le jour où une table source aura plus
          d'un consommateur, ou qu'un incident prendra plus d'une heure à attribuer.</td></tr>
      <tr><td><strong>Accord</strong></td><td><strong>ajouté</strong></td>
        <td>Pour une source quotidienne, le total « depuis le début » et la somme de sa
          série lisent la même table : ils <em>doivent</em> être égaux. Pour un compteur
          cumulé, la somme mesurée ne peut pas dépasser le compteur.</td></tr>
    </tbody>
  </table>

  <div class="box key">
    <div class="lbl">Pourquoi cet invariant plutôt qu'un seuil</div>
    <p>Un seuil se calibre, puis vieillit, puis crie ou se tait. L'égalité entre deux
      chemins de calcul est une <strong>propriété</strong> : elle ne dépend d'aucun
      réglage, et le jour où elle est violée, c'est qu'un des deux chemins a changé de
      sens. Vérifié : les deux rendent le même nombre à l'unité près.</p>
  </div>

  <h3>Un contrôle écrit qui n'a jamais été mis en service</h3>
  <p>La chaîne de contrôle qualité de 22 h est <strong>en pause depuis sa création</strong>
    — non pas « elle a cassé et on l'a coupée », mais « elle n'a jamais démarré ». La
    décision de l'y laisser est écrite et mesurée : ses cinq contrôles portent sur les
    fichiers déposés, et aucun artiste n'en a déposé depuis 95 jours. Elle porte un
    déclencheur vérifiable — le jour où un dépôt arrive, on la relance à la main et on lit
    ce qu'elle trouve pour de bon.</p>
  <div class="box"><div class="lbl">Le principe derrière</div>
    <p>Un détecteur qui tourne sur des données périmées produit du bruit, et un détecteur
      qui crie sur du juste finit désarmé. Mieux vaut une pause <em>datée et
      déclenchable</em> qu'une surveillance de façade.</p></div>
</section>

<section class="newpage">
  <h2>8 · La boucle de correction</h2>
  <p class="lead">Ce n'est pas une méthode générale : c'est la séquence qui a produit les
    six corrections, et dont chaque étape a rattrapé quelque chose que la précédente
    n'avait pas vu.</p>

  <mermaid>
flowchart TB
  A["Un défaut est signalé<br/>presque toujours par l'artiste"] --> B["MESURER<br/>sur les vraies données"]
  B --> C{"Le défaut est-il<br/>celui qu'on croyait ?"}
  C -->|"non — 2 fois sur 6"| B
  C -->|"oui"| D["BALAYER le dépôt<br/>pour les occurrences sœurs"]
  D --> E["CRITIQUER la conception<br/>avant d'écrire"]
  E --> F{"Verdict"}
  F -->|"à modifier"| E
  F -->|"à construire"| G["ÉCRIRE le correctif"]
  G --> H["ÉCRIRE le garde"]
  H --> I["MUTER : remettre le défaut<br/>et voir le garde ROUGIR"]
  I --> J{"Le garde<br/>a-t-il rougi ?"}
  J -->|"non"| H
  J -->|"oui"| K["CATALOGUER la classe"]
  K --> L["La classe ne peut plus<br/>revenir sans qu'on le sache"]
  </mermaid>

  <h3>Ce que chaque étape a rattrapé, concrètement</h3>
  <table>
    <thead><tr><th style="width:24%">Étape</th><th>Ce qu'elle a rattrapé</th></tr></thead>
    <tbody>
      <tr><td><strong>Mesurer</strong></td>
        <td>Deux conclusions tirées de la lecture du code étaient fausses. Une note
          expliquait depuis deux jours un écart qui n'existait plus.</td></tr>
      <tr><td><strong>Balayer</strong></td>
        <td>Environ 130 endroits portant l'une des cinq classes, dont deux défauts vivants :
          un sur de l'argent affiché, un sur un e-mail envoyé.</td></tr>
      <tr><td><strong>Critiquer avant d'écrire</strong></td>
        <td>Le verdict imprimé sur le rapport payant. Le correctif prévu ne touchait pas
          cette surface et ne l'aurait pas protégée.</td></tr>
      <tr><td><strong>Muter le garde</strong></td>
        <td>Une mutation est restée <strong>verte</strong> : le garde ne voyait pas ce
          qu'il prétendait garder. Un test a été ajouté pour l'atteindre.</td></tr>
      <tr><td><strong>Cataloguer</strong></td>
        <td>Six classes de plus, chacune avec un contrôle vu échouer puis réussir. Le
          catalogue en compte 255.</td></tr>
    </tbody>
  </table>

  <div class="box warn">
    <div class="lbl">Quatre fois où un garde a repris son auteur</div>
    <p>Un garde a détecté qu'on journalisait une exception en clair. <strong>Deux gardes
      ont échoué sur leur propre explication</strong> — le texte du correctif contenait les
      mots que le garde cherchait. Un prédicat a crié sur seize noms parfaitement valides
      avant de tenir sur six vraies dérives. Ces reprises ne sont pas des ratés : ce sont
      les seuls moments où l'on apprend qu'un garde regarde le texte au lieu de regarder
      la structure.</p>
  </div>
</section>
"""
