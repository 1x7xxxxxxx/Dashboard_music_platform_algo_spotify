# Idées de graphiques, page par page (R271, note L91)

Réponse à « + toute autre idée de graphique et de datas » sur YouTube, SoundCloud,
Instagram, Hypeddit, Wrapped, Meta Ads, Revenus, Compte, Saisie S4A. **Chaque idée lit une
donnée qui existe déjà en base** (colonne citée) — aucune ne demande une collecte neuve.
Celles qui lisent une table brute (`youtube_video_stats`, `instagram_media_insights`,
`s4a_song_playlist_adds`, `etl_run_log`) passeront d'abord par une vue or si elles sont
retenues (cliquet `tests/test_the_bronze_boundary_only_tightens.py`). Elles ne sont PAS construites : ce sont des propositions à trancher ; une idée
retenue devient une ligne de roadmap, avec sa question et son test.

Le filtre appliqué avant d'écrire une idée : elle répond à une **décision** (« est-ce que je
refais ça ? », « où je mets le prochain euro ? »), elle ne redit pas un graphique existant
de la même page (garde `tests/test_no_two_figures_on_a_page_share_a_fingerprint.py`), et
elle ne trace pas un cumul comme un quotidien.

| page | idée | la décision | donnée (vue or · colonnes) |
|---|---|---|---|
| YouTube | Vues gagnées dans les 7 jours suivant chaque publication, vidéo par vidéo, à âge égal | quel format de vidéo refaire | `youtube_video_stats` · `view_count` (différence entre relevés) |
| YouTube | Taux like / vue par vidéo, trié (Pareto) | quelle vidéo fait réagir, pas seulement regarder | `youtube_video_stats` · `like_count / view_count` (ratio par `utils.ratios`) |
| SoundCloud | Reposts par titre rapportés aux écoutes | quel titre circule par le bouche-à-oreille | `v_soundcloud_track_daily` · `reposts_lisibles`, `plays` |
| SoundCloud | Commentaires par mois, tous titres | la communauté parle-t-elle encore | `v_soundcloud_track_daily` · `comments_lisibles` |
| Instagram | Engagement par publication et par mois (likes + commentaires ÷ publications) | publier plus, ou mieux | `v_instagram_media_monthly` · `likes`, `comments`, `posts` |
| Instagram | Vues et interactions par publication, depuis R273 | quel post porte la musique | `instagram_media_insights` · `impressions` (= `views`), `engagement` (= `total_interactions`) |
| Hypeddit | Taux de clic visite → plateforme par campagne | quelle page de lien convertit | `v_hypeddit_daily` · `clicks / visits` |
| Hypeddit | Visites Hypeddit posées sur la dépense Meta du même jour | le lien intelligent capte-t-il le trafic payé | `v_hypeddit_daily` · `visits` ; `v_meta_daily` · `spend` |
| Meta Ads | Coût par clic selon l'appel à l'action (« Écouter », « En savoir plus »…) | quel bouton d'annonce mettre | `v_meta_ad_daily` · `call_to_action`, `spend`, `clicks` |
| Meta Ads | Fatigue d'une annonce : CTR par semaine depuis son lancement | quand couper ou renouveler une créa | `v_meta_ad_daily` · `clicks / impressions` par `ad_id` et semaine d'âge |
| Revenus | Part SACEM contre distributeur, mois par mois | d'où vient l'argent, et sa régularité | `v_artist_monthly_cashflow` · `source`, `amount_eur` |
| Revenus | Délai de versement SACEM (mois de droits → mois payé) | quand l'argent d'une sortie arrive | `v_sacem_monthly` · `year`, `month`, `line_type` |
| Wrapped | « Ton mois record » : le mois de plus d'écoutes, par plateforme | un chiffre à partager | `v_platform_totals` / séries or par mois |
| Compte | Ce que la collecte a rapporté ce mois : jours collectés par plateforme | la connexion marche-t-elle chez moi | `etl_run_log` · `status`, `rows_inserted` (déjà agrégé par `onboarding_journey`) |
| Saisie S4A | Ajouts en playlist saisis contre écoutes du lendemain | une playlist éditoriale a-t-elle payé | `s4a_song_playlist_adds` ; `v_s4a_song_daily` · `streams` |

Trois idées demandent ta réponse avant d'être utiles (lignes 🙋 de la roadmap) : le seuil
de déclenchement de l'algorithme posé sur la courbe Meta × Spotify (note L268, que tu as
différée), et les graphiques externes dont s'inspirer (note L276 : lesquels ?).
