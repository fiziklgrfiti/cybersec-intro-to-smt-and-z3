# Skill: remediate

Run the Stage 4 deep feedback loop to close gaps and ambiguities identified by
the Z3 solver.  Unlike a surface-level patch, this loop flows backwards to
rewrite the implicated Stage 1 SHALL statements with explicit gap-closing
guidance, re-formalises them in Stage 2, then re-validates with Z3.  Each pass
produces versioned output files so every revision is independently inspectable
and rollback/rollforward is safe.

---

## When to use this skill

Use this skill when:

- Stage 3 has produced findings (⚠️ GAP or 🔍 AMBIGUITY) and the user wants
  to resolve them by improving the underlying requirements.
- The user asks to "fix the gaps", "close the findings", "remediate", or
  "run the feedback loop".

Do NOT use this skill to modify `data/requirements.py` or any `skills/` source
file.  All fixes work by producing versioned Stage 1/2 output files.

---

## Why this matters

Because Z3 now reasons directly over the SMT-LIB2 derived from Stage 1/2
output, a gap that is properly closed in the new SHALL statements will be
**confirmed closed by Z3 in the same pass** — no manual axiom patching required.

Stage 4 does exactly this:
1. Identifies which requirement IDs are implicated in each gap/ambiguity
2. Rewrites only those requirements' SHALL statements, carrying specific
   missing-link guidance into the Stage 1 prompt
3. Re-formalises the updated SHALL statements in Stage 2
4. Re-runs Z3 against the new SMT-LIB2 to confirm the gap is closed
5. Shows inline before/after annotations per check and a running scoreboard

---

## Pre-flight checklist

1. Confirm `.opencode/pipeline/stage1_output.json` and
   `stage2_output.json` both exist (produced by a prior pipeline run).
2. Confirm the virtual environment is active:
   ```
   which python   # should point to .venv/bin/python
   ```
3. Confirm Z3 is installed:
   ```
   python -c "import z3; print(z3.get_version_string())"
   ```

---

## Running the loop

### With ANTHROPIC_API_KEY set (fully automated)

The loop runs end-to-end without agent involvement.  Stage 1/2 rewrites are
performed by the Anthropic SDK directly.

**User-confirmed mode (default — recommended for demos):**

```bash
python run.py --from-files --remediate
```

After each pass the pipeline will:
1. Print the planned fixes block (what will change, which axiom, why)
2. Rewrite the implicated Stage 1 SHALL statements with gap-closing guidance
3. Re-formalise Stage 2
4. Re-run Z3 and show inline before/after annotations per check
5. Print the delta (resolved / new / remaining) and the progress scoreboard
6. Prompt: `Run another remediation pass? [y/n]`
7. After all gaps are closed, prompt: `Continue into ambiguity fixes? [y/n]`

**Non-interactive / capped mode:**

```bash
python run.py --from-files --remediate --max-passes 3
```

Runs up to 3 passes without prompting.  Automatically proceeds into ambiguity
fixes after gaps are resolved.

### Without ANTHROPIC_API_KEY (agent handoff path)

When no API key is set, the loop pauses after identifying the implicated
requirements and writes a guidance file:

```
.opencode/pipeline/stage4_guidance.json
```

The terminal output will print clear instructions.  As the agent, you must:

1. Read `.opencode/pipeline/stage4_guidance.json`
2. Note the `revision` number (N), `stage`, and `requirements` dict
3. For each requirement ID listed in `requirements`:
   a. Load the current stage output (e.g. `stage1_output.json` or the latest rN)
   b. Apply the standard Stage 1 prompt from `skills/skill_01_rewriter.py`
      **plus** the guidance text from the `requirements` entry as an additional
      instruction (it specifies exactly which SHALL statement to add and why)
   c. Merge the result back — replace only this requirement's entry, keep all others
   d. Write the merged array to `stage1_output.r{N}.json`
4. Repeat for Stage 2 using `skills/skill_02_formalizer.py` prompts
5. Run the `resume_command` from the guidance file, e.g.:
   ```bash
   python run.py --from-files --revision 1 --remediate
   ```

---

## Versioned output files

Each pass through the loop produces a new pair of files.  The baseline is
never overwritten.

```
.opencode/pipeline/
  stage1_output.json          ←  baseline (initial run, revision 0)
  stage2_output.json          ←  baseline
  stage1_output.r1.json       ←  after pass 1
  stage2_output.r1.json
  stage1_output.r2.json       ←  after pass 2
  stage2_output.r2.json
  stage4_patches.json         ←  patch log (all passes, all revisions)
  stage4_guidance.json        ←  agent handoff file (written when no API key)
```

### Loading a specific revision

```bash
# Load and display revision 2 (runs Z3 against r2 files)
python run.py --from-files --revision 2

# Continue remediating from revision 2
python run.py --from-files --revision 2 --remediate
```

Omitting `--revision` with `--remediate` defaults to the latest revision present.

