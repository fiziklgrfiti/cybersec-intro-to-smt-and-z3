"""
skills/skill_02_formalizer.py — STAGE 2: Formal Representation
───────────────────────────────────────────────────────────────
Translates rewritten testable criteria (from skill_01) into two
parallel formal representations:

  (a) Pseudo-logic  — human-readable mathematical notation  (∀, →, ∧, ¬)
  (b) SMT-LIB2      — standard syntax consumed by Z3 and other SMT solvers

Can be run standalone (calls skill_01 first automatically):
    python skills/skill_02_formalizer.py

Output is also written to .opencode/pipeline/stage2_output.json so that
an OpenCode agent run can produce it without a direct API call, and
run.py --from-files can consume it.
"""

import os
import sys
import json
import anthropic

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Project root resolved from this file's location — used by _save_output()
# so that writing to .opencode/pipeline/ is CWD-independent.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from utils.terminal import (
    c, BOLD, CYAN, DIM, YELLOW, GREEN, WHITE,
    print_stage, print_requirement_header, print_smt_block, rule,
)

# ── Prompt ─────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a formal methods engineer specialising in translating
cybersecurity requirements into mathematical logic for automated reasoning.

Given a list of rewritten SHALL statements for a single requirement, produce TWO
formal representations:

1. PSEUDO_LOGIC — human-readable mathematical notation using:
     ∀  (for all),  ∃  (there exists),  →  (implies),  ∧  (and),  ∨  (or),  ¬  (not)
   Keep sorts and predicates named clearly so a non-expert can follow.
   Example: ∀ e ∈ Entity: has_credentials(e) → credentials_managed(e)

2. SMT_LIB2 — valid SMT-LIB2 syntax that Z3 can parse, using:
   - (declare-sort ...) for new types
   - (declare-fun ...) for predicates
   - (assert (forall ...)) for universal statements
   Use only the predicates needed for THIS requirement.
   Do NOT add (check-sat) or (get-model) — the solver harness does that.

You MUST respond with a JSON array. Each element has this exact shape:
{
  "id": "PR.AA-XX",
  "pseudo_logic": "<multi-line pseudo-logic string>",
  "smt_lib2": "<multi-line SMT-LIB2 string>",
  "sorts_used": ["Entity", "Asset", ...],
  "predicates_used": ["has_credentials", ...]
}

CANONICAL VOCABULARY — you MUST use only these sort and predicate names.
Introduce a new name only when no existing predicate covers the concept,
following the same snake_case convention and the exact type signatures shown.
Any name you introduce must not clash with an existing one.

Sorts:
  Entity   — users, services, and hardware
  Asset    — physical or logical resources
  Duty     — a discrete, named action or role that can conflict with another duty

Predicates (Entity → Bool):
  has_credentials, credentials_managed, identity_proofed, identity_bound,
  is_authenticated, assertion_protected, assertion_verified

Predicates (Entity × Asset → Bool):
  has_access, access_authorized, access_in_policy, least_privilege_applied,
  sep_of_duties_applied, access_reviewed, physical_access_monitored

Predicates (Entity × Asset × Duty → Bool):
  duty_of        — entity e holds duty d over asset a

Predicates (Duty × Duty → Bool):
  conflicts_with — duties d1 and d2 are designated as conflicting

Predicates (Asset → Bool):
  is_physical_asset, risk_assessed

For PR.AA-05 specifically: sep_of_duties_applied(e, a) MUST be given a definitional
axiom in terms of duty_of and conflicts_with.  It is not sufficient to merely assert
sep_of_duties_applied — you must add a forall axiom of the form:
  ∀ (e: Entity) (a: Asset): sep_of_duties_applied(e, a) →
    ∃ (d1: Duty) (d2: Duty) (e2: Entity):
      duty_of(e, a, d1) ∧ duty_of(e2, a, d2) ∧ conflicts_with(d1, d2) ∧ e ≠ e2

