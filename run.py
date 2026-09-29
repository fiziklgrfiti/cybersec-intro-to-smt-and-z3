"""
run.py — Requirements Engine Orchestrator
──────────────────────────────────────────
Runs all four stages of the pipeline end-to-end:

  Stage 0 → Load NIST CSF 2.0 PR.AA requirements
  Stage 1 → LLM rewrites vague outcomes into testable criteria
  Stage 2 → Translates criteria into formal logic: pseudo-logic + SMT-LIB2
  Stage 3 → Z3 SMT solver runs proofs and surfaces gaps, ambiguities, contradictions
  Stage 4 → Deep feedback loop: rewrite implicated Stage 1/2 artefacts, re-validate (opt-in)

Usage:
  python run.py                         # Full pipeline — requires ANTHROPIC_API_KEY
  python run.py --from-files            # Load stage 1 & 2 output from .opencode/pipeline/
                                        # (produced by an OpenCode agent run — no API key needed)
  python run.py --no-llm                # Skip LLM stages entirely, run Z3 only (offline demo)
  python run.py --from-files --remediate           # Run Stage 4 deep feedback loop
  python run.py --no-llm --remediate               # Stage 4 in offline mode (LLM rewrite skipped)
  python run.py --from-files --remediate --max-passes 3  # Cap at 3 passes, no prompts
  python run.py --from-files --revision 2          # Load stage1_output.r2.json / stage2_output.r2.json
  python run.py --from-files --revision 2 --remediate   # Continue remediating from revision 2
"""

import os
import sys
import json
import argparse
import glob as _glob

from data.requirements import NIST_PR_AA
from utils.terminal import (
    c, BOLD, CYAN, DIM, GREEN, YELLOW, WHITE,
    print_banner, print_stage, print_requirement_header,
    print_shall, print_smt_block, print_finding, print_summary,
    print_scoreboard, rule,
)

_PIPELINE_DIR = os.path.join(".opencode", "pipeline")


# ── Revision helpers ───────────────────────────────────────────────────────────

def _latest_revision() -> int:
    """
    Scans .opencode/pipeline/ for the highest rN suffix present across
    stage1_output.rN.json files.  Returns 0 if no versioned files exist
    (meaning the baseline is the most recent revision).
    """
    pattern = os.path.join(_PIPELINE_DIR, "stage1_output.r*.json")
    matches = _glob.glob(pattern)
    if not matches:
        return 0
    revisions = []
    for path in matches:
        basename = os.path.basename(path)
        # basename: stage1_output.rN.json
        try:
            n = int(basename.replace("stage1_output.r", "").replace(".json", ""))
            revisions.append(n)
        except ValueError:
            pass
    return max(revisions) if revisions else 0


def _stage_file(stage: int, revision: int) -> str:
    """Return the pipeline file path for the given stage and revision."""
    if revision == 0:
        return os.path.join(_PIPELINE_DIR, f"stage{stage}_output.json")
    return os.path.join(_PIPELINE_DIR, f"stage{stage}_output.r{revision}.json")


def _scoreboard_entry(label: str, findings: list[dict]) -> dict:
    counts: dict[str, int] = {"SAT": 0, "GAP": 0, "AMBIGUITY": 0, "UNSAT": 0}
    for f in findings:
        k = f.get("kind", "")
        if k in counts:
            counts[k] += 1
    return {"label": label, **counts}


# ── Stage functions ────────────────────────────────────────────────────────────

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


def stage_3_solve(
    formal: list[dict],
    previous_findings: dict | None = None,
    selected_req_ids: list[str] | None = None,
) -> list[dict]:
    """Call skill_03 to run Z3 proofs."""
    print_stage(
        3,
        "SMT SOLVING  (Z3)",
        "Automated reasoning: consistency, gaps, ambiguities, implication chains",
    )

    from skills.skill_03_smt_solver import run as solve
    findings = solve(
        formal=formal,
        verbose=True,
        previous_findings=previous_findings,
        selected_req_ids=selected_req_ids,
    )
    return findings


