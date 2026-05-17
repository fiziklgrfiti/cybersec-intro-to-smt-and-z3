"""
skills/skill_02_formalizer.py — STAGE 2: Formal Representation
───────────────────────────────────────────────────────────────
Translates rewritten testable criteria (from skill_01) into two
parallel formal representations:

  (a) Pseudo-logic  — human-readable mathematical notation  (∀, →, ∧, ¬)
  (b) SMT-LIB2      — standard syntax consumed by Z3 and other SMT solvers

Can be run standalone (calls skill_01 first automatically):
    python skills/skill_02_formalizer.py
"""

import os
import sys
import json
import anthropic

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

    if verbose:
        _print_results(rewritten, formal)

    return formal


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
