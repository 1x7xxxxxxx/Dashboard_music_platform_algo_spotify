# ADR-016 — Deux chemins de sonde, deux économies, deux règles

- **Date** : 2026-09-05
- **Statut** : Accepté
- **Ferme** : R59, inscrite le matin même comme « deux tests encodent des règles
  opposées ». **Sa prémisse était fausse** ; cet ADR existe pour que la prochaine
  lecture ne recrée pas ce faux conflit.

## Le faux conflit

Deux tests semblaient se contredire sur la même sonde :

| Test | Ce qu'il exige |
|---|---|
| `tests/test_readiness_carries_the_live_diagnosis.py::test_only_the_reds_are_probed` | on ne sonde **jamais** une plateforme verte |
| `tests/test_saving_credentials_yields_a_verdict_now.py::test_the_credentials_save_path_probes_immediately` | tout chemin de sauvegarde sonde, **inconditionnellement** |

Lus l'un contre l'autre, ils paraissent inconciliables. Lus avec leur **portée**, ils ne
se croisent pas.

## La décision

**Il y a deux chemins de sonde, et ils n'ont pas la même économie.**

**Le chemin nocturne** — `artist_readiness` + `check_onboarding_readiness`
(`airflow/dags/alert_monitor.py`). Personne n'attend. Le coût est multiplicatif :
*« à 100 locataires, cinq plateformes, c'est 500 appels API par nuit pour apprendre ce
que la base répond déjà »* (le commentaire du test, et c'est le bon argument). D'où le
budget `READINESS_PROBE_BUDGET = 25` et la règle **on ne sonde que le rouge**. La
fraîcheur est la preuve ; la sonde n'est là que pour **expliquer** un rouge.

**Le chemin interactif** — `_handle_save` (`views/credentials/_render.py`). Un artiste
vient de coller une valeur et regarde l'écran. Le coût est **un** appel, pour **un**
locataire, déclenché par un humain. Ne pas sonder, c'est lui dire « collecte lancée » et
le laisser apprendre à 23 h — ou jamais. C'est le défaut corrigé le 2026-08-30.

Les deux règles sont donc **compatibles** : « ne dépense pas d'appel pour une question
que la base a déjà tranchée » et « réponds tout de suite à qui attend ».

## Ce qu'on rejette

- **Unifier les deux chemins** sur une seule règle. Choisir « toujours sonder » ramène
  les 500 appels nocturnes ; choisir « jamais sur du vert » rend l'enregistrement muet.
- **Sonder au réveil de la page.** Le coût suit alors le trafic, pas les décisions, et
  une page rafraîchie trois fois sonde trois fois.

## La règle d'expédition

Toute nouvelle sonde déclare **à quel chemin elle appartient** :

- déclenchée par un humain qui attend une réponse ⇒ interactive, inconditionnelle,
  une plateforme à la fois ;
- déclenchée par un horaire ⇒ nocturne, sous budget, **et seulement sur du rouge**.

Une sonde qui n'appartient à aucun des deux n'a pas de raison de tourner.

## Conséquence mesurée le jour même

`_claimed_count` (`views/credentials/_platform_soundcloud.py`) emprunte une connexion
Streamlit. Sur le chemin **nocturne**, il n'y en a pas : la fonction rend donc `None`
par construction, et c'est le cas **courant** là-bas, pas l'exception. Un `None` n'y
autorise aucune conclusion — voir R60. Le chemin conditionne le sens de la valeur : ce
n'est pas un détail d'implémentation, c'est pourquoi cet ADR existe.
