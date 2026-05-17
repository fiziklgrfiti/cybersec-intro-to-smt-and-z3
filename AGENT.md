# AGENT.md — Requirements Engine
## Claude Code Orchestration Guide

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
        ▼  Stage 1  [skill_01_rewriter.py]
   Claude API: rewrite vague language → precise testable SHALL statements
        │
        ▼  Stage 2  [skill_02_formalizer.py]
   Claude API: translate criteria → pseudo-logic (∀ →) + SMT-LIB2
        │
        ▼  Stage 3  [skill_03_smt_solver.py]
   Z3 Python API: run proofs → surface gaps, ambiguities, contradictions
        │
        ▼
   Terminal summary with finding counts
```

---

## Commands

### Full pipeline (requires ANTHROPIC_API_KEY)
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
# Skill 1 only — rewrite requirements
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
1. Check for ANTHROPIC_API_KEY in environment
2. Run `python run.py`
3. Capture and display output

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

- `anthropic>=0.25.0` — Claude API client
- `z3-solver>=4.12.0` — SMT solver (Z3)
- Python 3.11+ recommended (uses `list[dict] | None` union syntax)

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
│   ├── skill_01_rewriter.py    ← Stage 1: LLM rewriting
│   ├── skill_02_formalizer.py  ← Stage 2: Formal logic generation
│   └── skill_03_smt_solver.py  ← Stage 3: Z3 proofs
└── utils/
    └── terminal.py             ← ANSI display helpers
```