In SMT-LIB2 this looks like:
  (assert (forall ((e Entity) (a Asset))
    (=> (sep_of_duties_applied e a)
        (exists ((d1 Duty) (d2 Duty) (e2 Entity))
          (and (duty_of e a d1)
               (duty_of e2 a d2)
               (conflicts_with d1 d2)
               (not (= e e2)))))))

This makes the conflict register non-vacuous and allows Check 4 to resolve.

Return ONLY valid JSON. No markdown fences. No commentary."""


USER_PROMPT_TEMPLATE = """Formalise the following rewritten requirements from {category_id}.
Each entry already has precise SHALL statements — convert them to formal logic.

{rewritten_json}
"""


# ── Core function ──────────────────────────────────────────────────────────────
def run(rewritten: list[dict], nist_data: dict, verbose: bool = True) -> list[dict]:
    """
    Calls Claude API to generate formal representations for each requirement.

    Args:
        rewritten:  Output from skill_01_rewriter.run()
        nist_data:  Original NIST data dict (used for category_id label)
        verbose:    If True, prints formatted output to terminal

    Returns:
        List of formal representation dicts
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(c("  ERROR: ANTHROPIC_API_KEY environment variable not set.", BOLD))
        print(c("  To run without an API key, use the OpenCode 'run-pipeline' skill", DIM))
        print(c("  (OpenCode handles the LLM call) then run:  python run.py --from-files", DIM))
        print(c("  Or run offline:  python run.py --no-llm", DIM))
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Send the full rewritten list; Claude formalises all at once for consistency
    # (shared sorts/predicates must be named consistently across requirements)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        category_id=nist_data["category_id"],
        rewritten_json=json.dumps(rewritten, indent=2),
    )

    if verbose:
        print(c("  Calling Claude API (claude-sonnet-4-20250514) …", DIM))

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]

    formal = json.loads(raw)

    _save_output(formal)

    if verbose:
        _print_results(rewritten, formal)

    return formal


def _save_output(formal: list[dict]):
    """Persist stage 2 output to .opencode/pipeline/ for --from-files consumption.

    Uses _PROJECT_ROOT (resolved from this file's location) so that the output
    path is correct regardless of the current working directory.
    """
    out_dir = os.path.join(_PROJECT_ROOT, ".opencode", "pipeline")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "stage2_output.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(formal, fh, indent=2, ensure_ascii=False)


def _print_results(rewritten: list[dict], formal: list[dict]):
    """Display pseudo-logic and SMT-LIB2 side by side for each requirement."""
    # Build lookup from rewritten for original text
    orig_lookup = {r["id"]: r.get("original", "") for r in rewritten}

    for f in formal:
        req_id = f["id"]
        print_requirement_header(req_id, orig_lookup.get(req_id, ""))

        # Pseudo-logic block
        print_smt_block(
            "Pseudo-Logic  (∀ ∃ → ∧ ¬)",
            f.get("pseudo_logic", ""),
            color="\033[36m",  # CYAN
        )

        # SMT-LIB2 block
        print_smt_block(
            "SMT-LIB2  (Z3-compatible)",
            f.get("smt_lib2", ""),
            color="\033[33m",  # YELLOW
        )

        # Inventory of sorts & predicates
        sorts = ", ".join(f.get("sorts_used", []))
        preds = ", ".join(f.get("predicates_used", []))
        if sorts:
            print(c(f"    Sorts     : {sorts}", DIM))
        if preds:
            print(c(f"    Predicates: {preds}", DIM))
        print()


# ── Standalone entry point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    from data.requirements import NIST_PR_AA
    from skills.skill_01_rewriter import run as rewrite

    print_stage(1, "LLM REQUIREMENT REWRITING", "(prerequisite — running now)")
    rewritten = rewrite(NIST_PR_AA, verbose=False)
    print(c(f"  ✓ Rewriting complete for {len(rewritten)} requirements.", DIM))
    print()

    print_stage(2, "FORMAL REPRESENTATION",
                "Generating pseudo-logic (∀ →) and SMT-LIB2 for each requirement")
    results = run(rewritten, NIST_PR_AA)
    print(rule("─"))
    print(c(f"  ✓ Formalised {len(results)} requirements.", BOLD, GREEN))
