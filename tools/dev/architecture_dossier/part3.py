PART3 = """
<section class="newpage">
  <h2>4 · Une fiche par plateforme</h2>
  <p class="lead">Chacune a un piège qui lui est propre. Les connaître est la moitié du
    travail de qualité.</p>

  <h3>Spotify for Artists — la seule source vraiment quotidienne</h3>
  <mermaid>
flowchart LR
  A["Export déposé<br/>par l'artiste"] --> B["BRONZE<br/>une ligne par titre<br/>et par jour"]
  B --> C{"Deux dépôts<br/>pour le même jour ?"}
  C -->|"oui"| D["On garde le<br/>relevé le plus fort"]
  C -->|"non"| E["Tel quel"]
  D & E --> F["ARGENT<br/>quantité du jour"]
  F --> G["OR — total et série"]
  B -.->|"écartée"| H["Ligne « Total »<br/>du fichier"]
  </mermaid>
  <div class="box warn"><div class="lbl">Le piège</div>
    <p>Le fichier contient une ligne d'agrégat qui ressemble à un titre. La compter double
      tous les chiffres. Elle est écartée à chaque lecture, et un contrôle automatique
      vérifie que la règle n'a disparu d'aucune requête.</p></div>

  <h3>YouTube — le bon compteur n'est pas celui qu'on croit</h3>
  <mermaid>
flowchart LR
  A["API YouTube"] --> B1["Compteur de CHAÎNE<br/>par paliers, pollué"]
  A --> B2["Compteur PAR VIDÉO"]
  B2 --> C["Écart depuis le<br/>maximum déjà vu<br/>de CETTE vidéo"]
  C --> D{"Le relevé précédent<br/>date-t-il de la veille ?"}
  D -->|"oui"| E["ARGENT<br/>écart du jour"]
  D -->|"non"| F["Écart écarté<br/>trou de collecte"]
  E --> G["OR"]
  B1 -.->|"abonnés<br/>uniquement"| G2["Page YouTube"]
  </mermaid>
  <div class="box warn"><div class="lbl">Le piège</div>
    <p>L'écart se prend <strong>par vidéo avant d'additionner</strong>. Le prendre sur la
      somme ferait apparaître le cumul entier d'une vidéo le jour de sa première
      collecte — un pic qui n'est pas une écoute.</p></div>

  <h3>SoundCloud — même forme, et une panne qui écrit des zéros</h3>
  <mermaid>
flowchart LR
  A["API SoundCloud"] --> B["Compteur par titre"]
  B --> C["Écart depuis le max<br/>déjà vu du titre"]
  C --> D["ARGENT"] --> E["OR"]
  B --> F{"Un compteur cumulé<br/>revient à zéro ?"}
  F -->|"oui"| G["ALERTE<br/>on signale,<br/>on ne réécrit pas"]
  </mermaid>
  <div class="box warn"><div class="lbl">Le piège, arrivé pour de vrai</div>
    <p>Une collecte ratée a écrit <strong>19 compteurs cumulés sur 19 à zéro</strong>. Ni
      la fraîcheur ni la détection de pics ne pouvaient le voir : les lignes étaient bien
      arrivées, elles étaient toutes fausses. Un compteur cumulé ne redescend jamais —
      c'est ce qui rend le contrôle possible sans seuil arbitraire.</p></div>

  <h3>Apple Music — un total de période, jamais une série</h3>
  <mermaid>
flowchart LR
  A["Export<br/>« 2015-06-30 → 2026-09-04 »"] --> B["Les deux bornes se lisent<br/>dans le NOM du fichier"]
  B --> C{"L'export tient-il<br/>dans une année civile ?"}
  C -->|"oui"| D["Un point annuel"]
  C -->|"non"| E["Écarté de la série<br/>recouvrirait les années<br/>qu'il contient"]
  D --> F["OR — total annuel"]
  D -.->|"jamais étalé<br/>sur 365 jours"| G["Série quotidienne"]
  </mermaid>
  <div class="box warn"><div class="lbl">Le piège</div>
    <p>Étaler 900 écoutes de 2024 sur 366 jours inventerait 2,46 écoutes par jour que
      personne n'a mesurées. Apple n'apparaît donc que sur le pas annuel, et l'interface le
      dit à l'endroit où l'artiste pourrait s'en étonner.</p></div>

  <h3>Instagram, Meta Ads et les distributeurs</h3>
  <table>
    <thead><tr><th style="width:22%">Source</th><th style="width:26%">Ce qu'elle rend</th><th>Le piège</th></tr></thead>
    <tbody>
      <tr><td><strong>Instagram</strong></td><td>un état d'abonnés</td>
        <td>Un état ne s'additionne pas. On compare deux relevés, et sans deux relevés on
          n'affiche pas d'écart — jamais « +0 », qui serait une affirmation qu'on n'a pas
          mesurée. Les mentions « j'aime » d'une publication sont un cumul : les sommer par
          mois de publication attribue au mois tout ce qui s'est accumulé depuis.</td></tr>
      <tr><td><strong>Meta Ads</strong></td><td>26 tables de ventilation</td>
        <td>Les ventilations sont des vues différentes du même budget : additionner deux
          grains double la dépense. Une seule chaîne écrit ces tables depuis qu'un double
          écrivain a gonflé la dépense d'un facteur deux.</td></tr>
      <tr><td><strong>Distributeurs<br/>et droits</strong></td><td>lignes de vente,
        agrégées au mois</td>
        <td>Le mois est le grain natif : il n'existe aucune fenêtre exacte plus fine. Une
          période demandée est donc élargie aux mois entiers, et la période réellement
          couverte est affichée — un réglage qu'on ne peut pas honorer se dit.</td></tr>
    </tbody>
  </table>
</section>

<section class="newpage">
  <h2>5 · Les traitements programmés</h2>
  <p class="lead">Treize chaînes. Onze collectent ou entretiennent, deux surveillent.</p>

  <div class="tl">
    <div class="trow taxis"><span class="tname"></span><span class="ttrack"><span class="ttick" style="margin-left:0.00%">5&nbsp;h</span><span class="ttick" style="margin-left:15.85%">9&nbsp;h</span><span class="ttick" style="margin-left:15.85%">13&nbsp;h</span><span class="ttick" style="margin-left:15.85%">17&nbsp;h</span><span class="ttick" style="margin-left:15.85%">21&nbsp;h</span></span></div>
    <div class="trow"><span class="tname">Meta Ads</span><span class="ttrack"><span class="tmark col" style="margin-left:0.00%"><i></i>5&nbsp;h</span></span></div><div class="trow"><span class="tname">Spotify (API)</span><span class="ttrack"><span class="tmark col" style="margin-left:9.52%"><i></i>7&nbsp;h</span></span></div><div class="trow"><span class="tname">YouTube</span><span class="ttrack"><span class="tmark col" style="margin-left:14.29%"><i></i>8&nbsp;h</span></span></div><div class="trow"><span class="tname">SoundCloud</span><span class="ttrack"><span class="tmark col" style="margin-left:19.05%"><i></i>9&nbsp;h</span></span></div><div class="trow"><span class="tname">Instagram</span><span class="ttrack"><span class="tmark col" style="margin-left:23.81%"><i></i>10&nbsp;h</span></span></div><div class="trow"><span class="tname">Scoring ML</span><span class="ttrack"><span class="tmark cal" style="margin-left:28.57%"><i></i>11&nbsp;h</span></span></div><div class="trow"><span class="tname">Rapport d'onboarding</span><span class="ttrack"><span class="tmark rel" style="margin-left:19.05%"><i></i>9&nbsp;h</span></span></div><div class="trow"><span class="tname">Rappel de fin d'essai</span><span class="ttrack"><span class="tmark rel" style="margin-left:19.05%"><i></i>9&nbsp;h</span></span></div><div class="trow"><span class="tname">Contrôle qualité</span><span class="ttrack"><span class="tmark sur" style="margin-left:80.95%"><i></i>22&nbsp;h</span></span></div><div class="trow"><span class="tname">Alerte consolidée</span><span class="ttrack"><span class="tmark sur" style="margin-left:85.71%"><i></i>23&nbsp;h</span></span></div>
    <div class="tleg"><span class="col">collecte</span><span class="cal">calcul</span>
      <span class="rel">relation client</span><span class="sur">surveillance</span></div>
  </div>

  <table>
    <thead><tr><th style="width:26%">Chaîne</th><th style="width:15%">Cadence</th><th>Rôle</th></tr></thead>
    <tbody>
      <tr><td>Meta Ads</td><td>tous&nbsp;les&nbsp;jours,&nbsp;5 h</td><td>dépense et performance publicitaire</td></tr>
      <tr><td>Spotify (API)</td><td>tous&nbsp;les&nbsp;jours,&nbsp;7 h</td><td>catalogue, popularité, historique d'artiste</td></tr>
      <tr><td>YouTube</td><td>tous&nbsp;les&nbsp;jours,&nbsp;8 h</td><td>chaîne, vidéos, compteurs par vidéo</td></tr>
      <tr><td>SoundCloud</td><td>tous&nbsp;les&nbsp;jours,&nbsp;9 h</td><td>compteurs par titre</td></tr>
      <tr><td>Instagram</td><td>tous&nbsp;les&nbsp;jours,&nbsp;10 h</td><td>abonnés, publications, statistiques</td></tr>
      <tr><td>Scoring ML</td><td>tous&nbsp;les&nbsp;jours,&nbsp;11 h</td><td>prédictions par titre</td></tr>
      <tr><td>Rapport d'onboarding</td><td>tous&nbsp;les&nbsp;jours,&nbsp;9 h</td><td>premier bilan, une fois par artiste</td></tr>
      <tr><td>Rappel de fin d'essai</td><td>tous&nbsp;les&nbsp;jours,&nbsp;9 h</td><td>relation client</td></tr>
      <tr><td>Contrôle qualité</td><td>tous&nbsp;les&nbsp;jours,&nbsp;22 h</td><td>cohérence des données déposées <em>(en pause — voir plus bas)</em></td></tr>
      <tr><td><strong>Alerte consolidée</strong></td><td>tous&nbsp;les&nbsp;jours,&nbsp;23 h</td><td><strong>dix-neuf contrôles, un seul e-mail</strong></td></tr>
      <tr><td>Renouvellement de jeton Meta</td><td>chaque&nbsp;lundi,&nbsp;7 h</td><td>entretien des accès</td></tr>
      <tr><td>Étiquetage des résultats ML</td><td>chaque&nbsp;lundi,&nbsp;6 h</td><td>boucle d'apprentissage</td></tr>
      <tr><td>Résumé hebdomadaire</td><td>chaque&nbsp;lundi,&nbsp;8 h</td><td>e-mail à l'artiste</td></tr>
    </tbody>
  </table>

  <h3>L'entonnoir du soir</h3>
  <p>Dix-neuf contrôles indépendants convergent vers <strong>un seul message</strong>. Le
    principe est explicite : une alerte nomme un symptôme et une action, jamais un code, et
    aucun contrôle ne réécrit quoi que ce soit en base.</p>

  <mermaid>
flowchart LR
  subgraph C["Dix-neuf contrôles indépendants"]
    direction TB
    K1["Fraîcheur des sources"]
    K2["Volume — pics et creux"]
    K3["Compteurs remis à zéro"]
    K4["Chiffres en désaccord"]
    K5["Identifiants et jetons"]
    K6["Facturation"]
    K7["Erreurs applicatives"]
    K8["Sauvegarde hors-site"]
    K9["… et onze autres"]
  end
  K1 & K2 & K3 & K4 & K5 & K6 & K7 & K8 & K9 --> M["Un seul e-mail<br/>le soir"]
  M --> H{"Rien à signaler ?"}
  H -->|"oui"| S["Silence"]
  H -->|"non"| E["Symptôme + action,<br/>par locataire"]
  </mermaid>
  <div class="caption">Un contrôle qui échoue ne fait pas échouer la chaîne : il pousse son
    constat, et l'envoi lit tout ce qui est arrivé.</div>
</section>
"""
