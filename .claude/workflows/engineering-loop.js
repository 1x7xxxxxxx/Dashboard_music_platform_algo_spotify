export const meta = {
  name: 'engineering-loop',
  description: 'One run: impact-sweep each finding, code-critic every fix design BEFORE writing, patch only what is approved (isolated worktrees), then a completeness critic. Returns a deploy manifest — it never writes the ROADMAP and never commits.',
  whenToUse: 'A batch of findings from one session: bugs, regressions, drift, silent failures, or config/meta defects. Replaces the four separate launches (impact-analysis / code-critic / bug-resolution / continuous-improvement) with one pass. Pass the findings as args.',
  phases: [
    { title: 'Impact',  detail: 'root cause read from code + whole-repo sibling sweep, one agent per finding' },
    { title: 'Critic',  detail: 'code-critic on each FIX DESIGN before a line is written — BUILD / BUILD-MODIFIED / DO-NOT-BUILD' },
    { title: 'Fix',     detail: 'approved designs only: patch + durable guard + targeted mutation, in an isolated worktree' },
    { title: 'Improve', detail: 'completeness critic — which class stays open, which detector would cover the lot' },
  ],
}

// ─────────────────────────────────────────────────────────────────────────────
// WHY THIS FILE EXISTS AS A FILE.
//
// Measured 2026-07-27 over 49 sessions IN ONE PROJECT (trading_bot). The numbers below are
// that project's; the mechanism they demonstrate is not project-specific: the `Workflow` tool has **6 calls all-time** against 190
// `Agent` calls, and all 6 passed an INLINE script — one of them literally named
// `engineering-loop-run` (13 KB, 2026-07-22), persisted only to an ephemeral session dir and then
// lost. The tool was not unused because it was unhelpful; it was unused because every use cost
// re-authoring 9-15 KB from scratch. So the loop becomes a file that `scriptPath` can re-run.
//
// AND WHY IT CALLS code-critic INSTEAD OF MENTIONING IT. Same measurement, the sharper half:
//
//     named in a BINDING RULE of CLAUDE.md ....... 2 agents -> 33 spawns
//     named only in a STEP of engineering-loop.md  5 agents ->  0 spawns
//     named nowhere .............................. 22 agents -> 10 spawns
//
// `security-specialist`, `performance-auditor`, `rollback-guardian`, `migration-planner` and
// `code-architecture-reviewer` sit in the numbered steps of a playbook that has been injected 98
// times, and have been spawned exactly ZERO times. Being written in a playbook step is worth
// nothing. `code-critic`'s 26 spawns across 9 sessions and 11 consecutive days come from binding
// rule 5, the one agent trigger that is mandatory rather than suggested. A `phase('Critic')` in
// executable JS is the strongest available form of that rule: not a reminder, a call site.
//
// THE THREE THINGS THIS SCRIPT DELIBERATELY DOES NOT DO — each is governance, not taste:
//   · it runs NO test batch. Phase 3 does its own targeted mutation check (~1 min) and nothing more.
//     The full suite is deferred to the deploy step, per engineering-loop.md §Deploy.
//   · it never touches the ROADMAP. Binding rule 4: a subagent may not write to the ROADMAP; a
//     finding enters only with the command that measured it and that command's output. So this
//     returns a MANIFEST and the main context does the recording.
//   · it never commits. Approved patches land in the working tree, unstaged, for a human-reviewed
//     deploy in the order the playbook fixes: ROADMAP -> batch -> commit -> push.
// ─────────────────────────────────────────────────────────────────────────────

const IMPACT = {
  type: 'object',
  required: ['title', 'root_cause', 'siblings', 'fix_scope', 'guard_plan', 'confidence'],
  properties: {
    title:       { type: 'string', description: 'one line naming the DEFECT, not the symptom' },
    root_cause:  { type: 'string', description: 'the cause read from the code, with file:line. If you could not read it, say so — do not infer.' },
    is_real:     { type: 'boolean', description: 'false if the sweep refuted the finding' },
    refutation:  { type: 'string', description: 'if is_real=false, the evidence that refutes it' },
    error_class: { type: 'string', description: 'existing kebab id from error-classes.md if this is an INSTANCE of a known class, else "" for a new class' },
    siblings:    { type: 'array', items: { type: 'object', required: ['path', 'same_bug', 'why'],
                   properties: { path: { type: 'string' }, same_bug: { type: 'boolean' }, why: { type: 'string' } } },
                   description: 'every hit of the sweep, each CLEARED with a written reason or marked same_bug' },
    fix_scope:   { type: 'string', description: 'the files the fix must touch, and why each' },
    guard_plan:  { type: 'string', description: 'the durable guard: a signature for error-classes.md and/or a test, plus the MUTATION that must make it go red' },
    decides_irreversible: { type: 'boolean', description: 'true if it touches a strategy signal, gate threshold, walk-forward split, cost model, or selection rule (binding rule 5)' },
    confidence:  { type: 'string', enum: ['measured', 'read', 'inferred'] },
  },
}

