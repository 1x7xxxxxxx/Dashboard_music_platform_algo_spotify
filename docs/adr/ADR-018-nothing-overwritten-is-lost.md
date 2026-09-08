# ADR-018 — Rien d'écrasé n'est perdu : un journal de révisions côté base

- **Date** : 2026-09-08
- **Statut** : Accepté
- **Demandé par** : « je souhaite une solution automatique qui conserve les données
  historiques si elles doivent être écrasées : solution long terme »

## Le problème

Nos upserts écrasent en place. `s4a_song_timeline` a pour clé `(artist_id, song, date)`
et `update_columns = ['streams']` : redéposer un export réécrit la valeur d'un jour
**sans laisser de trace**. Tant que la source ne se corrige jamais, c'est invisible.

Elle se corrige. La page *Artificial Streaming* de Spotify indique qu'ils **retirent
rétroactivement** des écoutes jugées artificielles. Un chiffre affiché hier peut donc
légitimement différer de celui d'aujourd'hui pour le même jour, et nous n'avons aucun
moyen de le dire — ni à l'artiste qui le remarque, ni à nous-mêmes en diagnostic.

Le même trou s'est déjà matérialisé dans l'autre sens le 2026-06-01 : une collecte
SoundCloud a écrit **19 compteurs cumulés à zéro** par-dessus des valeurs à quatre
chiffres. Les bonnes valeurs sont revenues le lendemain ; les fausses ont existé une
journée entière sans que rien ne conserve ce qu'elles avaient remplacé.

## La décision

Un **journal de révisions générique**, tenu par un déclencheur PostgreSQL
(`migrations/096_nothing_overwritten_is_lost.sql`) : toute mise à jour qui CHANGE une
valeur surveillée écrit une ligne dans `data_revisions` (table, locataire, clé de ligne
en JSONB, colonne, ancienne valeur, nouvelle valeur, horodatage). Inscrire une table
coûte un `CREATE TRIGGER` ; ne rien changer ne coûte rien.

## Pourquoi côté base, et pas dans le chemin d'écriture

`upsert_many` n'accepte que des noms de colonnes, pas des expressions : journaliser
depuis Python demanderait de modifier chaque appelant. Le coût réel n'est pas d'écrire
ce code — c'est que **tout écrivain futur qui l'oublie perdrait l'historique en
silence**, et qu'aucun test ne peut détecter une écriture qui n'a jamais été écrite. Un
déclencheur ne s'oublie pas : il est attaché à la table, pas au chemin.

Précédent existant dans ce dépôt : `trg_calculate_hypeddit_metrics` sur
`hypeddit_daily_stats`. On n'introduit donc pas un mécanisme nouveau.

## Pourquoi ce patron générique passe, alors qu'ADR-002 en a rejeté d'autres

ADR-002 a écarté Alembic, le patron *repository* et une couche d'observabilité. Le
critère y était : une abstraction qui **ajoute une couche à traverser** pour un dépôt
d'une seule personne. Celle-ci ne s'en traverse pas — elle n'a pas d'API, pas d'appelant
et pas de configuration. Son coût à l'usage est nul (une comparaison `IS DISTINCT FROM`
par ligne mise à jour), et elle rend possible une question qu'on ne sait pas poser
aujourd'hui : « ce chiffre a-t-il changé, et quand ? »

## Conséquences

### Positives
- Une valeur écrasée est récupérable, et le moment de l'écrasement est daté.
- On peut alerter sur une collecte qui révise anormalement beaucoup de lignes.
- L'e-mail de `check_zero_resets` peut renvoyer vers `data_revisions` pour dire ce que
  les zéros ont remplacé.

### Négatives / arbitrages
- Une table de plus qui grossit. **La rétention n'est pas décidée** : à ce jour la
  volumétrie réelle est nulle (aucune révision observée depuis l'installation), donc la
  décider maintenant serait un chiffre inventé. À revoir dès qu'elle dépasse ~1 M de
  lignes, avec une purge par âge — la même forme que `purge_expired()`.
- Un déclencheur est invisible depuis Python : quelqu'un qui lit `upsert_many` ne
  saura pas qu'il journalise. C'est le prix de l'impossibilité de l'oublier.

### Opérationnelles
- Tables inscrites : `s4a_song_timeline.streams`,
  `apple_songs_performance.plays,listeners,shazam_count`. Les autres s'inscrivent une
  par une, **après lecture de leur chemin d'écriture** — pas en masse.
- `data_revisions` est hors périmètre de `tools/tenant_contamination_check.py` : son
  `artist_id` est **copié** depuis la ligne révisée, jamais résolu depuis une identité
  de plateforme. La raison est écrite dans `_OUT_OF_SCOPE`.
- Garde : `tests/test_nothing_overwritten_is_lost.py` prouve l'EFFET (une réécriture
  identique ne journalise rien ; une réécriture différente journalise l'avant et
  l'après), pas la présence du déclencheur.

## Alternatives rejetées

| Option | Pourquoi rejetée |
|---|---|
| Une colonne `previous_streams` | Ne garde que l'avant-dernière valeur. Trois corrections successives et la première est perdue — or c'est justement la série qui répond à « depuis quand ? ». |
| Journaliser dans `upsert_many` | S'oublie. Un écrivain futur qui ne passe pas par là perd l'historique sans qu'aucun test ne puisse le voir. |
| Une table d'historique par table surveillée | Quatre schémas à maintenir au lieu d'un, et une inscription qui coûte une migration au lieu d'un `CREATE TRIGGER`. |
| Ne rien garder, et refuser l'écrasement | Refuser une révision légitime de Spotify nous ferait afficher un chiffre que la source a désavoué. |
