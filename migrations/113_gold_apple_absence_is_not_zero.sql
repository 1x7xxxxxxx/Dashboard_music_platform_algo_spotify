-- ═══════════════════════════════════════════════════════════════════════════
-- 113 — Apple : une absence de mesure n'est pas zéro écoute
-- ═══════════════════════════════════════════════════════════════════════════
-- ⚠️ DÉFAUT VIVANT, mesuré le 2026-09-12.
--
--     platform_totals(db, <locataire sans données>)
--       → {'spotify': None, 'youtube': None, 'soundcloud': None, 'apple': 0}
--
-- Trois plateformes disent « je n'ai pas mesuré », la quatrième affirme zéro. Un
-- artiste qui vient de s'inscrire lit « 0 écoute Apple Music », ce qui se lit comme
-- un échec du produit et non comme une absence de mesure — c'est la classe
-- `absence-rendered-as-a-measurement`, déjà au catalogue, sur une surface qu'elle
-- n'avait pas encore atteinte.
--
-- Les deux `COALESCE(..., 0)` de la fonction sont la cause. Ils étaient justes tant
-- que la porte Python en remettait un par-dessus ; maintenant qu'elle distingue les
-- trois cas (aucune ligne / mesuré à zéro / lecture échouée), ils effacent la
-- distinction juste en dessous.
--
-- CE QUI NE CHANGE PAS : `v_platform_totals` n'appelle cette fonction que pour les
-- locataires qui ONT des lignes Apple (`SELECT DISTINCT artist_id FROM
-- apple_songs_performance`). Sa branche apple est donc inchangée, et l'invariant
-- `apple_total_vs_function` continue de tenir — il compare les deux sur ces
-- locataires-là.
--
-- Un locataire qui a des lignes Apple mais aucune valeur exploitable rend toujours
-- un nombre : `GREATEST(widest_plays, cover_total)` vaut 0 dans ce cas, et c'est un
-- zéro MESURÉ. Seule l'absence totale de relevé rend NULL.
CREATE OR REPLACE FUNCTION gold_apple_lifetime(p_artist_id integer,
                                               p_metric text DEFAULT 'plays')
RETURNS bigint
LANGUAGE plpgsql
STABLE
AS $function$
DECLARE
    r            RECORD;
    widest_span  integer := -1;
    widest_plays bigint  := 0;
    cover_total  bigint  := 0;
    kept_s       date[]  := '{}';
    kept_e       date[]  := '{}';
    has_overlap  boolean;
    i            integer;
    fallback     bigint;
    n_rows       bigint;
BEGIN
    IF p_metric NOT IN ('plays', 'shazam_count') THEN
        RAISE EXCEPTION 'gold_apple_lifetime: métrique non autorisée: %', p_metric;
    END IF;

    -- LA QUESTION D'ABORD : ce locataire a-t-il seulement des relevés Apple ?
    -- Sans cette porte, toutes les branches ci-dessous finissent par rendre 0, et
    -- « jamais importé » devient « zéro écoute ».
    SELECT count(*) INTO n_rows
      FROM apple_songs_performance WHERE artist_id = p_artist_id;
    IF n_rows = 0 THEN
        RETURN NULL;
    END IF;

    FOR r IN EXECUTE format(
        'SELECT period_start AS s, period_end AS e, '
        '       COALESCE(SUM(%I), 0)::bigint AS p, '
        '       (period_end - period_start) AS span '
        '  FROM apple_songs_performance '
        ' WHERE artist_id = $1 AND period_start IS NOT NULL '
        '   AND period_end IS NOT NULL '
        ' GROUP BY period_start, period_end '
        ' ORDER BY (period_end - period_start) DESC, period_start', p_metric)
        USING p_artist_id
    LOOP
        IF r.span > widest_span THEN
            widest_span  := r.span;
            widest_plays := r.p;
        END IF;

        has_overlap := FALSE;
        IF array_length(kept_s, 1) IS NOT NULL THEN
            FOR i IN 1 .. array_length(kept_s, 1) LOOP
                IF r.s <= kept_e[i] AND r.e >= kept_s[i] THEN
                    has_overlap := TRUE;
                    EXIT;
                END IF;
            END LOOP;
        END IF;

        IF NOT has_overlap THEN
            kept_s := kept_s || r.s;
            kept_e := kept_e || r.e;
            cover_total := cover_total + r.p;
        END IF;
    END LOOP;

    IF widest_span >= 0 THEN
        RETURN GREATEST(widest_plays, cover_total);
    END IF;

    EXECUTE format(
        'SELECT COALESCE(SUM(%I), 0)::bigint FROM apple_songs_performance '
        ' WHERE artist_id = $1 AND period_start IS NULL '
        '   AND snapshot_date = (SELECT MAX(snapshot_date) '
        '                          FROM apple_songs_performance '
        '                         WHERE artist_id = $1 AND period_start IS NULL)',
        p_metric)
        USING p_artist_id INTO fallback;
    RETURN COALESCE(fallback, 0);
END;
$function$;
