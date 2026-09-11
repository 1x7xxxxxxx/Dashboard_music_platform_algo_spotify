-- 105 — La couche OR gagne le grain TITRE pour Spotify S4A (R94).
--
-- Le comptage du 2026-09-12 : 32 agrégats sur `s4a_song_timeline` depuis des surfaces
-- d'affichage, et **21 d'entre eux sont au grain TITRE**. Aucune vue ne répondait à
-- cette maille, donc chaque surface écrivait la sienne — avec, à chaque fois, les deux
-- mêmes règles à ne pas oublier.
--
-- CES DEUX RÈGLES CESSENT D'ÊTRE UNE DISCIPLINE :
--
--   1. **La déduplication par (date, titre).** Deux imports du même jour ne doivent
--      pas doubler les écoutes ; c'est `MAX(streams)`, pas `SUM`. Un index unique
--      l'interdit aujourd'hui — mais un index peut sauter, et la règle survit ici.
--   2. **La ligne « Total » des CSV S4A est écartée.** C'est la règle transverse de
--      `CLAUDE.md` (« toute requête sur `s4a_song_timeline` porte
--      `AND song NOT ILIKE '%1x7xxxxxxx%'` »), tenue par un garde qui compte plus de
--      trente sites. Un garde qui compte des sites est un garde qui attend qu'on en
--      oublie un ; une vue qui les porte rend l'oubli impossible.
--
-- LES QUATRE FORMES que les surfaces demandent se dérivent toutes d'ici :
--
--     par titre, borné   SUM(streams) WHERE song = %s AND day BETWEEN %s AND %s
--     par titre, total   SUM(streams) WHERE song = %s
--     global, borné      SUM(streams) WHERE day BETWEEN %s AND %s
--     global, total      SUM(streams)            = v_platform_totals, branche spotify
--
-- S4A est une QUANTITÉ quotidienne, pas un compteur : toutes les journées sont dans
-- le CSV, donc la somme est exacte et aucun report en avant n'est nécessaire. C'est
-- ce qui la distingue de YouTube et SoundCloud, et la raison pour laquelle son grain
-- naturel est le jour et non le niveau.

CREATE OR REPLACE VIEW v_s4a_song_daily AS
    SELECT artist_id,
           song,
           date AS day,
           MAX(streams)::bigint AS streams
      FROM s4a_song_timeline
     WHERE artist_id IS NOT NULL
       AND song NOT ILIKE '%1x7xxxxxxx%'
       AND streams IS NOT NULL
     GROUP BY artist_id, song, date;

COMMENT ON VIEW v_s4a_song_daily IS
    'Couche OR (ADR-019) : les écoutes Spotify S4A au grain (locataire, titre, jour). '
    'Porte la déduplication par (date, titre) et le retrait de la ligne « Total » des '
    'CSV — les deux règles que chaque surface devait se rappeler. Toute question sur '
    'les écoutes S4A, par titre ou globale, bornée ou non, se dérive d''ici.';
