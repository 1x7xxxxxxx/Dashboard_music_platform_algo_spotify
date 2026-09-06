-- Un fichier REFUSÉ à la détection n'était enregistré nulle part.
--
-- `csv_upload_log` ne recevait que ce qui atteignait l'import : succès et erreurs
-- d'écriture. Un fichier écarté plus tôt — « type non reconnu » — ne laissait aucune
-- trace, donc aucune alerte ne pouvait le voir. Mesuré le 2026-09-06 : douze fichiers
-- Spotify for Artists refusés à cause d'un BOM, depuis juin, sans que rien ne le dise.
-- L'artiste, lui, l'avait vu quinze fois à l'écran.
--
-- Le statut s'ajoute au CHECK plutôt que de réutiliser 'error' : les deux appellent des
-- gestes différents. 'error' est une écriture qui échoue — notre faute, à corriger dans
-- le code. 'rejected' est un fichier que nous n'avons pas su lire — cause probable chez
-- nous aussi, mais visible seulement en agrégeant : un refus isolé est peut-être un
-- mauvais export, dix refus du même motif sont un défaut de détection.
ALTER TABLE csv_upload_log DROP CONSTRAINT IF EXISTS csv_upload_log_status_check;
ALTER TABLE csv_upload_log
  ADD CONSTRAINT csv_upload_log_status_check
  CHECK (status = ANY (ARRAY['success'::text, 'error'::text, 'rejected'::text]));

-- Les colonnes vues au moment du refus. Sans elles, « type non reconnu » ne se
-- diagnostique pas a posteriori — et c'est exactement ce qui manquait en juin : le
-- message à l'écran portait la réponse (un BOM invisible devant `date`), personne
-- n'était là pour le lire, et rien ne l'a gardé.
ALTER TABLE csv_upload_log ADD COLUMN IF NOT EXISTS seen_columns text;

CREATE INDEX IF NOT EXISTS idx_csv_upload_log_status_date
  ON csv_upload_log (status, imported_at DESC);