const VERDICT = {
  type: 'object',
  required: ['verdict', 'reason'],
  properties: {
    verdict: { type: 'string', enum: ['BUILD', 'BUILD-MODIFIED', 'DO-NOT-BUILD'] },
    reason:  { type: 'string', description: 'the motive, in the critic\'s own words. For DO-NOT-BUILD this becomes a ROADMAP brick, so it must stand alone.' },
    required_modifications: { type: 'array', items: { type: 'string' }, description: 'BUILD-MODIFIED only: what must change before it is written' },
    hidden_coupling_risk:      { type: 'string', description: 'or "n/a" when the change decides nothing irreversible' },
    unobservable_failure_risk:   { type: 'string' },
    verified_on_the_same_data_that_produced_it:  { type: 'string' },
  },
}

// ⚠️ `isolation: 'worktree'` means phase 3 edits a SEPARATE checkout. That is what makes parallel
// fixes safe, and it is also why the patch has to travel back as DATA: the script cannot reach into
// a worktree, and the main context never sees those files. So the agent returns a unified diff and
// the deploy step applies it (`git apply`). Without this field the phase would run, report success,
// and leave every change stranded in a directory that gets cleaned up — a whole phase that measures
// as "done" and delivers nothing, which is the exact class this repo keeps paying for.
const PATCH = {
  type: 'object',
  required: ['applied', 'files_touched', 'guard', 'mutation_result', 'diff'],
  properties: {
    applied:         { type: 'boolean' },
    files_touched:   { type: 'array', items: { type: 'string' } },
    diff:            { type: 'string', description: 'the COMPLETE `git diff` of the fix + guard, applicable with `git apply` from the repo root. This is the only way the work leaves the isolated worktree.' },
    guard:           { type: 'string', description: 'the signature command or test path that now blocks the CLASS' },
    mutation_result: { type: 'string', description: 'the exact assertion that fired when the bug was re-introduced, or WHY the mutation could not be run' },
    mutation_verified: { type: 'boolean', description: 'false if the guard was never seen failing — a test never seen fail is not a guard' },
    blocked:         { type: 'string', description: 'if applied=false, what blocked it' },
  },
}

const COMPLETENESS = {
  type: 'object',
  required: ['open_classes', 'proposed_detectors', 'what_was_not_swept'],
  properties: {
    open_classes:       { type: 'array', items: { type: 'string' } },
    proposed_detectors: { type: 'array', items: { type: 'object', required: ['detector', 'covers'],
                          properties: { detector: { type: 'string' }, covers: { type: 'string' } } } },
    what_was_not_swept: { type: 'string', description: 'the honest gap: a tree, a direction, or a claim left unverified. Never "nothing".' },
  },
}

const RULES = `
BINDING CONTEXT (this repo's governance — violating any of these makes your output unusable):
- MEASURE, THEN ANNOUNCE. Never state a number you have not just computed. A green test is not a
  measurement of the output. This applies to your own earlier statements too.
- A defect is an instance of a CLASS. One instance fixed with the class left alive is the repo's
  dominant failure (A6-quater: 36/38 references left dangling; A32: the same rename, second field,
  found a month later).
- An AST/structural check proves an edge is DRAWN, not that it BINDS (A24). Execution is the proof.
- You may NOT write to the ROADMAP and you may NOT commit. Return findings only.
- Read .claude/skills/impact-analysis.md and .claude/dev-docs/error-classes.md before concluding.
`.trim()

// ─── Phase 1+2+3 pipeline. No barrier between them: finding B is being critiqued while finding C is
// still in its impact sweep, and an approved fix starts as soon as ITS verdict lands. A barrier here
// would idle every fast finding behind the slowest sweep, for nothing — no stage needs cross-item
// context. (Phase 4 does, and it is the one place this script blocks.)

const findings = Array.isArray(args) ? args : (args ? [args] : [])
if (!findings.length) {
  log('no findings passed — call with args: ["symptom 1", "symptom 2", …]')
  return { error: 'no findings', manifest: [] }
}
log(`${findings.length} finding(s) — impact → critic → fix, pipelined`)

