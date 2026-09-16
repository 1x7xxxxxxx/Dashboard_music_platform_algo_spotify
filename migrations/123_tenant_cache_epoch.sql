-- 123 — saas_artists.cache_epoch : l'invalidation de cache traverse les instances
--
-- POURQUOI. Onze `@st.cache_data(ttl=600)` du dashboard sont purgés par
-- `kpi_helpers.clear_kpi_caches()`, et cette purge ne touche QUE le processus qui
-- l'appelle. Tant qu'il y a une instance, c'est exact. À deux instances, un artiste
-- déclenche une collecte sur A, voit ses nouveaux chiffres, recharge, tombe sur B, et
-- revoit les anciens PENDANT DIX MINUTES. C'est un ticket de support avant d'être un
-- incident, et c'est le préalable de la seconde réplique (R114).
--
-- FORME. Un compteur par LOCATAIRE, pas un drapeau global : une collecte déclenchée
-- par l'artiste 12 n'a aucune raison de faire manquer leur cache aux autres. Un
-- entier monotone plutôt qu'un horodatage — deux instances dont les horloges
-- divergent de quelques secondes compareraient des dates et concluraient l'inverse
-- l'une de l'autre ; un compteur qu'une seule instruction SQL incrémente n'a pas ce
-- problème.
--
-- PAS DE TABLE NEUVE. Le locataire existe déjà, et une table `tenant_cache_epoch`
-- ajouterait une jointure à une lecture qui doit rester d'une seule requête.
--
-- COÛT. Une écriture par collecte déclenchée (quelques-unes par jour et par artiste),
-- et une lecture par processus toutes les `_EPOCH_TTL` secondes — pas par rendu.

ALTER TABLE saas_artists
    ADD COLUMN IF NOT EXISTS cache_epoch BIGINT NOT NULL DEFAULT 0;

COMMENT ON COLUMN saas_artists.cache_epoch IS
    'Compteur d''invalidation de cache par locataire. Incrémenté par '
    'src/dashboard/utils/cache_epoch.py:bump() quand une écriture rend les compteurs '
    'faux ; chaque instance le relit et purge SES caches quand il a bougé. '
    'Monotone — ne jamais le remettre à zéro, une instance croirait n''avoir rien raté.';
