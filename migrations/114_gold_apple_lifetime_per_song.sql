-- ═══════════════════════════════════════════════════════════════════════════
-- 114 — Le total Apple/Shazam d'UN titre, par la même règle que celui du catalogue
-- ═══════════════════════════════════════════════════════════════════════════
-- L'accueil gagne une tuile Shazam (R106, ADR-025 : Shazam est dans le cœur du
-- produit et n'était sur aucun écran). Elle porte deux chiffres — le total du
-- catalogue et celui de la DERNIÈRE SORTIE. Le premier existait déjà
-- (`gold_apple_lifetime(artist_id, 'shazam_count')`, migration 113) ; le second
-- demandait le même calcul restreint à un titre.
--
-- ── POURQUOI UNE SURCHARGE À TROIS ARGUMENTS SANS DÉFAUT ────────────────────
--
-- Deux fausses routes ont été écartées, chacune pour une raison mesurée le
-- 2026-09-13 :
--
--   1. « ajouter `p_song text DEFAULT NULL` à la fonction existante ».
--      CREATE OR REPLACE ne peut pas changer le nombre d'arguments : Postgres
--      créerait une SECONDE fonction, et `gold_apple_lifetime(1, 'plays')`
--      deviendrait AMBIGU — les deux candidates l'acceptent. Ce dépôt a déjà payé
--      exactement cette panne : l'`AmbiguousFunction` du 2026-09-12 a fait afficher
--      **zéro** à la tuile Apple, et le commentaire de `_lifetime()` en garde la
--      trace.
--
--   2. « dropper la 2-arguments et la recréer à trois ».
--      `v_platform_totals` DÉPEND de cette fonction (vérifié par `pg_depend` le
--      2026-09-13, une seule dépendance). Le DROP échoue, ou force à démonter puis
--      remonter une vue que **15 surfaces** lisent. Un risque sans rapport avec ce
--      qu'on ajoute.
--
-- La forme retenue : une surcharge `(integer, text, text)` **sans aucun défaut**.
-- Une 3-arguments sans défaut n'est jamais candidate pour un appel à 1 ou 2
-- arguments, donc aucune ambiguïté n'est possible — et la 2-arguments garde son OID,
-- donc `v_platform_totals` n'est pas touchée.
--
-- ── ET UNE SEULE DÉFINITION DE LA RÈGLE (ADR-019) ───────────────────────────
--
-- La 2-arguments n'est pas laissée en double : elle devient un APPEL de la
-- 3-arguments avec `NULL`. Le corps de la règle — la période la plus large, la
-- couverture non chevauchante, le repli sur le dernier dépôt sans bornes, et
-- `NULL` quand rien n'a été mesuré — n'existe plus qu'à un endroit.

-- ── 1. LA RÈGLE, avec son filtre de titre ───────────────────────────────────
CREATE OR REPLACE FUNCTION gold_apple_lifetime(p_artist_id integer,
                                               p_metric text,
                                               p_song text)
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

    -- LA QUESTION D'ABORD : a-t-on seulement un relevé pour CE périmètre ?
    -- Le filtre de titre entre ici aussi, et ce n'est pas un détail : sans lui, un
    -- titre absent de tous les exports Apple rendrait 0 — « aucun Shazam » — au lieu
    -- de NULL — « jamais mesuré ». C'est la distinction que la migration 113 a
    -- rétablie pour le catalogue ; elle vaut par titre pour la même raison.
    SELECT count(*) INTO n_rows
      FROM apple_songs_performance
     WHERE artist_id = p_artist_id
       AND (p_song IS NULL OR song_name = p_song);
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
        '   AND ($2::text IS NULL OR song_name = $2) '
        ' GROUP BY period_start, period_end '
        ' ORDER BY (period_end - period_start) DESC, period_start', p_metric)
        USING p_artist_id, p_song
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

    -- LE DERNIER DÉPÔT SANS BORNES — et son `MAX(snapshot_date)` est calculé SUR LE
    -- MÊME PÉRIMÈTRE que la somme. Prendre le dépôt le plus récent tous titres
    -- confondus rendrait 0 pour un titre absent de ce dépôt-là, alors qu'il a un
    -- relevé plus ancien : un zéro affirmé à la place d'un chiffre connu.
    EXECUTE format(
        'SELECT COALESCE(SUM(%I), 0)::bigint FROM apple_songs_performance '
        ' WHERE artist_id = $1 AND period_start IS NULL '
        '   AND ($2::text IS NULL OR song_name = $2) '
        '   AND snapshot_date = (SELECT MAX(snapshot_date) '
        '                          FROM apple_songs_performance '
        '                         WHERE artist_id = $1 AND period_start IS NULL '
        '                           AND ($2::text IS NULL OR song_name = $2))',
        p_metric)
        USING p_artist_id, p_song INTO fallback;
    RETURN COALESCE(fallback, 0);
END;
$function$;

-- ── 2. LA 2-ARGUMENTS DEVIENT UN APPEL, PAS UNE COPIE ───────────────────────
-- Même signature, même type de retour : `CREATE OR REPLACE` conserve l'OID, donc
-- `v_platform_totals` continue de pointer dessus sans être reconstruite.
CREATE OR REPLACE FUNCTION gold_apple_lifetime(p_artist_id integer,
                                               p_metric text DEFAULT 'plays')
RETURNS bigint
LANGUAGE sql
STABLE
AS $function$
    SELECT gold_apple_lifetime(p_artist_id, p_metric, NULL::text);
$function$;

COMMENT ON FUNCTION gold_apple_lifetime(integer, text, text) IS
    'Total Apple à vie (plays ou shazam_count), pour tout le catalogue (p_song NULL) '
    'ou pour un seul titre. NULL = jamais mesuré, jamais un zéro inventé.';
