-- ============================================================
-- 075 — tenant_platform_probe : ce que la plateforme a répondu, et quand
-- ============================================================
-- 2026-08-22. La passe nocturne interroge déjà l'API de chaque plateforme pour les
-- couples (locataire, plateforme) que la base juge rouges — c'est ce qui a fait
-- passer le message de GRiNCH de « vérifie ton User ID » à « aucun titre public ».
-- Elle jetait ce diagnostic après l'avoir mis dans l'e-mail.
--
-- Le conserver a deux effets, et le second est le vrai :
--   1. l'artiste lit EXACTEMENT ce que dit l'alerte, sans un appel API de plus ;
--   2. la matrice de setup s'affiche instantanément. Streamlit relance la page à
--      chaque clic ; sonder au rendu, ce serait cinq appels par clic et par
--      locataire. La sonde reste donc à la demande, et cette table porte la mémoire.
--
-- Une ligne par (locataire, plateforme), écrasée à chaque nouvelle mesure : on veut
-- le dernier verdict, pas un historique. `probed_at` dit son âge, ce qui permet à
-- l'affichage de distinguer « mesuré il y a 6 h » de « mesuré il y a trois semaines ».
--
-- `platform` porte le nom LOGIQUE, donc `instagram` y figure — contrairement aux
-- onglets du formulaire, où l'identité Instagram est un champ de la ligne `meta`.

CREATE TABLE IF NOT EXISTS tenant_platform_probe (
    artist_id  INTEGER     NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    platform   TEXT        NOT NULL,
    probed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ok         BOOLEAN     NOT NULL,
    reason     TEXT,
    PRIMARY KEY (artist_id, platform)
);

COMMENT ON TABLE tenant_platform_probe IS
    'Dernier verdict de l''API de chaque plateforme pour un locataire. Écrit par '
    'alert_monitor (nuit, sur les plateformes rouges) et par le bouton « Vérifier '
    'maintenant ». Absence de ligne = jamais mesuré, ce qui n''est PAS un verdict.';
COMMENT ON COLUMN tenant_platform_probe.platform IS
    'Nom LOGIQUE (instagram inclus), pas la ligne de stockage.';
