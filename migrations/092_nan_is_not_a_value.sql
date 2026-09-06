-- 092 — « nan » n'est pas une valeur.
--
-- `str(row[col] or '')` était le motif employé dans le parseur iMusician. Il paraît
-- sûr et ne l'est pas : un NaN pandas est VRAI en contexte booléen, donc `nan or ''`
-- rend `nan`, et `str(nan)` rend la chaîne littérale 'nan'.
--
-- Mesuré en production le 2026-09-06 : 2 533 lignes de `track_version`, deux `isrc`
-- et deux `track_title` valant littéralement 'nan'.
--
-- Le coût n'est pas cosmétique. L'ISRC est la clé exacte du secteur — chaque version
-- d'un morceau en porte une propre — et une absence écrite 'nan' regroupe sous UNE
-- MÊME valeur tout ce qui n'a pas d'identifiant. C'est le pire regroupement possible
-- pour une colonne dont le rôle est de distinguer, et c'est exactement ce sur quoi
-- `track_release_reference` va désormais s'appuyer.
--
-- Idempotent : réexécuter ne trouve plus rien à corriger.

UPDATE imusician_sales_detail SET isrc          = NULL WHERE isrc          = 'nan';
UPDATE imusician_sales_detail SET track_title   = NULL WHERE track_title   = 'nan';
UPDATE imusician_sales_detail SET track_version = NULL WHERE track_version = 'nan';
UPDATE imusician_sales_detail SET release_title = NULL WHERE release_title = 'nan';
UPDATE imusician_sales_detail SET label         = NULL WHERE label         = 'nan';
UPDATE imusician_sales_detail SET barcode       = NULL WHERE barcode       = 'nan';
UPDATE imusician_sales_detail SET country       = NULL WHERE country       = 'nan';
UPDATE imusician_sales_detail SET shop          = NULL WHERE shop          = 'nan';
UPDATE imusician_sales_detail SET transaction_type = NULL WHERE transaction_type = 'nan';

UPDATE imusician_release_summary SET release_title = NULL WHERE release_title = 'nan';
