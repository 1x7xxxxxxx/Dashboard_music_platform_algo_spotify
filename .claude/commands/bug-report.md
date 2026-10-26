---
rex: []
---

Take a **bug report** — a sentence someone wrote, an issue, a log pasted in — and turn it into a
**reproduced** defect with a roadmap row, BEFORE anyone touches the code. This is the intake; the
resolution that follows is the `bug-resolution` playbook (or the engineering loop for a batch).

A report is a claim, not a fact. It becomes one when a command goes red on it — and that same
command, green, is the proof of the fix. Nothing in this command is skipped for a « small » bug.

## Input

`$ARGUMENTS`: the report, verbatim. If it is empty, ask for it — never invent one.

## 1. Restate the report as an expected/observed pair

One line each, in the reporter's terms: **attendu** … / **observé** … Name what is missing (the
version, the input, the account, the command) and ask for it if the repro needs it. Do not guess a
missing input: a repro on a guessed input reproduces your guess.

## 2. Write the reproduction — a command that is RED while the bug lives

Prefer, in order: an existing test that already fails › a new failing test (the future guard) › a
one-line shell command whose exit status carries the verdict (`! grep …`, `python3 -c "assert …"`).
A command that only PRINTS the symptom is not a repro: its exit is 0 whatever it shows.

## 3. Run the intake — it executes the repro and refuses a green one

```bash
python3 .claude/scripts/bug_intake.py --write "<titre court du défaut>" -- <commande de reproduction>
```

- exit 0 → **reproduced**: the row is in the 📋 table, `<!-- défaut -->`, its « Mesuré par » the repro.
  Commit the roadmap row alone, as the repo's roadmap rules say.
- exit 2 → **not reproduced**: the command exited 0. Nothing is written. Say so to the reporter with
  the output, and go back to step 1 — never record a report as a defect on a green command.
- exit 3 → the repo has no 📋 table: the row is printed; write it where the repo keeps its roadmap.

## 4. Hand over to resolution

Apply the `bug-resolution` playbook if the repo ships one in its workflows (root cause read from the code,
sibling sweep, guard, mutation). Two reports or more in the same session → one engineering-loop
run instead (`Workflow({name: "engineering-loop", args: [...]})`). The row closes only when its
repro, replayed verbatim, exits 0.

## Out of scope — what this command does not do

- It does not fix anything: it stops at a reproduced, recorded defect.
- It does not decide that the reporter is wrong. « Not reproduced » is a request for a better repro,
  not a verdict on the report.
