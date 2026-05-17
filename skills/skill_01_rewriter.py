"""
skills/skill_01_rewriter.py — STAGE 1: LLM Requirement Rewriting
─────────────────────────────────────────────────────────────────
Transforms vague NIST natural-language outcomes into precise,
testable SHALL statements using the Anthropic Claude API.

Can be run standalone:
    python skills/skill_01_rewriter.py
"""

import os
import sys
import json
import anthropic

# ── Allow standalone execution from project root ─────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.terminal import (
    c, BOLD, CYAN, DIM, YELLOW, MAGENTA, BLUE, GREEN,
    print_stage, print_requirement_header, print_shall, rule,
)

# ── Prompt ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a cybersecurity requirements engineer specialising in translating
vague, natural-language control requirements into precise, testable criteria.

For EACH requirement you receive, produce a structured list of SHALL statements that:
  1. Are unambiguous — no undefined terms, no passive voice without a subject
  2. Are atomic — one condition per statement
  3. Identify the SUBJECT  (who or what must comply)
  4. Identify the OBJECT   (what resource or asset is being controlled)
  5. State the CONDITION   (when, how, or under what circumstances)
  6. Include a TESTABLE INDICATOR (observable evidence that the statement is met)

You MUST respond with a JSON array. Each element has this exact shape:
{
  "id": "PR.AA-XX",
  "original": "<the original requirement text>",
  "rewritten": [
    {
      "id": "PR.AA-XX.1",
      "statement": "The organization SHALL ...",
      "subject": "...",
      "object": "...",
      "condition": "...",
      "testable_indicator": "..."
    }
  ]
}

Return ONLY valid JSON. No markdown fences. No commentary."""


USER_PROMPT_TEMPLATE = """Rewrite the following NIST CSF 2.0 requirements from category {category_id} into
precise, testable SHALL statements.

Requirements:
{requirements_json}
"""


# ── Core function ─────────────────────────────────────────────────────────────
def run(nist_data: dict, verbose: bool = True) -> list[dict]:
    """
    Calls Claude API to rewrite each requirement into testable criteria.

    Args:
        nist_data: The NIST_PR_AA dict from data/requirements.py
        verbose:   If True, prints formatted output to terminal

    Returns:
        List of rewritten requirement dicts
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(c("  ERROR: ANTHROPIC_API_KEY environment variable not set.", BOLD))
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Build a compact list of {id, text} for the prompt
    req_list = [{"id": r["id"], "text": r["text"]} for r in nist_data["requirements"]]

    user_prompt = USER_PROMPT_TEMPLATE.format(
        category_id=nist_data["category_id"],
        requirements_json=json.dumps(req_list, indent=2),
    )

    if verbose:
        print(c("  Calling Claude API (claude-sonnet-4-20250514) …", DIM))

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown fences if Claude added them despite instructions
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]

    rewritten = json.loads(raw)

    if verbose:
        _print_results(nist_data, rewritten)

    return rewritten


def _print_results(nist_data: dict, rewritten: list[dict]):
    """Pretty-print rewritten requirements to terminal."""
    category_line = (
        f"  {c(nist_data['category_id'], BOLD, YELLOW)}  "
        f"{nist_data['category_name']}"
    )
    print(category_line)
    print(c(f"  {nist_data['category_description']}", DIM))
    print()

    for req in rewritten:
        print_requirement_header(req["id"], req["original"])

        print(c("    Rewritten as testable SHALL statements:", BOLD, CYAN))
        print()
        print_shall(req["rewritten"])


# ── Standalone entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    from data.requirements import NIST_PR_AA

    print_stage(1, "LLM REQUIREMENT REWRITING",
                "Translating vague NIST outcomes into precise testable criteria")
    results = run(NIST_PR_AA)
    print(rule("─"))
    print(c(f"  ✓ Processed {len(results)} requirements.", BOLD, GREEN))