const results = await pipeline(
  findings,

  // ── Phase 1 · Impact ────────────────────────────────────────────────────────
  (finding, _orig, i) => agent(
    `${RULES}

You are running STEP 2 of .claude/workflows/engineering-loop.md — the whole-repo impact analysis —
on this finding:

  ${typeof finding === 'string' ? finding : JSON.stringify(finding)}

Follow .claude/skills/impact-analysis.md steps 1-3 EXACTLY, in order:

 1. REPRODUCE / CONFIRM. Get the real symptom: a traceback, a failing test, or a measured number.
    Never work from a guess. If the finding does not reproduce, set is_real=false and give the
    evidence that refutes it — a refuted finding is a successful analysis, not a failure.
 2. ROOT-CAUSE BY READING THE CODE. Name the true cause with file:line. If you cannot read your way
    to it, say so in root_cause and set confidence="inferred". Do not dress a hypothesis as a cause.
 3. WHOLE-REPO SIBLING SWEEP — the core step, and the one that is always skipped. grep the symbol
    across EVERY source tree the project has — application code, scripts, tools, tests AND
    `.claude/` — the config layer is inside the set, it is not exempt (a sweep that skipped
    .claude/ is how a sensor wrote 735 unread rows for 9 days). Ask the INVERSE question too:
    producer→caller AND artefact→reader (A17 hides in the first direction, A32 in the second).
    List EVERY hit. For each, decide same-bug or false-alarm and WRITE DOWN WHY. A hit you cleared
    without a reason is a hit you did not clear.

    ⚠️ SWEEP WITH grep AND Read — NOT with the repo-wide runners. Do not run audit_runner.py, do not
    run audit_invariants.py, do not run the test suite. All three are ALREADY in the deferred deploy
    batch, where they run ONCE; here they would run once PER FINDING for the same answer.
    MEASURED 2026-07-27 on this script's own first run: the phase-1 agent spent 25 minutes and never
    produced a fiche, because \`audit_runner.py --deterministic\` blew its 400 s tool timeout (exit
    143) and it retried in background. 0 of ~8 agent calls completed. If one SPECIFIC error class is
    relevant, run that single class's signature from error-classes.md — seconds, not the catalogue.

Then state the fix scope and the guard plan. The guard must name the MUTATION that will be used to
verify it — re-introduce the bug, watch it go red. Check whether this is an INSTANCE of a class
already in error-classes.md before proposing a new one; extending a class beats duplicating it.

Do NOT write any code. This phase produces a fiche, nothing else.`,
    { label: `impact:${String(i + 1).padStart(2, '0')}`, phase: 'Impact', schema: IMPACT }
  ),

  // ── Phase 2 · Critic — on the DESIGN, before a line is written ──────────────
  async (impact, orig, i) => {
    if (!impact) return null
    if (impact.is_real === false) {
      log(`  ${String(i + 1).padStart(2, '0')} refuted in impact — skipping critic and fix`)
      return { impact, verdict: { verdict: 'DO-NOT-BUILD', reason: `Refuted during impact analysis: ${impact.refutation || 'no evidence found'}` }, patch: null }
    }
    const verdict = await agent(
      `${RULES}

You are code-critic running STEP 6 of the engineering loop: a COLD AUDIT of a proposed fix DESIGN,
BEFORE a single line of it is written. A binding rule in this project's CLAUDE.md makes you mandatory for anything that decides an
irreversible outcome; this design declares decides_irreversible=${impact.decides_irreversible === true}.

  DEFECT ......... ${impact.title}
  ROOT CAUSE ..... ${impact.root_cause}
  CONFIDENCE ..... ${impact.confidence}
  FIX SCOPE ...... ${impact.fix_scope}
  GUARD PLAN ..... ${impact.guard_plan}
  SIBLINGS ....... ${JSON.stringify(impact.siblings)}

Audit it for, in this order:
  1. Does the fix address the ROOT CAUSE or the symptom? A patch on the symptom re-rots.
  2. Does it close the CLASS, or one instance? Name any sibling the scope leaves live.
  3. Is the guard real? A structural/AST assertion proves the edge is drawn, not that it binds (A24).
     Is the stated mutation one that would ACTUALLY fire, or would a second constraint mask it?
     (Measured 2026-07-27: two mutation verdicts were both wrong — one went red through a
     pre-existing branch, one survived because another constraint masked it.)
  4. If it touches anything deciding \`profitable\`: hidden coupling, a failure mode the guard cannot observe, a check that reuses the very
  data that produced the finding,
     in-sample contamination dressed as OOS, and whether a threshold is being tuned on the window
     that measured it. Any of these unresolved is DO-NOT-BUILD, not BUILD-MODIFIED.
  5. What does this change BREAK? Especially: does it re-mint a run_id (a catalogue event, ~2h20),
     or move a number that other documents restate?

Return exactly one verdict:
  BUILD ............ sound as designed
  BUILD-MODIFIED ... sound once required_modifications are applied — list them, specifically
  DO-NOT-BUILD ..... do not write this. Your reason becomes a ROADMAP brick, so make it stand alone.

Be cold. You are not here to approve. Praise is not an output of this phase.`,
      { label: `critic:${String(i + 1).padStart(2, '0')}`, phase: 'Critic', agentType: 'code-critic', schema: VERDICT }
    )
    return { impact, verdict, patch: null }
  },

  // ── Phase 3 · Fix — approved designs only, isolated worktree, NOT committed ──
  async (prev, orig, i) => {
    if (!prev || !prev.verdict) return prev
    const { impact, verdict } = prev
    if (verdict.verdict === 'DO-NOT-BUILD') {
      log(`  ${String(i + 1).padStart(2, '0')} DO-NOT-BUILD — ${String(verdict.reason).slice(0, 90)}`)
      return prev            // still reaches the manifest, carrying the refusal's reason
    }
    const mods = (verdict.required_modifications || [])
    const patch = await agent(
      `${RULES}

You are running STEPS 7-8 of the engineering loop on a design code-critic has APPROVED
(${verdict.verdict}). Implement it.

  DEFECT ......... ${impact.title}
  ROOT CAUSE ..... ${impact.root_cause}
  FIX SCOPE ...... ${impact.fix_scope}
  GUARD PLAN ..... ${impact.guard_plan}
  CRITIC ......... ${verdict.reason}
${mods.length ? `  REQUIRED MODIFICATIONS — these are NOT optional, the verdict is conditional on them:\n${mods.map(m => `    - ${m}`).join('\n')}` : ''}

Do all four, in order:
 1. Apply the fix — every sibling marked same_bug too, not just the first instance.
 2. Add the DURABLE GUARD: a signature in .claude/dev-docs/error-classes.md (a shell command,
    exit != 0 = hit) and/or a test. Follow the existing entry format exactly: status / kind /
    signature / guard / history, and the history states what was MEASURED, with numbers.
 3. MUTATION-VERIFY the guard. Re-introduce the bug, run the guard, confirm it goes RED, then
    restore. Report the exact assertion that fired.
    ⚠️ RESTORE FROM A BACKUP COPY (cp the file aside first). NEVER \`git checkout\` — it clobbered
    an uncommitted fix on 2026-07-19 and that is a recorded REX.
    ⚠️ Confirm the RIGHT assertion fired. A test going red through a pre-existing branch, or a
    mutation surviving because a second constraint masks it, are both FALSE verdicts — set
    mutation_verified=false and say so rather than claiming a guard you did not see work.
 4. Run ONLY the targeted test for your guard. Do NOT run the full suite, do NOT run pytest tests/ —
    the batch is deferred to the deploy step by design and running it here costs ~15 minutes per
    finding for information the deploy step will produce once.
 5. Return the COMPLETE \`git diff\` in the \`diff\` field. ⚠️ YOU ARE IN AN ISOLATED WORKTREE: the
    main repo cannot see your files, and this diff is the ONLY way your work survives. A patch you
    applied but did not return is a phase that reports success and delivers nothing.

DO NOT: git add, git commit, git push, or edit .claude/dev-docs/roadmap/*.md. The main context records
the ROADMAP with the measuring command's output (binding rule 4) and owns the deploy order.`,
      { label: `fix:${String(i + 1).padStart(2, '0')}`, phase: 'Fix', schema: PATCH, isolation: 'worktree' }
    )
    return { impact, verdict, patch }
  }
)

