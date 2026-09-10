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


  <h3 class="newpage">Le trajet complet d'un KPI, plateforme par plateforme</h3>
  <p>Les fiches ci-dessus disent le piège de chaque source. Celles qui suivent disent le
    <em>trajet</em> : pour un chiffre précis, ce que la plateforme a écrit, ce qu'on en
    fait, et d'où sort la valeur affichée. Les nombres sont ceux de l'artiste 1, relevés
    le 2026-09-10 — un schéma sans mesure est un dessin.</p>
  <p class="tight">Trois couleurs, trois rôles, et la même lecture partout :
    <span class="pill b">BRONZE</span> ce que la source a écrit, jamais retouché —
    <span class="pill s">ARGENT</span> la nature de la série résolue une fois —
    <span class="pill g">OR</span> une définition par métrique, et une seule.
    L'argent porte souvent <em>deux</em> branches : la série et le total ne posent pas la
    même question au même relevé.</p>

  <h4>Spotify for Artists — KPI « écoutes totales » : 163 088</h4>
  <mermaid>
flowchart LR
  subgraph B["BRONZE"]
    B1["s4a_song_<br/>timeline<br/>13 794 lignes<br/>11 titres · 1 254 jours"]
  end
  subgraph S["ARGENT"]
    S1["Nature : QUOTIDIEN<br/>rien à convertir"]
    S2["MAX par jour et par titre<br/>un re-dépôt du même jour<br/>ne compte qu'une fois"]
  end
  subgraph G["OR"]
    G1["v_platform_<br/>totals<br/>platform = spotify<br/>163 088"]
  end
  B1 --> S1 --> S2 --> G1
  B1 -.->|"ligne « Total »<br/>du fichier : ÉCARTÉE"| S1
  </mermaid>
  <p class="tight">La seule source réellement quotidienne. Le seul travail de l'argent est
    de refuser le double comptage — celui d'un re-dépôt, et celui de la ligne d'agrégat
    qui ressemble à un titre.</p>

  <h4>YouTube — KPI « vues totales » : 118 219</h4>
  <mermaid>
flowchart LR
  subgraph B["BRONZE"]
    B1["youtube_video_<br/>stats<br/>1 734 lignes<br/>67 vidéos · 34 jours"]
    B2["youtube_channel_<br/>history<br/>compteur de CHAÎNE"]
  end
  subgraph S["ARGENT"]
    S1["Pour la SÉRIE<br/>cumul par vidéo<br/>écart jour moins veille<br/>jours consécutifs seuls"]
    S2["Pour le TOTAL<br/>dernier compteur<br/>de chaque vidéo"]
    S3["Écarts jetés : COMPTÉS<br/>et affichés sous la figure"]
  end
  subgraph G["OR"]
    G1["v_platform_<br/>totals<br/>118 219"]
    G2["Abonnés<br/>aucune autre source"]
  end
  B1 --> S1 --> S3
  B1 --> S2 --> G1
  B2 --> G2
  B2 -.->|"JAMAIS pour les vues<br/>prouvé ~10x faux"| G1
  </mermaid>
  <div class="box warn"><div class="lbl">Les deux compteurs</div>
    <p>La chaîne expose un total de vues, et il est faux d'un facteur dix : il agrège une
      audience que nos vidéos ne couvrent pas. Le total juste est la somme des compteurs
      PAR VIDÉO. Quatre surfaces sur six lisaient le mauvais avant que la couche or
      n'existe ; le même compteur reste la bonne source pour les ABONNÉS, qui n'en ont pas
      d'autre. Une source n'est ni bonne ni mauvaise — elle l'est pour une métrique.</p>
  </div>

  <h4>SoundCloud — KPI « écoutes totales » : 23 486</h4>
  <mermaid>
flowchart LR
  subgraph B["BRONZE"]
    B1["soundcloud_tracks_<br/>daily<br/>349 lignes<br/>19 titres · 19 jours"]
  end
  subgraph S["ARGENT"]
    S1["Pour la SÉRIE<br/>écart par titre,<br/>jours consécutifs"]
    S2["Pour le TOTAL<br/>dernier compteur<br/>de chaque titre"]
    S3["Remise à zéro détectée<br/>= panne, pas une baisse"]
  end
  subgraph G["OR"]
    G1["v_platform_<br/>totals<br/>23 486"]
  end
  B1 --> S1 --> S3
  B1 --> S2 --> G1
  </mermaid>
  <p class="tight">Même forme que YouTube, avec un piège de plus : l'API a déjà répondu
    zéro sur des titres vivants. Un cumul qui redescend n'est pas une écoute perdue, c'est
    une panne — la traiter comme une mesure écrirait des zéros dans l'histoire.</p>

  <h4>Apple Music — KPI « écoutes » : 3 267, et pas de série</h4>
  <mermaid>
flowchart LR
  subgraph B["BRONZE"]
    B1["apple_songs_<br/>performance<br/>11 lignes<br/>UN instantané par dépôt"]
  end
  subgraph S["ARGENT"]
    S1["Nature : TOTAL<br/>DE PÉRIODE<br/>la période est dans<br/>le NOM du fichier"]
    S2["Découpage non chevauchant<br/>« depuis le début »<br/>contient déjà « 2024 »"]
  end
  subgraph G["OR"]
    G1["Total de période<br/>3 267"]
    G2["Série quotidienne<br/>AUCUNE — et c'est dit"]
  end
  B1 --> S1 --> S2 --> G1
  S1 -.->|"rien à découper<br/>en jours"| G2
  </mermaid>
  <div class="box warn"><div class="lbl">Ce que l'or refuse de fabriquer</div>
    <p>Apple ne livre pas de série : additionner ses relevés jour par jour reviendrait à
      inventer une répartition. La couche or rend donc un total et <em>déclare</em> qu'il
      n'y a pas de courbe, au lieu de tracer une plateforme muette à zéro. Un chiffre
      absent qui se dit vaut mieux qu'un zéro qui ment.</p>
  </div>

  <h4>Instagram — KPI « abonnés » : de 1 526 à 1 606</h4>
  <mermaid>
