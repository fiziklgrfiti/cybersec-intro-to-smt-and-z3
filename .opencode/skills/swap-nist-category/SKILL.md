# skill: swap-nist-category

Use this skill when asked to change the NIST CSF 2.0 category being analysed,
load a different set of outcomes, or target a different function (e.g. DE.CM
instead of PR.AA).

---

## when to use this

- "swap to the DE.CM category"
- "run the pipeline against detect outcomes"
- "analyse GV.OC instead of PR.AA"
- "change the requirements dataset to a different NIST category"

---

## step 1 — create a new requirements file

Create a new file under `data/` following the same structure as
`data/requirements.py`.

Example for DE.CM (Detect: Continuous Monitoring):

```python
"""
NIST CSF 2.0 — DE.CM (Continuous Monitoring)
Source: https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf
"""

NIST_DE_CM = {
    "framework": "NIST CSF 2.0",
    "domain": "DETECT (DE)",
    "category_id": "DE.CM",
    "category_name": "Continuous Monitoring",
    "category_description": (
        "assets are monitored to find anomalies, indicators of compromise,
        and other potentially adverse events"
    ),
    "requirements": [
        {
            "id": "DE.CM-01",
            "text": "networks and network services are monitored to find potentially adverse events",
        },
        # add remaining outcomes...
    ],
}
```

Required fields:

| field | description |
|-------|-------------|
| `framework` | always `"NIST CSF 2.0"` |
| `domain` | the CSF function, e.g. `"DETECT (DE)"` |
| `category_id` | e.g. `"DE.CM"` |
| `category_name` | the category's published name |
| `category_description` | the category-level description from the framework |
| `requirements` | list of `{"id": "...", "text": "..."}` dicts |

---

## step 2 — update the import in `run.py`

Open `run.py` and change the import at the top:

```python
# before:
from data.requirements import NIST_PR_AA

# after (example — swap variable name to match the new file's export):
from data.requirements_detect import NIST_DE_CM as NIST_PR_AA
```

The alias `as NIST_PR_AA` keeps the rest of `run.py` working without further
changes — the variable name throughout the orchestrator stays the same.

---

## step 3 — rebuild the Z3 domain model

The domain model in `skills/skill_03_smt_solver.py` (`build_model()`) is
hand-crafted for PR.AA concepts (`Entity`, `Asset`, `has_credentials`, etc.).
A different category introduces different concepts and requires a new model.

For each new requirement:

1. Identify the key entities, assets, or events referenced
2. Declare new sorts if needed (e.g. `Event = DeclareSort("Event")`)
3. Declare predicates as `Function(...)` objects
4. Write axioms as `ForAll(...)` + `Implies(...)` expressions
5. Add axioms to the `axioms` list
6. Design new check functions (see the `add-z3-check` skill)

The existing PR.AA checks (`check_01` through `check_06`) can be left in place
or removed — they will still run against the new model, but their results may
not be meaningful for a different domain.

---

## step 4 — verify

Run the full offline pipeline to confirm the new category loads and stages 0–3
execute without error:

```bash
source .venv/bin/activate
python run.py --no-llm
```

Then run with the LLM stages if `ANTHROPIC_API_KEY` is available:

```bash
python run.py
```

Check 1 (global consistency) should return SAT for the new axiom set before
building additional checks.
