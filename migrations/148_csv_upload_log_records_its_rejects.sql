-- 148 — Enregistrer ce que la lecture a MIS DE CÔTÉ (R502).
--
-- « Dead-letter queue: … events that cannot be ingested are set aside rather than
--   blocking the pipeline. »  — Reis & Housley, Fundamentals of Data Engineering, p.363
--
-- Avant R502, une cellule illisible (« 12x », « n.c. ») était lue 0 sans un mot : le
-- fichier s'importait, et le chiffre faux se relisait des semaines plus tard. Elle est
-- désormais comptée par colonne ; au-delà de 5 % d'une colonne (≥ 3 valeurs), ou à
-- 100 %, le fichier est refusé en nommant la colonne. Cette colonne garde le décompte
-- sur les TROIS issues — refusé, importé, erreur — comme 091 le fait pour la
-- sérialisation : c'est la trace qui rend un import partiel vérifiable après coup.

ALTER TABLE csv_upload_log ADD COLUMN IF NOT EXISTS rejected jsonb;

COMMENT ON COLUMN csv_upload_log.rejected IS
    'Valeurs illisibles mises de côté, par colonne : {col: {count, seen, samples}} ; '
    '« __row__ » = lignes entières écartées. NULL quand rien n''a été écarté (R502, '
    'Reis & Housley p.363).';