flowchart LR
  subgraph B["BRONZE"]
    B1["instagram_daily_<br/>stats<br/>29 relevés"]
    B2["instagram_<br/>media<br/>plafonné à 10 pages"]
  end
  subgraph S["ARGENT"]
    S1["Nature : NIVEAU<br/>ni cumul,<br/>ni quantité du jour"]
    S2["Écart = dernier moins premier<br/>sur la période DEMANDÉE"]
    S3["Lecture tronquée<br/>= statut « partial »<br/>jamais « success »"]
  end
  subgraph G["OR"]
    G1["Abonnés<br/>de 1 526 à 1 606"]
  end
  B1 --> S1 --> S2 --> G1
  B2 --> S3
  </mermaid>
  <p class="tight">Un nombre d'abonnés n'est ni un cumul ni une quantité du jour : c'est un
    NIVEAU. Sa variation se lit entre deux relevés de la période demandée — et le compteur
    lui-même ne se bornait pas, ce qui faisait afficher un compteur hors période à côté
    d'un écart borné. Le plafond de pagination, lui, laisse des publications hors de la
    base : la collecte s'enregistre alors « partielle », jamais « réussie ».</p>

  <h4>Meta Ads — KPI « dépense » : 3 088 EUR sur 205 jours</h4>
  <mermaid>
flowchart TB
  subgraph B["BRONZE — 26 tables, par grain et par découpage"]
    B1["meta_insights_<br/>performance_day<br/>231 lignes · 205 jours"]
    B2["meta_insights<br/>grain publicité"]
  end
  subgraph S["ARGENT"]
    S1["Nature : QUOTIDIEN<br/>la journée est celle de Meta,<br/>arrêtée dans SON fuseau"]
    S2["Un compte publicitaire<br/>collecté UNE fois par nuit"]
  end
  subgraph G["OR"]
    G1["Dépense de la période<br/>3 088 EUR"]
    G2["v_artist_monthly_<br/>revenue"]
    G3["ROI = revenu moins dépense<br/>TROIS états"]
  end
  B1 --> S1 --> S2 --> G1 --> G3
  B2 --> S2
  G2 --> G3
  G3 -.->|"revenu absent"| G4["« illisible »<br/>jamais zéro"]
  </mermaid>
  <div class="box warn"><div class="lbl">Le ROI a trois états, pas deux</div>
    <p>Positif, négatif, et <em>illisible</em>. Un mois sans dépense publicitaire déclarée
      n'a pas un ROI de zéro : il n'en a pas. Le troisième état existe parce que la
      jointure entre revenu mensuel et dépense quotidienne comblait les trous avec des
      zéros — et un zéro sur de l'argent est la forme de mensonge la plus coûteuse de ce
      produit.</p>
  </div>

  <h4>Ce que les six ont en commun</h4>
  <mermaid>
flowchart TB
  subgraph B["BRONZE — 64 tables, jamais retouchées"]
    B1["quotidien<br/>Spotify · Meta"]
    B2["cumul par entité<br/>YouTube · SoundCloud"]
    B3["total de période<br/>Apple"]
    B4["niveau<br/>Instagram"]
  end
  subgraph S["ARGENT — la nature résolue UNE fois"]
    S1["tel quel"]
    S2["écart par entité<br/>ou dernier compteur"]
    S3["découpage<br/>non chevauchant"]
    S4["dernier moins premier"]
  end
  subgraph G["OR — une définition par métrique"]
    G1["v_platform_<br/>totals"]
    G2["v_artist_monthly_<br/>revenue"]
  end
  B1 --> S1
  B2 --> S2
  B3 --> S3
  B4 --> S4
  S1 --> G1
  S2 --> G1
  S1 --> G2
  G1 --> U["Accueil · API · PDF<br/>e-mail hebdomadaire<br/>Data Wrapped"]
  G2 --> U
  </mermaid>
  <p>C'est la seule figure du dossier qui explique <em>pourquoi</em> la couche existe.
    Quatre natures de série entrent ; si chaque surface les reconvertit pour son compte,
    il y a autant de définitions que de surfaces — et c'est exactement ce qui a été mesuré
    avant : le même artiste lisait <strong>120 627</strong> vues YouTube sur une page et
    <strong>118 219</strong> sur une autre, au même instant. La conversion se fait une
    fois, à l'argent ; la définition vit une fois, à l'or ; les cinq surfaces la lisent.</p>
  <p class="tight">Et rien de tout cela n'est une base de données nouvelle. Mesuré le
    2026-09-10 : zéro base, zéro schéma, zéro table portant ces noms, zéro vue
    matérialisée. L'or est <strong>deux vues Postgres ordinaires</strong>, calculées à la
    lecture. La couche est une frontière, pas un stockage — et l'argent n'est pas une
    table non plus : c'est la décision qui vit à l'intérieur de la vue et du module de
    séries.</p>

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
