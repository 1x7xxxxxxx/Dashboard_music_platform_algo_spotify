-- 091 — Enregistrer la configuration de SÉRIALISATION réellement retenue.
--
-- « CSV file encoding and schema information must be configured in the target system
--   to ensure appropriate ingestion. Autodetection is a convenience feature provided
--   in many cloud environments but is inappropriate for production ingestion. As a
--   best practice, engineers should record CSV encoding and schema details in file
--   metadata. »   — Reis & Housley, Fundamentals of Data Engineering, p. 374
--
-- On ne peut pas cesser de deviner : les fichiers viennent de Spotify, d'Apple et
-- parfois d'un Excel français, et rien ne nous laisse configurer la source. Mais on
-- peut enregistrer CE QU'ON A DEVINÉ — c'est la moitié qui manquait. Le 2026-09-06,
-- douze exports ont été refusés à cause d'un BOM et rien, nulle part, ne disait quel
-- encodage avait gagné : l'écran affichait « Colonnes vues : ﻿date, streams », où le
-- BOM ne se rend pas. La migration 090 a ajouté les colonnes vues (le « schema
-- details » de la citation) ; celle-ci ajoute l'encodage et le séparateur.
--
-- Écrite sur les DEUX issues, refus et succès : un fichier importé sous le mauvais
-- séparateur ne lève pas — il produit des chiffres faux qu'on relira des semaines
-- plus tard, et c'est alors la seule trace qui permette de comprendre.

ALTER TABLE csv_upload_log ADD COLUMN IF NOT EXISTS serialization text;

COMMENT ON COLUMN csv_upload_log.serialization IS
    'Encodage et séparateur RETENUS par la détection, ex. « utf-8-sig | , ». '
    'Devinés, jamais configurés : cette colonne est ce qui rend la devinette '
    'vérifiable après coup (Reis & Housley, Fundamentals of Data Engineering p.374).';