// ─── Phase 4 · Improve. THE one barrier, and it is justified: a completeness critic that cannot see
// every finding at once is just another per-finding reviewer. It needs the whole set to answer
// "which class is still open across all of this".

// NO SILENT CAPS. `agent()` returns null if the user skips it or a subagent dies on a terminal API
// error after retries, and `.filter(Boolean)` would quietly shrink the population — a manifest of 2
// for a run of 5 reads as "5 findings handled" to anyone who does not count. Say what was lost, by
// name: a dropped finding is a finding still open, not a finding resolved.
const dropped = results.map((r, i) => (r ? null : findings[i])).filter(Boolean)
if (dropped.length) {
  log(`⚠️ ${dropped.length} finding(s) produced NO result and are NOT in the manifest — still open:`)
  dropped.forEach(f => log(`    · ${String(typeof f === 'string' ? f : JSON.stringify(f)).slice(0, 120)}`))
}

const done = results.filter(Boolean)
const built = done.filter(r => r.patch && r.patch.applied)
const refused = done.filter(r => r.verdict && r.verdict.verdict === 'DO-NOT-BUILD')
const unverified = built.filter(r => r.patch.mutation_verified === false)
log(`impact/critic/fix done — ${built.length} patched · ${refused.length} refused · ${unverified.length} guard(s) NOT mutation-verified`)