def _load_stage_file(stage: int, revision: int) -> list[dict]:
    """Load and parse a stage output file; exit with a clear message if missing."""
    path = _stage_file(stage, revision)
    stage_titles = {
        1: "LLM REQUIREMENT REWRITING",
        2: "FORMAL REPRESENTATION",
    }
    title = stage_titles.get(stage, f"STAGE {stage}")
    rev_label = f"r{revision}" if revision > 0 else "baseline"
    if not os.path.exists(path):
        print()
        print(c(f"  ERROR: {path} not found.", BOLD))
        if revision > 0:
            print(c(f"  Revision r{revision} has not been produced yet.", DIM))
            print(c(f"  Available revisions: baseline (0)"
                    + (f", r1–r{_latest_revision()}" if _latest_revision() > 0 else ""), DIM))
        else:
            print(c("  Run the OpenCode 'run-pipeline' skill to generate it, or use --no-llm.", DIM))
        print()
        sys.exit(1)
    print_stage(stage, title, f"[FROM FILES — loading {path}  ({rev_label})]")
    with open(path, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            print(c(f"  ERROR: {path} is not valid JSON: {exc}", BOLD))
            sys.exit(1)
    print(c(f"  ✓ Loaded {len(data)} entries from {path}.", BOLD, GREEN))
    return data


def stage_1_offline(nist_data: dict) -> list[dict]:
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
    """Stub formal output for offline mode — uses canonical predicate names."""
    print_stage(2, "FORMAL REPRESENTATION", "[OFFLINE MODE — using stub data]")
    stub = []
    for req in rewritten:
        req_id = req["id"]
        stub.append({
            "id": req_id,
            "pseudo_logic": f"∀ e ∈ Entity: has_credentials(e) → credentials_managed(e)  ; {req_id} stub",
            "smt_lib2": (
                f"; {req_id} — offline stub using canonical predicates\n"
                f"(declare-sort Entity 0)\n"
                f"(declare-sort Asset 0)\n"
                f"(declare-fun has_credentials (Entity) Bool)\n"
                f"(declare-fun credentials_managed (Entity) Bool)\n"
                f"(assert (forall ((e Entity))\n"
                f"  (=> (has_credentials e) (credentials_managed e))))"
            ),
            "sorts_used": ["Entity", "Asset"],
            "predicates_used": ["has_credentials", "credentials_managed"],
        })
        print(c(f"  {req_id}", BOLD, YELLOW) + c("  [stub formal output]", DIM))
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
        help="Skip LLM stages (1 & 2). Run Z3 solver only using stub data.",
    )
    parser.add_argument(
        "--from-files",
        action="store_true",
        help=(
            "Load stage 1 & 2 output from .opencode/pipeline/ instead of calling "
            "an LLM API. Use this after running the OpenCode 'run-pipeline' skill."
        ),
    )
    parser.add_argument(
        "--revision",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Load stage1_output.rN.json / stage2_output.rN.json instead of the "
            "baseline files.  Use 0 for the baseline.  When omitted with "
            "--remediate, defaults to the latest revision present."
        ),
    )
    parser.add_argument(
        "--remediate",
        action="store_true",
        help=(
            "Run Stage 4 deep feedback loop after Stage 3.  "
            "Rewrites implicated Stage 1 SHALL statements and Stage 2 formal logic, "
            "then re-validates with Z3.  Produces versioned output files (rN). "
            "By default, prompts the user after each pass (user-confirmed mode). "
            "Use --max-passes to run non-interactively."
        ),
    )
    parser.add_argument(
        "--max-passes",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Maximum number of Stage 4 remediation passes. "
            "When set, the loop runs up to N passes without user prompts. "
            "Without --max-passes, the loop is user-confirmed after each pass."
        ),
    )
    parser.add_argument(
        "--requirements",
        nargs="+",
        metavar="ID",
        default=None,
        help=(
            "Requirement IDs to analyse (e.g. PR.AA-01 PR.AA-03). "
            "Defaults to all requirement IDs present in the loaded Stage 1 file. "
            "Only Z3 checks whose required scope is a subset of this list are run."
        ),
    )
    args = parser.parse_args()

    # Resolve starting revision
    if args.revision is not None:
        start_revision = args.revision
    elif args.from_files and args.remediate:
        start_revision = _latest_revision()
    else:
        start_revision = 0

    # Pre-flight: ANTHROPIC_API_KEY only required for the direct API path
    if not args.no_llm and not args.from_files and not os.environ.get("ANTHROPIC_API_KEY"):
        print()
        print(c("  ERROR: ANTHROPIC_API_KEY is not set.", BOLD))
        print(c("  Options:", DIM))
        print(c("    1. Export the key for direct API access:", DIM))
        print(c("         export ANTHROPIC_API_KEY=sk-ant-...", DIM))
        print(c("    2. Use the OpenCode 'run-pipeline' skill (no key required),", DIM))
        print(c("       then run:  python run.py --from-files", DIM))
        print(c("    3. Run offline (Z3 only, stub LLM data):", DIM))
        print(c("         python run.py --no-llm", DIM))
        print()
        sys.exit(1)

    # Warn if --revision is passed without --from-files (it will be ignored)
    if args.revision is not None and not args.from_files:
        print()
        print(c("  WARNING: --revision has no effect without --from-files.", YELLOW))
        print(c("  Re-run with --from-files --revision N to load a specific revision.", DIM))
        print()

    print_banner()

    # Stage 0 — display source requirements
    stage_0_display(NIST_PR_AA)

    # Stages 1 & 2 — LLM pipeline, pre-computed files, or stubs
    if args.no_llm:
        rewritten = stage_1_offline(NIST_PR_AA)
        formal    = stage_2_offline(rewritten, NIST_PR_AA)
    elif args.from_files:
        rewritten = _load_stage_file(1, start_revision)
        formal    = _load_stage_file(2, start_revision)
    else:
        rewritten = stage_1_rewrite(NIST_PR_AA)
        formal    = stage_2_formalize(rewritten, NIST_PR_AA)

    # Stage 3 — Z3 SMT solving (always runs)
    # Derive selected_req_ids from --requirements flag or from loaded Stage 1 IDs
    if args.requirements:
        selected_req_ids = args.requirements
    else:
        selected_req_ids = [r["id"] for r in rewritten]

    findings = stage_3_solve(formal, selected_req_ids=selected_req_ids)

    # Summary
    print_summary(findings)

    # Stage 4 — deep feedback loop (opt-in via --remediate)
    if args.remediate:
        stage_4_remediate(
            findings=findings,
            stage1=rewritten,
            stage2=formal,
            start_revision=start_revision,
            max_passes=args.max_passes,
            no_llm=args.no_llm,
            selected_req_ids=selected_req_ids,
        )
    else:
        # Hint: offer remediation if there are open issues
        open_issues = [f for f in findings if f.get("kind") in {"GAP", "AMBIGUITY", "UNSAT"}]
        if open_issues:
            print(c(f"  ℹ️   {len(open_issues)} finding(s) can be addressed by the Stage 4 feedback loop.", CYAN))
            print(c("       Re-run with --remediate to rewrite the implicated requirements and re-validate.", DIM))
            print()


