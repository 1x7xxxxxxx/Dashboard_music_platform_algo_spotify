"""Privacy policy page — GDPR / RGPD.

Type: Feature
Accessible without login via /?page=privacy.
"""
import streamlit as st

from src.dashboard.utils.i18n import t


def show():
    st.title(t("privacy.title", "Politique de confidentialité"))
    st.caption(t("privacy.last_updated", "Dernière mise à jour : mars 2026"))

    st.markdown(t("privacy.s1", """
## 1. Responsable du traitement

La plateforme **Music Cross Platform Dashboard** est opérée par son administrateur.
Pour toute demande relative à vos données personnelles, contactez :
**1x7xxxxxxx@gmail.com**
"""))

    st.markdown("---")

    st.markdown(t("privacy.s2", """
## 2. Données collectées

| Donnée | Finalité | Base légale |
|---|---|---|
| Nom d'artiste, slug | Identification du compte | Exécution du contrat |
| Nom d'utilisateur | Connexion à la plateforme | Exécution du contrat |
| Adresse email | Vérification du compte, communication | Exécution du contrat + Consentement (marketing) |
| Mot de passe (haché bcrypt) | Authentification | Exécution du contrat |
| Credentials API (chiffrés) | Collecte de données musicales | Exécution du contrat |
| Données de streaming (Spotify, YouTube…) | Analyse de performance musicale | Exécution du contrat |
"""))

    st.markdown("---")

    st.markdown(t("privacy.s3", """
## 3. Utilisation de l'adresse email

Votre email est utilisé pour :
- La **vérification de votre compte** (email transactionnel, obligatoire)
- Les **communications marketing** (newsletters, mises à jour) — **uniquement si vous y avez consenti**
  lors de votre inscription. Vous pouvez retirer ce consentement à tout moment.
"""))

    st.markdown("---")

    st.markdown(t("privacy.s4", """
## 4. Durée de conservation

- **Données de compte** : conservées tant que le compte est actif. Supprimées sur demande.
- **Données de streaming** : conservées 3 ans à des fins d'analyse historique.
- **Logs techniques** : 30 jours.
"""))

    st.markdown("---")

    st.markdown(t("privacy.s5", """
## 5. Sécurité

- Les mots de passe sont **hachés de manière irréversible** (bcrypt) — personne ne peut les lire.
- Les tokens API sont **chiffrés** (AES-128 Fernet) avant stockage en base.
- La base de données est hébergée localement ou sur un serveur sécurisé.
"""))

    st.markdown("---")

    st.markdown(t("privacy.s6", """
## 6. Vos droits (RGPD Art. 15-22)

Vous disposez des droits suivants, exercés par email à **1x7xxxxxxx@gmail.com** :

- **Droit d'accès** (Art. 15) — obtenir une copie de vos données
- **Droit de rectification** (Art. 16) — corriger des données inexactes
- **Droit à l'effacement** (Art. 17) — supprimer votre compte et vos données
- **Droit d'opposition** (Art. 21) — vous opposer aux communications marketing
- **Droit à la portabilité** (Art. 20) — recevoir vos données dans un format lisible

Délai de réponse : 30 jours maximum.
"""))

    st.markdown("---")

    st.markdown(t("privacy.s7", """
## 7. Cookies

Cette plateforme utilise **un seul cookie de session** (`music_dashboard`) pour maintenir
votre connexion. Ce cookie est strictement nécessaire au fonctionnement du service —
il ne tracke pas votre navigation et n'est pas partagé avec des tiers.
"""))

    st.markdown("---")

    st.markdown(t("privacy.s8", """
## 8. Transferts de données

Vos données ne sont **pas vendues ni transmises** à des tiers.
Les APIs tierces (Spotify, YouTube, Meta, SoundCloud) sont contactées uniquement avec
vos propres credentials, conformément à leurs conditions d'utilisation respectives.
"""))

    st.markdown("---")

    st.markdown(t("privacy.s9", """
## 9. Contact & réclamation

**Contact RGPD** : 1x7xxxxxxx@gmail.com

Vous pouvez également introduire une réclamation auprès de la **CNIL** :
[www.cnil.fr](https://www.cnil.fr) — 3 place de Fontenoy, 75007 Paris.
"""))

    st.markdown("---")
    st.markdown(t("privacy.back", "[← Retour à l'accueil](/)"))
