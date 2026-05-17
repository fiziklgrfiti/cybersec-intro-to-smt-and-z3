"""
run.py — Requirements Engine Orchestrator
──────────────────────────────────────────
Runs all four stages of the pipeline end-to-end:

  Stage 0 → Load NIST CSF 2.0 PR.AA requirements
  Stage 1 → LLM rewrites vague outcomes into testable criteria (Claude API)
  Stage 2 → Translates criteria into formal logic: pseudo-logic + SMT-LIB2 (Claude API)
  Stage 3 → Z3 SMT solver runs proofs and surfaces gaps, ambiguities, contradictions

Usage:
  python run.py              # Full pipeline
  python run.py --no-llm     # Skip API calls, run Z3 only (for offline demos)
"""

import os
import sys
import argparse

from data.requirements import NIST_PR_AA
from utils.terminal import (
    c, BOLD, CYAN, DIM, GREEN, YELLOW, WHITE,
    print_banner, print_stage, print_requirement_header,
    print_shall, print_smt_block, print_finding, print_summary, rule,
)


def stage_0_display(nist_data: dict):
    """Display the raw NIST requirements as loaded."""
    print_stage(0, "SOURCE REQUIREMENTS", "NIST CSF 2.0 — PR.AA as published")

    print(c(f"  Framework : {nist_data['framework']}", DIM))
    print(c(f"  Domain    : {nist_data['domain']}", DIM))
    print(c(f"  Category  : {nist_data['category_id']} — {nist_data['category_name']}", DIM))
    print()
    print(c(f"  {nist_data['category_description']}", WHITE))
    print()
    print(rule("·", width=60))
    print()

    for req in nist_data["requirements"]:
        print(c(f"  {req['id']}", BOLD, YELLOW) + c(f"  {req['text']}", WHITE))
    print()


def stage_1_rewrite(nist_data: dict) -> list[dict]:
    """Call skill_01 to rewrite requirements with the LLM."""
    print_stage(
        1,
        "LLM REQUIREMENT REWRITING",
        "Claude translates vague outcomes into precise, testable SHALL statements",
    )

    from skills.skill_01_rewriter import run as rewrite
    rewritten = rewrite(nist_data, verbose=True)
    print(c(f"  ✓ {len(rewritten)} requirements rewritten.", BOLD, GREEN))
    return rewritten


def stage_2_formalize(rewritten: list[dict], nist_data: dict) -> list[dict]:
    """Call skill_02 to generate formal logic representations."""
    print_stage(
        2,
        "FORMAL REPRESENTATION",
        "Claude generates pseudo-logic (∀ →) and SMT-LIB2 for each requirement",
    )

    from skills.skill_02_formalizer import run as formalize
    formal = formalize(rewritten, nist_data, verbose=True)
    print(c(f"  ✓ {len(formal)} requirements formalised.", BOLD, GREEN))
    return formal


def stage_3_solve(formal: list[dict]) -> list[dict]:
    """Call skill_03 to run Z3 proofs."""
    print_stage(
        3,
        "SMT SOLVING  (Z3)",
        "Automated reasoning: consistency, gaps, ambiguities, implication chains",
    )

    from skills.skill_03_smt_solver import run as solve
    findings = solve(formal=formal, verbose=True)
    return findings


def stage_1_offline(nist_data: dict) -> list[dict]:
    """Stub rewritten requirements for offline (no-LLM) mode."""
    print_stage(1, "LLM REQUIREMENT REWRITING", "[OFFLINE MODE — using stub data]")
    stub = []
    for req in nist_data["requirements"]:
        stub.append({
            "id": req["id"],
            "original": req["text"],
            "rewritten": [
                {
                    "id": req["id"] + ".1",
                    "statement": f"The organization SHALL ensure: {req['text']}",
                    "subject": "Organization",
                    "object": "Identity/Access assets",
                    "condition": "At all times",
                    "testable_indicator": "Audit log / policy document review",
                }
            ],
        })
        print(c(f"  {req['id']}", BOLD, YELLOW) + c(f"  {req['text']}", DIM))
    print()
    print(c("  ⚠️  Offline mode: LLM rewriting skipped. Using stub SHALL statements.", YELLOW))
    print()
    return stub


def stage_2_offline(rewritten: list[dict], nist_data: dict) -> list[dict]:
    """Stub formal output for offline mode."""
    print_stage(2, "FORMAL REPRESENTATION", "[OFFLINE MODE — using stub data]")
    stub = []
    for req in rewritten:
        stub.append({
            "id": req["id"],
            "pseudo_logic": f"∀ e ∈ Entity: requirement_{req['id'].replace('-','_').lower()}(e)",
            "smt_lib2": (
                f"; {req['id']} — stub\n"
                f"(declare-sort Entity 0)\n"
                f"(declare-fun req_{req['id'].replace('-','_').lower()} (Entity) Bool)\n"
                f"(assert (forall ((e Entity)) (req_{req['id'].replace('-','_').lower()} e)))"
            ),
            "sorts_used": ["Entity"],
            "predicates_used": [f"req_{req['id'].replace('-','_').lower()}"],
        })
        print(c(f"  {req['id']}", BOLD, YELLOW) + c("  [stub formal output]", DIM))
    print()
    print(c("  ⚠️  Offline mode: LLM formalisation skipped. Using stub SMT-LIB2.", YELLOW))
    print()
    return stub


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Requirements Engine — NIST CSF 2.0 PR.AA pipeline"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip Claude API calls (stages 1 & 2). Run Z3 solver only.",
    )
    args = parser.parse_args()

    if not args.no_llm and not os.environ.get("ANTHROPIC_API_KEY"):
        print()
        print(c("  ERROR: ANTHROPIC_API_KEY is not set.", BOLD))
        print(c("  Export it before running, or use --no-llm for offline Z3 demo.", DIM))
        print()
        print(c("  export ANTHROPIC_API_KEY=sk-ant-...", DIM))
        print()
        sys.exit(1)

    print_banner()

    # Stage 0 — display source requirements
    stage_0_display(NIST_PR_AA)

    # Stages 1 & 2 — LLM pipeline (or stubs)
    if args.no_llm:
        rewritten = stage_1_offline(NIST_PR_AA)
        formal    = stage_2_offline(rewritten, NIST_PR_AA)
    else:
        rewritten = stage_1_rewrite(NIST_PR_AA)
        formal    = stage_2_formalize(rewritten, NIST_PR_AA)

    # Stage 3 — Z3 SMT solving (always runs)
    findings = stage_3_solve(formal)

    # Summary
    print_summary(findings)


if __name__ == "__main__":
    main()