def stage_4_remediate(
    findings: list[dict],
    stage1: list[dict],
    stage2: list[dict],
    start_revision: int,
    max_passes: int | None,
    no_llm: bool = False,
    selected_req_ids: list[str] | None = None,
):
    """
    Runs the Stage 4 deep remediation feedback loop.

    Each pass:
      - Identifies which requirements are implicated in open findings
      - Rewrites their Stage 1 SHALL statements with explicit gap-closing guidance
      - Re-formalises them in Stage 2
      - Re-runs Z3 and shows inline before/after annotations per check
      - Prints a running progress scoreboard

    Terminates when: no issues remain, --max-passes reached, no progress, or
    the user declines to continue (interactive mode).
    """
    from skills.skill_04_remediator import (
        run_pass, print_delta, ISSUE_KINDS, PHASE_GAP_KINDS,
        PHASE_AMBIGUITY_KINDS, GuidanceRequired,
    )

    if no_llm:
        print(c("\n  ⚠️  Stage 4 deep loop requires LLM access for Stage 1/2 rewrites.", YELLOW))
        print(c("     Offline mode (--no-llm) cannot produce updated requirements.", YELLOW))
        print(c("     Run without --no-llm, or set ANTHROPIC_API_KEY.", DIM))
        print()
        return

    interactive = max_passes is None

    accumulated_patches: list[dict] = []
    current_findings  = findings
    current_stage1    = stage1
    current_stage2    = stage2
    pass_number       = start_revision
    fix_ambiguities   = False

    # Scoreboard — seed with the baseline (revision 0 or the starting revision)
    baseline_label = "Baseline" if start_revision == 0 else f"r{start_revision}"
    scoreboard_history = [_scoreboard_entry(baseline_label, findings)]

    while True:
        pass_number += 1

        # Enforce max_passes cap (relative to start_revision)
        passes_done = pass_number - start_revision
        if max_passes is not None and passes_done > max_passes:
            print(c(f"\n  Max passes ({max_passes}) reached — stopping remediation loop.", YELLOW))
            break

        open_issues      = [f for f in current_findings if f["kind"] in ISSUE_KINDS]
        open_gaps        = [f for f in current_findings if f["kind"] in PHASE_GAP_KINDS]
        open_ambiguities = [f for f in current_findings if f["kind"] in PHASE_AMBIGUITY_KINDS]

        if not open_issues:
            print(c("\n  ✅  All issues resolved — exiting remediation loop.", BOLD, GREEN))
            break

        # After gaps are closed, decide whether to move into ambiguities
        if not open_gaps and open_ambiguities and not fix_ambiguities:
            if interactive:
                print()
                print(c("  No gaps remain. Ambiguities still open:", BOLD, YELLOW))
                for f in open_ambiguities:
                    print(c(f"    🔍  {f['check']}", YELLOW))
                print()
                answer = input(c("  Continue into ambiguity fixes? [y/n]: ", BOLD)).strip().lower()
                if answer != "y":
                    print(c("  Stopping remediation loop.", DIM))
                    break
                fix_ambiguities = True
            else:
                fix_ambiguities = True

        print_stage(
            4,
            f"REMEDIATION  — revision r{pass_number}",
            ("gaps + ambiguities" if fix_ambiguities else "gaps only")
            + "  |  rewriting Stage 1/2 artefacts and re-validating with Z3",
        )

        try:
            current_findings, accumulated_patches, delta, current_stage1, current_stage2 = run_pass(
                findings=current_findings,
                accumulated_patches=accumulated_patches,
                pass_number=pass_number,
                current_stage1=current_stage1,
                current_stage2=current_stage2,
                fix_ambiguities=fix_ambiguities,
                verbose=True,
                selected_req_ids=selected_req_ids,
            )
        except GuidanceRequired as exc:
            # No API key — agent handoff path
            print()
            print(c("  ── Agent handoff required ──────────────────────────────────────", BOLD, YELLOW))
            print(c(f"  ANTHROPIC_API_KEY is not set.  Stage 1/2 rewrite cannot run automatically.", YELLOW))
            print(c(f"  A guidance file has been written to:", DIM))
            print(c(f"    {exc.guidance_path}", CYAN))
            print()
            print(c("  To complete this pass:", BOLD))
            print(c("  1. Read .opencode/pipeline/stage4_guidance.json", DIM))
            print(c(f"  2. Rewrite the listed requirements' SHALL statements per the guidance", DIM))
            print(c(f"  3. Write the result to .opencode/pipeline/stage1_output.r{exc.revision}.json", DIM))
            print(c(f"  4. Re-formalise and write .opencode/pipeline/stage2_output.r{exc.revision}.json", DIM))
            print(c(f"  5. Resume with:", DIM))
            print(c(f"       python run.py --from-files --revision {exc.revision} --remediate", CYAN))
            print()
            break

        print_delta(delta, pass_number)
        print_summary(current_findings)

        # Update and print scoreboard
        scoreboard_history.append(_scoreboard_entry(f"r{pass_number}", current_findings))
        print_scoreboard(scoreboard_history)

        # Check termination conditions
        still_open = [f for f in current_findings if f["kind"] in ISSUE_KINDS]
        if not still_open:
            print(c("  ✅  All issues resolved.", BOLD, GREEN))
            break

        if not delta["resolved"] and not delta["new_issues"]:
            print(c("  —  No progress made this pass — stopping to avoid infinite loop.", YELLOW))
            print(c("     The remaining findings may require manual sub-requirement authoring.", DIM))
            break

        if interactive:
            print()
            answer = input(c("  Run another remediation pass? [y/n]: ", BOLD)).strip().lower()
            if answer != "y":
                print(c("  Stopping remediation loop.", DIM))
                break


if __name__ == "__main__":
    main()
