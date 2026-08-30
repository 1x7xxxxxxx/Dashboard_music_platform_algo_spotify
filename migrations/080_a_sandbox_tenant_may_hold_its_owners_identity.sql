-- ============================================================
-- 080 — `saas_artists.is_sandbox` : un locataire d'essai, opéré par nous
-- ============================================================
-- Le besoin, formulé pendant les tests du 2026-08-30 : refaire le parcours
-- d'onboarding DEPUIS ZÉRO pour vérifier que ses propres identifiants de
-- plateforme fonctionnent — avec un seul profil d'artiste à disposition.
--
-- Le garde d'unicité (migration 064 + `find_identity_conflict`) refuse, à raison :
-- un identifiant de plateforme n'appartient qu'à un locataire, sinon deux tableaux
-- de bord collectent la même source et personne ne sait à qui sont les chiffres.
-- Le désactiver « temporairement » rouvrirait exactement la fuite qui a coûté deux
-- sessions de test artiste — et un doublon, une fois créé, ne se voit plus.
--
-- Un locataire BAC À SABLE est le troisième cas, jusqu'ici absent :
--
--   locataire réel     — un client. Garde actif dans les deux sens.
--   canari (064)       — un robot permanent de surveillance, identités PUBLIQUES.
--                        Garde actif : il ne doit pas entrer en collision par accident.
--   bac à sable (ici)  — un locataire jetable que NOUS créons pour rejouer le
--                        parcours avec NOS PROPRES identifiants. Le garde le laisse
--                        passer, dans les deux sens.
--
-- Pourquoi un drapeau distinct de `is_canary` plutôt que le réutiliser : l'exemption
-- accordée ici est dangereuse, et l'accorder au canari de production l'élargirait
-- sans aucun besoin. Un drapeau, une permission.
--
-- Ce que le drapeau NE change pas : la collecte. `load_all_artists()` ne filtre
-- rien par défaut, donc un bac à sable collecte pour de vrai — c'est le point : sans
-- collecte, il ne prouverait rien sur les identifiants.
--
-- Ce qu'il change : les contrôles orientés onboarding, les compteurs publics et la
-- facturation, exactement comme pour le canari.
--
-- Idempotent : `make migrate` rejoue tous les fichiers.
ALTER TABLE saas_artists
    ADD COLUMN IF NOT EXISTS is_sandbox BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN saas_artists.is_sandbox IS
    'Locataire d''essai opéré par l''exploitant : peut réutiliser une identité de '
    'plateforme déjà tenue par un autre locataire, et n''est jamais compté dans les '
    'statistiques publiques ni dans les alertes d''onboarding. Collecte normalement.';

CREATE INDEX IF NOT EXISTS idx_saas_artists_is_sandbox
    ON saas_artists (is_sandbox) WHERE is_sandbox;