### Rolling back

To go back to an earlier revision, simply pass `--revision N` with the desired
revision number.  The rN files are never deleted by the pipeline.

---

## What Stage 4 does — pass structure

| Phase | What happens |
|-------|-------------|
| 4a — identify | Find which requirement IDs are implicated in each open gap/ambiguity using `FINDING_REQUIREMENT_MAP` |
| 4b — guidance | Build a targeted Stage 1 rewrite prompt per requirement, carrying the specific missing-link instruction from `AXIOM_GUIDANCE_MAP` |
| 4c — Stage 1 rewrite | Re-run Stage 1 for implicated requirements only; merge back into full array; write `stage1_output.rN.json` |
| 4d — Stage 2 formalise | Re-run Stage 2 for the same requirements; merge back; write `stage2_output.rN.json` |
| Validate | Re-run Z3 against the rN files; show inline before/after per check; compute delta; update scoreboard |

### Finding → requirement mapping

| Finding (check name substring) | Implicated requirements | Missing link to introduce |
|-------------------------------|------------------------|--------------------------|
| `Authentication ↛ Credential Management` | PR.AA-01, PR.AA-03 | `is_authenticated(e) → has_credentials(e)` |
| `Access ↛ Identity Proofing` | PR.AA-02, PR.AA-03 | Same bridge — closes downstream chain |
| `has_access ↛ credentials_managed` | PR.AA-01, PR.AA-03 | `has_access(e,a) → has_credentials(e)` |
| `Separation of Duties — undefined` | PR.AA-05 | Define SoD criteria and two-person authorisation |
| `Physical/Logical access boundary` | PR.AA-05, PR.AA-06 | `is_physical_asset(a) ∧ has_access(e,a) → access_in_policy(e,a)` |

---

## Reading the output

### Planned fixes block (before each pass)

Before any rewrite occurs, the pipeline prints a boxed block listing every
finding targeted, the axiom/link to be introduced, and the rationale.  This
is your opportunity to understand what will change before it happens.

### Inline before/after annotations (after Z3 re-runs)

Each check result is annotated when it changes:

```
✅  [SAT]  PR.AA-03 + PR.AA-01: Authentication → Credential Management
           ↳ was ⚠️ [GAP] — closed this revision
```

Checks that were already passing show no annotation.  Checks still failing
show `↳ still open`.

### Progress scoreboard

After every pass a compact table shows the trend:

```
  ┌─ Progress scoreboard ───────────────────────────────────────────
  │  Revision      ✅ SAT    ⚠️  Gaps   🔍 Ambig    ❌ Unsat
  │  ─────────────────────────────────────────────────────────────
  │  Baseline           1         3          2           0
  │  r1          →      4         0 ✓        2           0
  └────────────────────────────────────────────────────────────────
```

`✓` marks any cell where the count improved compared to the previous revision.
The `r1: 0 gaps` outcome is achievable — when the bridging axiom is present in
the Stage 2 SMT-LIB2, Z3 confirms the gap is closed directly.

### Patch log

All applied rewrites are recorded in:

```
.opencode/pipeline/stage4_patches.json
```

Each entry records:
- `pass`         — which pass produced this entry
- `check`        — the finding check name
- `kind`         — GAP or AMBIGUITY
- `fix_source`   — always `stage1_rewrite` (the durable fix mechanism)
- `req_id`       — which requirement was rewritten
- `description`  — human-readable summary
- `guidance`     — the exact guidance text carried into the Stage 1 prompt
- `output_file`  — the versioned file that was produced

---

## Loop termination conditions

| Condition | Message shown |
|-----------|---------------|
| No open issues remain | `✅  All issues resolved.` |
| `--max-passes N` reached | `Max passes (N) reached — stopping.` |
| User answers `n` at prompt | `Stopping remediation loop.` |
| No progress made in a pass | `—  No progress made — stopping to avoid infinite loop.` |
| API key absent | `Agent handoff required` — writes guidance file and pauses |

When "no progress" is reported, the remaining findings are likely ambiguities
that require new sub-requirements to be authored manually (e.g. defining what
"separation of duties" means in your organisation).  The patch log and guidance
file document exactly what is needed.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `stage4_guidance.json` missing after pause | Pipeline directory not writable | `mkdir -p .opencode/pipeline` |
| `stage1_output.r1.json not found` after agent handoff | Agent did not write the file | Re-read guidance file and complete the rewrite step |
| `No progress made — stopping` immediately | Open findings are all ambiguities with no matching guidance | Set `fix_ambiguities=True` or add guidance to `AXIOM_GUIDANCE_MAP` |
| Check 1 (global consistency) flips to UNSAT after a pass | New SHALL statements introduced a contradiction | Load the rN files, inspect the new statements, and revise |
| LLM returns requirements with wrong ID | Model hallucination | Check the merged rN file; manually correct the ID and re-run |