const improve = await agent(
  `${RULES}

You are the COMPLETENESS CRITIC — the last phase of the engineering loop. Your job is not to review
the fixes. It is to answer: WHAT IS STILL OPEN?

Here is everything the run produced:

${JSON.stringify(done.map(r => ({
    title: r.impact && r.impact.title,
    error_class: r.impact && r.impact.error_class,
    root_cause: r.impact && r.impact.root_cause,
    siblings_same_bug: r.impact && (r.impact.siblings || []).filter(s => s.same_bug).map(s => s.path),
    siblings_cleared: r.impact && (r.impact.siblings || []).filter(s => !s.same_bug).map(s => s.path),
    verdict: r.verdict && r.verdict.verdict,
    reason: r.verdict && r.verdict.reason,
    files_touched: r.patch && r.patch.files_touched,
    guard: r.patch && r.patch.guard,
    mutation_verified: r.patch && r.patch.mutation_verified,
  })), null, 1)}

Answer three questions, and answer the third one honestly:

 1. WHICH CLASS REMAINS OPEN? For each fix, is the class closed or only this instance? Cross-check
    against .claude/dev-docs/error-classes.md — an existing class that gained an instance should be
    EXTENDED, not duplicated as a new one.
 2. WHICH SINGLE DETECTOR WOULD COVER THE LOT? Prefer a detector over an agent, always: a signature
    in error-classes.md runs free on every change forever; an agent is a file someone must remember
    to call (measured: 26 of 29 declared agents in this repo have never been invoked). If two or
    more findings share a shape, name the ONE check that would have caught them all.
 3. WHAT WAS NOT SWEPT? Name the tree, the direction, or the claim left unverified. "Nothing" is not
    an acceptable answer — every sweep has a boundary, and the boundary is the finding. Two of this
    repo's expensive defects were exactly this: a coverage % whose denominator omitted a whole tree
    (.claude/workflows/ for the REX validator; python/ only for the orphan detector).`,
  { label: 'completeness', phase: 'Improve', schema: COMPLETENESS }
)

// ─── The deploy manifest. NOT a deploy — the main context does that, in the playbook's order:
// ROADMAP first (each item with the command that measured it and its output), then the single
// verification batch, then commit + push.

return {
  summary: {
    findings: findings.length,
    in_manifest: done.length,
    dropped_still_open: dropped.length,   // != 0 means the manifest does NOT cover the run
    patched: built.length,
    refused: refused.length,
    guards_not_mutation_verified: unverified.length,
  },
  manifest: done.map(r => ({
    title: r.impact && r.impact.title,
    error_class: r.impact && r.impact.error_class,
    root_cause: r.impact && r.impact.root_cause,
    confidence: r.impact && r.impact.confidence,
    verdict: r.verdict && r.verdict.verdict,
    critic_reason: r.verdict && r.verdict.reason,
    required_modifications: r.verdict && r.verdict.required_modifications,
    files_touched: (r.patch && r.patch.files_touched) || [],
    diff: r.patch && r.patch.diff,        // apply with `git apply` — see the PATCH schema comment
    guard: r.patch && r.patch.guard,
    mutation_result: r.patch && r.patch.mutation_result,
    mutation_verified: r.patch && r.patch.mutation_verified,
    // A DO-NOT-BUILD is not a silent drop — it becomes a ROADMAP brick carrying the refusal's reason.
    roadmap_action: r.verdict && r.verdict.verdict === 'DO-NOT-BUILD'
      ? 'brick: record the refusal AND its reason'
      : 'checked-off item: record the fix WITH the command that proves it and that command output',
  })),
  completeness: improve,
  deploy_order: [
    '1. ROADMAP first — every item above, each with the command that measured it and its OUTPUT (rule 4)',
    '2. then the deferred batch, ONCE: pytest tests/ -q · audit_invariants.py · audit_runner --deterministic --coverage · validate_rex.py · roadmap_stats.py --write',
    '3. then commit the approved fixes and push origin master (the VPS pulls — an unpushed commit is invisible to prod)',
    '4. DEVLOG: Why / What changed / Backtest evidence',
    '⚠️ never edit a tracked file while the suite runs — such a run is contaminated, not green',
  ],
}
