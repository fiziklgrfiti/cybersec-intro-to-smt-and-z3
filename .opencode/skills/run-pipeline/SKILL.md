# skill: run-pipeline

Use this skill when asked to run the requirements engine, execute the Z3 solver,
demonstrate the tool, or produce analysis output.

---

## prerequisites

Before running any pipeline stage, verify the virtual environment is active:

```bash
# check the venv is active — python should resolve inside .venv/
which python
# expected: <project-root>/.venv/bin/python
```

If it is not active:

```bash
source .venv/bin/activate
```

If `.venv/` does not exist (fresh clone), run the bootstrap script first:

```bash
bash setup.sh
source .venv/bin/activate
```

---

## running the full pipeline — opencode-native (preferred, no api key required)

When running inside OpenCode (e.g. GitHub Copilot or any other configured
model), stages 1 and 2 are performed by the agent itself. No `ANTHROPIC_API_KEY`
is needed.

### step 1 — perform stage 1: LLM requirement rewriting

Read `data/requirements.py` to obtain the NIST PR.AA requirements, then apply
the system prompt and user prompt defined in `skills/skill_01_rewriter.py`
(the `SYSTEM_PROMPT` and `USER_PROMPT_TEMPLATE` constants) using your own model.

The response must be a JSON array matching the schema in `SYSTEM_PROMPT`.
Write the result to `.opencode/pipeline/stage1_output.json`.

Example output shape:

```json
[
  {
    "id": "PR.AA-01",
    "original": "...",
    "rewritten": [
      {
        "id": "PR.AA-01.1",
        "statement": "The organization SHALL ...",
        "subject": "...",
        "object": "...",
        "condition": "...",
        "testable_indicator": "..."
      }
    ]
  }
]
```

### step 2 — perform stage 2: formal representation

Using the stage 1 output as input, apply the system prompt and user prompt
defined in `skills/skill_02_formalizer.py` (`SYSTEM_PROMPT` and
`USER_PROMPT_TEMPLATE`) using your own model.

Write the result to `.opencode/pipeline/stage2_output.json`.

Example output shape:

```json
[
  {
    "id": "PR.AA-01",
    "pseudo_logic": "∀ e ∈ Entity: ...",
    "smt_lib2": "(declare-sort Entity 0)\n...",
    "sorts_used": ["Entity"],
    "predicates_used": ["has_credentials"]
  }
]
```

### step 3 — run stage 3 (Z3 solver) using the pre-computed files

```bash
python run.py --from-files
```

This loads `.opencode/pipeline/stage1_output.json` and
`.opencode/pipeline/stage2_output.json`, skips the API call, and runs the Z3
solver (stage 3) against the agent-produced formal representations.

Z3 now reasons **directly over the SMT-LIB2 produced in step 2** — the axioms
are derived dynamically from Stage 2 output, not hard-coded.  Gaps that are
properly closed in the Stage 1/2 artefacts will be confirmed closed by Z3 in
the same pass.

By default, `selected_req_ids` is derived from the requirement IDs present in
`stage1_output.json`.  To be explicit, or to analyse a subset, use:

```bash
python run.py --from-files --requirements PR.AA-01 PR.AA-03
```

Only Z3 checks whose required scope is a subset of the selected IDs will run.

---

## running the full pipeline — direct api path (requires ANTHROPIC_API_KEY)

If `ANTHROPIC_API_KEY` is set in the environment, the Python scripts call the
Anthropic API directly. No agent involvement in stages 1 and 2.

```bash
export ANTHROPIC_API_KEY=<your-api-key>
python run.py
```

The pipeline runs four stages in sequence:

| stage | what happens |
|-------|-------------|
| 0 | loads and displays the six raw NIST CSF 2.0 PR.AA outcomes |
| 1 | LLM rewrites each outcome into structured SHALL statements (JSON) |
| 2 | LLM translates SHALL statements into pseudo-logic and SMT-LIB2 |
| 3 | Z3 SMT solver runs six automated proofs; surfaces gaps and ambiguities |

Stage 1 and 2 output is also saved to `.opencode/pipeline/` as a side-effect.

---

## running offline (no api key, no agent required)

Stages 1 and 2 are replaced with stub data. Stage 3 runs real Z3 proofs.
Useful for demos, air-gapped environments, or studying the solver in isolation.

```bash
python run.py --no-llm
```

---

## running a single stage in isolation

Each skill is independently executable. Skills 1 and 2 require `ANTHROPIC_API_KEY`
when run standalone (they use the Anthropic SDK directly).
Skill 3 has no external dependencies beyond `z3-solver`.

```bash
# stage 1 only — LLM rewriting (requires ANTHROPIC_API_KEY)
python skills/skill_01_rewriter.py

# stage 2 only — formal logic generation (runs stage 1 automatically as prerequisite)
python skills/skill_02_formalizer.py

# stage 3 only — Z3 solver (no API key, no prerequisites)
python skills/skill_03_smt_solver.py
```

---

## interpreting findings

| symbol | kind | meaning | Z3 result |
|--------|------|---------|-----------|
| ✅ | SAT | no contradiction at this check | `sat` (desired) |
| ⚠️ | GAP | a required implication between requirements is missing | `sat` (counterexample exists) |
| 🔍 | AMBIGUITY | a predicate is formally undefined or unconstrained | `sat` (vacuously satisfiable) |
| ❌ | UNSAT | a contradiction — two requirements conflict | `unsat` (unexpected) |

---

## troubleshooting

**`z3-solver` import error** — venv is not active or setup.sh has not been run:
```bash
bash setup.sh && source .venv/bin/activate
```

**`ANTHROPIC_API_KEY is not set`** — either export the key, use `--from-files`
after completing the OpenCode-native steps above, or use `--no-llm`:
```bash
python run.py --no-llm
```

**`.opencode/pipeline/stage1_output.json` not found** — the OpenCode agent
steps above have not been completed yet. Run steps 1 and 2 first, then:
```bash
python run.py --from-files
```

**`ModuleNotFoundError: No module named 'data'`** — run from the project root,
not from inside a subdirectory:
```bash
# correct — from project root:
python run.py
```

---

## after stage 3 — offering remediation

After `python run.py --from-files` completes, if the output contains any
⚠️ GAP or 🔍 AMBIGUITY findings, always offer the user the Stage 4 feedback loop:

> "There are [N] findings. The Stage 4 feedback loop can rewrite the implicated
> requirements with gap-closing guidance and re-validate with Z3.
> Load the `remediate` skill to proceed."

If the user accepts, load the `remediate` skill and follow it exactly.
Do not attempt to drive Stage 4 from memory.
