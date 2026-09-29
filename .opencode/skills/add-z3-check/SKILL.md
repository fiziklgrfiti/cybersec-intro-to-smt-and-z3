# skill: add-z3-check

Use this skill when asked to add a new Z3 proof, create a new logical check,
or extend `skills/skill_03_smt_solver.py` with a new assertion against the
PR.AA domain model.

---

## when to use this

- "add a check that verifies X"
- "prove that Y is guaranteed by the requirements"
- "write a new Z3 proof for Z"
- "extend the solver with a check for separation of duties"

---

## step 1 — understand the domain model

All Z3 sorts, predicates, and axioms are declared in `skills/skill_03_smt_solver.py`.
Read this file first to understand what predicates are available.

**Two model-building paths:**

- `build_model(formal)` — production path.  Parses Stage 2 SMT-LIB2 output to
  build axioms dynamically.  Used by `run.py --from-files` and the Stage 4 loop.
- `build_reference_model()` — regression/standalone path.  Hard-coded PR.AA axioms.
  Used only when `python skills/skill_03_smt_solver.py` is run directly.

New checks you write work in both contexts, provided they reference only
predicates from the canonical vocabulary defined in `skill_02_formalizer.py`.
The canonical predicates are declared as module-level constants in
`skill_03_smt_solver.py` and are always available via the model dict.

Key sorts: `Entity`, `Asset`

Key predicates (Entity → Bool): `has_credentials`, `credentials_managed`,
`identity_proofed`, `identity_bound`, `is_authenticated`, `assertion_protected`,
`assertion_verified`

Key predicates (Entity × Asset → Bool): `has_access`, `access_authorized`,
`access_in_policy`, `least_privilege_applied`, `sep_of_duties_applied`,
`access_reviewed`, `physical_access_monitored`

Key predicates (Asset → Bool): `is_physical_asset`, `risk_assessed`

---

## step 2 — write the check function

Add a new function to `skills/skill_03_smt_solver.py` following this pattern:

```python
def check_07_my_new_check(m: dict) -> dict:
    """
    describe what you are testing and why.
    state the expected result and what it means if SAT or UNSAT.
    """
    e, a = m["e"], m["a"]
    s = _solver_with_axioms(m["axioms"])

    # to check if property P is guaranteed by the axioms:
    #   assert Not(P) and check satisfiability.
    #   if UNSAT: P is always guaranteed (negation is impossible).
    #   if SAT:   P is not guaranteed — a counterexample exists (gap).
    s.add(m["has_access"](e, a))
    s.add(Not(m["some_predicate"](e)))

    result = s.check()
    if result == sat:
        return {
            "kind": "GAP",       # GAP | AMBIGUITY | UNSAT | SAT
            "check": "short description of this check",
            "detail": "detailed explanation of the finding and real-world implications.",
        }
    return {
        "kind": "SAT",
        "check": "short description",
        "detail": "no gap found — property is guaranteed by the axioms.",
    }
```

**kind values:**

| kind | when to use |
|------|-------------|
| `SAT` | check passed — no issue found |
| `GAP` | a required implication is missing (SAT when it should be UNSAT) |
| `AMBIGUITY` | a predicate is unconstrained / formally undefined |
| `UNSAT` | a contradiction found — requirements conflict |

---

## step 3 — register the check

Add your function to the `CHECKS` list and `CHECK_REQUIREMENT_MAP` dict near the
bottom of `skills/skill_03_smt_solver.py`:

```python
CHECKS = [
    check_01_global_consistency,
    check_02_authentication_gap,
    check_03_access_proofing_gap,
    check_04_sep_of_duties_ambiguity,
    check_05_physical_logical_boundary,
    check_06_full_access_chain,
    check_07_my_new_check,        # ← add here
]

CHECK_REQUIREMENT_MAP = {
    # ... existing entries ...
    check_07_my_new_check: "PR.AA-XX × PR.AA-YY",   # ← add scope label
}
```

---

## step 4 — verify

Run the solver standalone (uses `build_reference_model()`) to confirm your
check executes without error and produces the expected result:

```bash
source .venv/bin/activate
python skills/skill_03_smt_solver.py
```

Then run the full offline pipeline (uses `build_model()` with stub SMT-LIB2)
to confirm the summary counts are correct end-to-end:

```bash
python run.py --no-llm
```

---

## adding a new predicate

If your check requires a predicate that does not yet exist, declare it in
`build_model()` and add it to the returned dict:

```python
# inside build_model(), after existing declarations:
time_limited_access = Function("time_limited_access", Entity, Asset, BoolSort())

# add to the return dict:
return {
    # ... existing entries ...
    "time_limited_access": time_limited_access,
}
```

Then add it as a new axiom if the requirement implies it:

```python
ax_new = ForAll(
    [e, a],
    Implies(
        And(high_sensitivity_asset(a), has_access(e, a)),
        time_limited_access(e, a),
    ),
)
axioms = [ax_pr_aa_01, ax_pr_aa_02, ..., ax_new]
```

Always re-run Check 1 (global consistency) after adding an axiom to confirm the
requirement set remains satisfiable.
