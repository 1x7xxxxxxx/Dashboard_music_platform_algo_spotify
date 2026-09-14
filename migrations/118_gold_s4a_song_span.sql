-- ═══════════════════════════════════════════════════════════════════════════
-- 118 — Jusqu'où la mesure va, TITRE PAR TITRE — et quand le titre a existé
-- ═══════════════════════════════════════════════════════════════════════════
-- Deux faits mesurés le 2026-09-14 qui exigent la même vue.
--
-- 1. L'IMPORT S4A EST ÉPISODIQUE, au moment d'une sortie (décision du propriétaire).
--    Une date de fraîcheur GLOBALE affirme donc un arrêt général qui n'a pas eu
--    lieu : la mesure est dense autour de chaque sortie. C'est une borne PAR TITRE
--    qu'il faut, et la page en affichait une seule pour onze.
--
-- 2. CHAQUE SÉRIE COMMENCE AU 2023-01-01, QUELLE QUE SOIT LA DATE DE SORTIE.
--    « Ô Chiotte l'arbitre Tucome Back », sorti le 2024-08-30, porte **20 mois de
--    `streams = 0`** avant d'exister. Il y a 6 365 lignes de cette forme.
--
--    Ces zéros ne sont PAS fabriqués par notre parseur — vérifié dans
--    `src/transformers/s4a_csv_parser.py` : il écrit exactement ce que le CSV porte.
--    Spotify exporte la timeline du COMPTE, et y met 0 pour un titre qui n'était
--    pas publié. Le zéro est donc réel dans le fichier et FAUX à l'écran : « le
--    titre n'existait pas » n'est pas « personne ne l'a écouté ». En « Tout
--    l'historique », la courbe de détail dessinait 20 mois de plat à zéro pour un
--    morceau non publié — la classe `an-unmeasured-platform-is-rendered-as-zero`,
--    au grain titre.
--
--    `first_streamed` est la réponse : le premier jour où la mesure porte quelque
--    chose. Une série commence là, jamais au premier jour du fichier.
--
-- Hérite de `v_s4a_song_daily` (migration 105) : déduplication (date, titre) et
-- retrait de la ligne « Total » compris — deux règles qu'aucun appelant n'a plus à
-- se rappeler. Idempotent.

CREATE OR REPLACE VIEW v_s4a_song_measured_span AS
    SELECT artist_id,
           song,
           MIN(day)                                          AS first_measured,
           MAX(day)                                          AS last_measured,
           COUNT(DISTINCT day)::int                          AS days_measured,
           (MAX(day) - MIN(day) + 1)::int                    AS span_days,
           -- Le premier jour où le titre EXISTE, au sens de la mesure. NULL quand
           -- il n'a jamais rien fait — et NULL, pas 0 : « aucune écoute jamais »
           -- est un fait, « zéro ce jour-là » en est un autre.
           MIN(day) FILTER (WHERE streams > 0)               AS first_streamed,
           MAX(day) FILTER (WHERE streams > 0)               AS last_streamed,
           COUNT(*) FILTER (WHERE streams > 0)::int          AS days_with_streams,
           SUM(streams)::bigint                              AS streams_total
      FROM v_s4a_song_daily
     GROUP BY artist_id, song;

COMMENT ON VIEW v_s4a_song_measured_span IS
    'Couche OR (ADR-019) : jusqu''où la mesure va, TITRE PAR TITRE, et depuis quand '
    'le titre existe. L''import S4A est ÉPISODIQUE — dense autour d''une sortie — '
    'donc une fraîcheur globale affirme un arrêt général qui n''a pas eu lieu. '
    'last_measured est la BORNE D''ASSERTION : rien ne se dessine après elle. '
    'first_streamed est le début légitime d''une série : Spotify exporte la timeline '
    'du COMPTE et y met 0 avant la sortie (6 365 lignes), or « le titre n''existait '
    'pas » n''est pas « personne ne l''a écouté ». days_measured < span_days signale '
    'un trou intérieur.';
