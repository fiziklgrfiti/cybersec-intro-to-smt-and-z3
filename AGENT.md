# AGENT.md — Requirements Engine
## OpenCode Orchestration Guide

This agent orchestrates a four-stage cybersecurity requirements analysis pipeline
against NIST CSF 2.0 outcomes. Each stage is a discrete, independently runnable skill.

---

## Pipeline Architecture

```
NIST Requirements (data/requirements.py)
        │
        ▼  Stage 0
   Display raw NIST PR.AA outcomes
        │
        ▼  Stage 1  [skill_01_rewriter.py  OR  OpenCode agent]
   Rewrite vague language → precise testable SHALL statements
        │
        ▼  Stage 2  [skill_02_formalizer.py  OR  OpenCode agent]
   Translate criteria → pseudo-logic (∀ →) + SMT-LIB2
        │
        ▼  Stage 3  [skill_03_smt_solver.py]
   Z3 Python API: run proofs → surface gaps, ambiguities, contradictions
        │
        ▼
   Terminal summary with finding counts
```

---

## Commands

### Full pipeline — OpenCode-native (preferred, no API key required)

When running inside OpenCode (e.g. GitHub Copilot or any other configured model),
the agent itself performs stages 1 and 2. Load the `run-pipeline` skill for the
detailed workflow. In brief:

1. Read `data/requirements.py` and apply the prompts in `skills/skill_01_rewriter.py`
   using your own model. Write output to `.opencode/pipeline/stage1_output.json`.
2. Apply the prompts in `skills/skill_02_formalizer.py` using the stage 1 output.
   Write output to `.opencode/pipeline/stage2_output.json`.
3. Run the Z3 solver against the pre-computed files:

```bash
python run.py --from-files
```

### Full pipeline — direct API path (requires ANTHROPIC_API_KEY)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python run.py
```

### Offline demo — Z3 only, no API calls

```bash
python run.py --no-llm
```

### Run a single skill in isolation

```bash
# Skill 1 only — rewrite requirements (requires ANTHROPIC_API_KEY when run standalone)
python skills/skill_01_rewriter.py

# Skill 2 only — formalise (runs skill 1 as prerequisite automatically)
python skills/skill_02_formalizer.py

# Skill 3 only — Z3 solver (no prerequisites, runs standalone)
python skills/skill_03_smt_solver.py
```

---

## Agent Tasks

When asked to run or extend this pipeline, the agent should:

### Task: Run the full pipeline
1. Load the `run-pipeline` OpenCode skill for the full workflow
2. Perform stages 1 & 2 using the agent's own model (write JSON to `.opencode/pipeline/`)
3. Run `python run.py --from-files`
4. Capture and display output

### Task: Run Z3 solver only (offline demo)
1. Run `python run.py --no-llm`
2. The Z3 stage runs with stub formal data — findings are still real

### Task: Add a new requirement
1. Open `data/requirements.py`
2. Add an entry to the `requirements` list with a new `id` and `text`
3. Optionally extend `skills/skill_03_smt_solver.py` with a new check function
4. Register the new check in the `CHECKS` list at the bottom of skill_03

### Task: Add a new Z3 check
1. Open `skills/skill_03_smt_solver.py`
2. Write a new function `check_NN_<name>(m: dict) -> dict`
3. The function receives the model dict (all predicates and axioms) and returns:
   ```python
   {"kind": "GAP|SAT|AMBIGUITY|UNSAT", "check": "description", "detail": "..."}
   ```
4. Add the function to the `CHECKS` list
5. Add a scope entry to `CHECK_REQUIREMENT_MAP`

### Task: Swap in a different NIST category
1. Create a new file in `data/` (e.g. `data/requirements_detect.py`)
2. Follow the same structure as `data/requirements.py`
3. Update the import in `run.py`: `from data.requirements_detect import NIST_DE_CM as NIST_PR_AA`
4. Build a matching Z3 domain model in `skills/skill_03_smt_solver.py`

---

## Dependency Notes

- `anthropic>=0.25.0` — Claude API client (used by skill_01/skill_02 for the direct API path)
- `z3-solver>=4.12.0` — SMT solver (Z3)
- Python 3.11+ recommended (uses `list[dict] | None` union syntax)

The `anthropic` package is only exercised when `ANTHROPIC_API_KEY` is set and
`python run.py` is called without `--from-files` or `--no-llm`. When running
via OpenCode, the agent handles LLM calls and the package is not invoked.

Install with:
```bash
pip install -r requirements.txt
```

---

## Finding Types

| Kind        | Meaning                                          | Z3 result |
|-------------|--------------------------------------------------|-----------|
| `SAT`       | Check passed — no issue found                    | sat       |
| `GAP`       | A required implication is missing                | sat (bad) |
| `AMBIGUITY` | A predicate is unconstrained / undefined         | sat       |
| `UNSAT`     | Contradiction found — requirements conflict      | unsat     |

---

## File Map

```
requirements-engine/
├── AGENT.md                    ← this file
├── README.md                   ← setup & usage
├── requirements.txt            ← Python dependencies
├── run.py                      ← full pipeline orchestrator
├── data/
│   └── requirements.py         ← NIST PR.AA source data
├── skills/
│   ├── skill_01_rewriter.py    ← Stage 1: LLM rewriting (or OpenCode agent)
│   ├── skill_02_formalizer.py  ← Stage 2: Formal logic generation (or OpenCode agent)
│   └── skill_03_smt_solver.py  ← Stage 3: Z3 proofs
├── .opencode/
│   ├── skills/run-pipeline/    ← OpenCode skill: full pipeline workflow
│   └── pipeline/               ← intermediate JSON output (gitignored)
│       ├── stage1_output.json  ← produced by agent or skill_01 direct run
│       └── stage2_output.json  ← produced by agent or skill_02 direct run
└── utils/
    └── terminal.py             ← ANSI display helpers
```
