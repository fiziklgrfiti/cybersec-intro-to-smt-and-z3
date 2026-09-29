# skill: add-requirement

Use this skill when asked to add a new NIST requirement or outcome to the
pipeline data set.

---

## when to use this

- "add PR.AA-07 to the requirements"
- "include this new NIST outcome in the analysis"
- "extend the dataset with a new requirement"

---

## step 1 — edit `data/requirements.py`

Open `data/requirements.py` and add a new entry to the `requirements` list:

```python
{
    "id": "PR.AA-07",
    "text": (
        "the exact NIST outcome text, verbatim from the framework document"
    ),
},
```

Keep the `id` consistent with the NIST CSF 2.0 identifier scheme
(e.g. `PR.AA-07`, `DE.CM-01`). The `text` field should be the verbatim
published outcome — do not paraphrase.

---

## step 2 — run stages 1 and 2 to rewrite and formalise

With `ANTHROPIC_API_KEY` set, run the full pipeline to see how the LLM handles
the new requirement:

```bash
source .venv/bin/activate
python run.py
```

Or run each stage independently to inspect intermediate output:

```bash
python skills/skill_01_rewriter.py     # rewriting only
python skills/skill_02_formalizer.py   # formalisation (runs stage 1 first)
```

---

## step 3 — optionally extend the Z3 domain model

The Stage 3 solver uses a hand-crafted domain model in `build_model()` inside
`skills/skill_03_smt_solver.py`. Adding a requirement to `data/requirements.py`
does **not** automatically add it to the Z3 model — the model must be updated
manually if you want the new requirement to participate in proofs.

To extend the domain model:

1. Identify the new predicates introduced by the requirement
2. Declare them in `build_model()` as `Function(...)` objects
3. Write the axiom as a `ForAll(...)` + `Implies(...)` expression
4. Add the axiom to the `axioms` list
5. Add it to the returned dict so checks can reference it

See the `add-z3-check` skill for full syntax and patterns.

---

## step 4 — verify

Run the solver standalone to confirm the model is still globally consistent
(Check 1 should remain SAT):

```bash
python skills/skill_03_smt_solver.py
```

A new axiom that causes Check 1 to return UNSAT means the new requirement
contradicts an existing one — that is a finding, not a bug. Document it.
