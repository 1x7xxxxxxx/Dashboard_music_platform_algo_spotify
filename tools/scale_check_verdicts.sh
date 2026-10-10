# shellcheck shell=bash
# The two R87 trigger decisions of tools/scale_check.sh, sourced — never executed.
#
# Type: Utility
# Uses: nothing (pure bash, no ssh)
# Triggers: sourced by tools/scale_check.sh; by tests/test_a_crash_is_never_credited_as_a_judgement.py
# Persists in: nothing
#
# R495 — class `a-crash-credited-as-a-judgement`. Each trigger has THREE outcomes, and
# the third is the one the script used to lose:
#   0  ✅ under the threshold
#   1  🔴 threshold crossed
#   2  ⊘  the measure is unreadable — a dead ssh, a psql error, a load test that never
#         printed its p50. Before R495 an empty p50 fell into the `else` branch and
#         printed « ✅ p50 = ? ms, sous le seuil », and a non-numeric peak made `[ -gt ]`
#         fail inside an `if`, which bash reads as false: ✅ again. A measure nobody took
#         read as « nothing to reopen ».
# Extracted so the decision can be tested under `set -euo pipefail` without ssh.

_is_count() { [[ "${1:-}" =~ ^[0-9]+$ ]]; }

# sessions_verdict PEAK THRESHOLD
sessions_verdict() {
  local peak="${1:-}" seuil="$2"
  if ! _is_count "$peak"; then
    echo "  ⊘ pic illisible (« ${peak} ») — la requête n'a rien rendu : ce déclencheur n'a RIEN vérifié"
    return 2
  fi
  if [ "$peak" -gt "$seuil" ]; then
    echo "  🔴 SEUIL FRANCHI — R87 se rouvre. Voir l'inventaire de ce qui casse à N>1 :"
    echo "     tests/test_in_memory_limits_forbid_replicas.py"
    return 1
  fi
  echo "  ✅ sous le seuil — répliques toujours injustifiées"
  return 0
}

# p50_verdict P50 THRESHOLD
p50_verdict() {
  local p50="${1:-}" seuil="$2"
  if ! _is_count "$p50"; then
    echo "  ⊘ p50 illisible — la mesure n'a imprimé aucun p50 : ce déclencheur n'a RIEN vérifié"
    return 2
  fi
  if [ "$p50" -gt "$seuil" ]; then
    echo "  🔴 SEUIL FRANCHI — R87 se rouvre."
    return 1
  fi
  echo "  ✅ p50 = ${p50} ms, sous le seuil de ${seuil} ms"
  return 0
}
