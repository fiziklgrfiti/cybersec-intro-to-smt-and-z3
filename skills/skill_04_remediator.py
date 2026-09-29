"""
skills/skill_04_remediator.py — STAGE 4: Deep Feedback Loop / Remediation
──────────────────────────────────────────────────────────────────────────
Receives findings from Stage 3 and closes them by flowing backwards to
rewrite the implicated Stage 1 SHALL statements and re-formalise them in
Stage 2, then re-validates with Z3.  Each pass produces versioned output
files so progress is visible and every revision can be rolled back or
inspected independently.

Loop phases per pass
────────────────────
  4a  Identify which requirement IDs are implicated in each open finding,
      and look up the missing-axiom guidance from FINDING_REQUIREMENT_MAP
      and AXIOM_GUIDANCE_MAP.

  4b  Build a targeted rewrite prompt for each implicated requirement,
      carrying the specific missing-link instruction into Stage 1.

  4c  Re-run Stage 1 for the implicated requirements only (either via the
      Anthropic SDK if ANTHROPIC_API_KEY is set, or by writing a
      stage4_guidance.json handoff file for the OpenCode agent to action).
      Merge the updated SHALL statements back into the full stage1 array
      and write stage1_output.rN.json.

  4d  Re-run Stage 2 for the same requirements.  Merge and write
      stage2_output.rN.json.

  Validate  Re-run Stage 3 against the new rN files.  Compute and display
            the delta (resolved / still open / new issues).  Print the
            running progress scoreboard.

Fixes are never applied in-memory to the Z3 solver (extra_axioms is
reserved for diagnostic isolation tests only).  The durable artefacts —
stage1_output.rN.json and stage2_output.rN.json — are the source of truth.

Versioned file convention
──────────────────────────
  .opencode/pipeline/stage1_output.json       baseline (initial run)
  .opencode/pipeline/stage2_output.json       baseline
  .opencode/pipeline/stage1_output.r1.json    after pass 1
  .opencode/pipeline/stage2_output.r1.json
  .opencode/pipeline/stage1_output.r2.json    after pass 2
  ...
  .opencode/pipeline/stage4_patches.json      patch log (all passes)
  .opencode/pipeline/stage4_guidance.json     agent handoff file (no-key path)
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PIPELINE_DIR = os.path.join(_PROJECT_ROOT, ".opencode", "pipeline")

from utils.terminal import (
    c, BOLD, CYAN, DIM, YELLOW, GREEN, RED, MAGENTA, WHITE,
    print_stage, print_finding, print_patch_plan, rule,
)


# ── Finding kind constants ──────────────────────────────────────────────────────
KIND_GAP         = "GAP"
KIND_AMBIGUITY   = "AMBIGUITY"
KIND_SAT         = "SAT"
KIND_UNSAT       = "UNSAT"

PHASE_GAP_KINDS        = {KIND_GAP}
PHASE_AMBIGUITY_KINDS  = {KIND_AMBIGUITY}
ISSUE_KINDS            = {KIND_GAP, KIND_AMBIGUITY, KIND_UNSAT}


# ── GuidanceRequired sentinel ───────────────────────────────────────────────────
class GuidanceRequired(Exception):
    """
    Raised when ANTHROPIC_API_KEY is not set and the deep loop requires Stage 1/2
    to be re-run.  The guidance file has already been written to the pipeline
    directory.  run.py catches this and prints the agent handoff instructions.
    """
    def __init__(self, revision: int, guidance_path: str):
        self.revision      = revision
        self.guidance_path = guidance_path
        super().__init__(f"guidance file written to {guidance_path}")


# ── Finding → requirement mapping ──────────────────────────────────────────────
# Maps a substring of finding["check"] to the list of requirement IDs whose
# Stage 1 SHALL statements need to be rewritten to close the gap.
FINDING_REQUIREMENT_MAP: dict[str, list[str]] = {
    "Authentication ↛ Credential Management": ["PR.AA-01", "PR.AA-03"],
    "Access ↛ Identity Proofing":             ["PR.AA-02", "PR.AA-03"],
    "has_access ↛ credentials_managed":       ["PR.AA-01", "PR.AA-03"],
    "Separation of Duties — undefined":        ["PR.AA-05"],
    "Physical/Logical access boundary":        ["PR.AA-05", "PR.AA-06"],
}


# ── Missing-axiom guidance for Stage 1 rewrite prompts ─────────────────────────
# The human-readable guidance carried into the Stage 1 rewrite prompt so the
# LLM knows exactly which logical link is missing and must be introduced.
AXIOM_GUIDANCE_MAP: dict[str, str] = {
    "Authentication ↛ Credential Management": (
        "The current SHALL statements do not establish that every authenticated "
        "entity must have managed credentials.  Add a SHALL statement that requires: "
        "any entity that is authenticated MUST have credentials that appear in the "
        "organisation's credential inventory (is_authenticated → has_credentials).  "
        "This closes the gap where hardware tokens or service accounts can authenticate "
        "without being registered in credential management."
    ),
    "Access ↛ Identity Proofing": (
        "The current SHALL statements do not guarantee that an entity with access "
        "has had its identity proofed.  The chain is broken because authentication "
        "does not imply credential possession, so PR.AA-02's proofing guarantee never "
        "triggers.  Add a SHALL statement that requires: any entity that is authenticated "
        "MUST hold credentials (is_authenticated → has_credentials), which — combined "
        "with PR.AA-02 — closes the full chain to identity proofing."
    ),
    "has_access ↛ credentials_managed": (
        "The current SHALL statements do not ensure that an entity with access to any "
        "asset has credentials that are actively managed.  Add a SHALL statement that "
        "requires: any entity granted access to an asset MUST hold credentials "
        "(has_access → has_credentials), making credential management a pre-condition "
        "for access rather than a separate obligation."
    ),
    "Separation of Duties — undefined": (
        "The current model asserts sep_of_duties_applied but never defines what it "
        "means in terms of concrete duty conflicts — the conflict register is empty by "
        "default, so SoD is vacuously satisfied.  To resolve this: (1) declare the "
        "Duty sort in your SMT-LIB2, (2) use duty_of(Entity, Asset, Duty) to record "
        "which duties each entity holds over each asset, (3) use "
        "conflicts_with(Duty, Duty) to register which duty pairs are incompatible, "
        "and (4) add a forall axiom defining sep_of_duties_applied(e, a) as requiring "
        "the existence of two distinct entities holding conflicting duties over a.  "
        "This makes the conflict register non-vacuous and closes the Check 4 ambiguity."
    ),
    "Physical/Logical access boundary": (
        "The current SHALL statements are ambiguous about whether access policy "
        "obligations (PR.AA-05) apply to physical assets as well as logical ones.  "
        "Add a SHALL statement that explicitly asserts: physical access to an asset "
        "MUST be governed by the same access policy and authorisation requirements "
        "as logical access (is_physical_asset ∧ has_access → access_in_policy).  "
        "This removes the implementation ambiguity that would allow physical access "
        "to bypass policy checks."
    ),
}


# ── Tier 1: rule-based fix catalogue (kept for display/plan purposes) ───────────
# Used by print_patch_plan to show what rewrite guidance will be applied.
# The actual fix mechanism is now Stage 1/2 rewriting, not in-memory axioms.
RULE_CATALOGUE: list[tuple] = [
    (
        "Authentication ↛ Credential Management",
        None,  # no factory — fix is via Stage 1 rewrite
        "rewrite PR.AA-01 + PR.AA-03: add SHALL linking is_authenticated → has_credentials",
        "stage1_rewrite",
    ),
    (
        "Access ↛ Identity Proofing",
        None,
        "rewrite PR.AA-02 + PR.AA-03: add SHALL closing chain to identity_proofed",
        "stage1_rewrite",
    ),
    (
        "Separation of Duties — undefined predicate",
        None,
        "rewrite PR.AA-05: add duty_of/conflicts_with axioms defining the SoD conflict register",
        "stage1_rewrite",
    ),
    (
        "Physical/Logical access boundary",
        None,
        "rewrite PR.AA-05 + PR.AA-06: add SHALL asserting physical access is in-policy",
        "stage1_rewrite",
    ),
    (
        "has_access ↛ credentials_managed",
        None,
        "rewrite PR.AA-01 + PR.AA-03: add SHALL linking has_access → has_credentials",
        "stage1_rewrite",
    ),
]


# ── 4a: identify implicated requirements ───────────────────────────────────────

def _identify_implicated(
    findings: list[dict],
    fix_ambiguities: bool,
) -> dict[str, list[dict]]:
    """
    Returns a dict mapping requirement ID → list of findings that implicate it.
    Only targets GAP findings (and AMBIGUITY findings when fix_ambiguities is True).
    """
    target_kinds = PHASE_GAP_KINDS | (PHASE_AMBIGUITY_KINDS if fix_ambiguities else set())
    req_map: dict[str, list[dict]] = {}

    for finding in findings:
        if finding["kind"] not in target_kinds:
            continue
        check_name = finding.get("check", "")
        for substr, req_ids in FINDING_REQUIREMENT_MAP.items():
            if substr in check_name:
                for req_id in req_ids:
                    req_map.setdefault(req_id, []).append(finding)
                break

    return req_map


# ── 4b: build targeted rewrite prompt ──────────────────────────────────────────

def _build_rewrite_guidance(
    req_id: str,
    findings: list[dict],
    current_shall: dict,
) -> str:
    """
    Builds the guidance text carried into the Stage 1 rewrite prompt for a
    specific requirement.  Combines the general rewrite instructions with the
    specific missing-axiom hints for every finding that implicates this requirement.
    """
    hints = []
    for finding in findings:
        check_name = finding.get("check", "")
        for substr, guidance in AXIOM_GUIDANCE_MAP.items():
            if substr in check_name:
                hints.append(guidance)
                break

    original_text = current_shall.get("original", "")
    existing_stmts = current_shall.get("rewritten", [])
    existing_text  = "\n".join(
        f"  {s['id']}: {s['statement']}" for s in existing_stmts
    )

    guidance = (
        f"You are refining the SHALL statements for requirement {req_id}.\n\n"
        f"Original requirement text:\n  {original_text}\n\n"
        f"Existing SHALL statements (do NOT remove or weaken these):\n{existing_text}\n\n"
        f"The following gaps or ambiguities have been identified in the current "
        f"formal model and must be closed by adding new or updated SHALL statements:\n\n"
    )
    for i, hint in enumerate(hints, 1):
        guidance += f"{i}. {hint}\n\n"

    guidance += (
        "Produce an updated list of SHALL statements for this requirement that "
        "closes all of the above gaps.  Keep all existing statements that are "
        "still correct.  Add new statements as needed.  Follow the same JSON "
        "schema as before (id, statement, subject, object, condition, "
        "testable_indicator).  Number new statements continuing from the last "
        "existing ID (e.g. if the last was PR.AA-01.5, next is PR.AA-01.6)."
    )
    return guidance


# ── 4c: run targeted Stage 1 rewrite ───────────────────────────────────────────

def _run_targeted_stage1(
    req_guidance: dict[str, str],
    current_stage1: list[dict],
    revision: int,
    api_key: str | None,
    verbose: bool,
) -> list[dict]:
    """
    Re-runs Stage 1 for the implicated requirements only.

    If ANTHROPIC_API_KEY is set, calls the Anthropic SDK directly.
    If not, writes stage4_guidance.json and raises GuidanceRequired.

    Returns the updated full stage1 list (all requirements, with implicated
    ones replaced by the rewritten versions).
    """
    if not api_key:
        _write_guidance_file(req_guidance, revision, stage=1)
        guidance_path = os.path.join(_PIPELINE_DIR, "stage4_guidance.json")
        raise GuidanceRequired(revision=revision, guidance_path=guidance_path)

    try:
        import anthropic
    except ImportError:
        print(c("  ERROR: anthropic package not installed.", BOLD))
        sys.exit(1)

    from skills.skill_01_rewriter import SYSTEM_PROMPT

    client   = anthropic.Anthropic(api_key=api_key)
    updated  = {r["id"]: r for r in current_stage1}

    for req_id, guidance_text in req_guidance.items():
        if verbose:
            print(c(f"    Rewriting Stage 1 for {req_id} …", DIM))

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": guidance_text}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]

        # The response should be a JSON array with one element for this req_id,
        # or a bare object.  Normalise to a list and take the first match.
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = [parsed]

        for item in parsed:
            if item.get("id") == req_id:
                updated[req_id] = item
                break
        else:
            # Fallback: LLM returned a list with no matching id.
            # Warn and use the first element rather than silently overwriting.
            if parsed:
                if len(parsed) > 1 and verbose:
                    print(c(f"    ⚠️  LLM returned {len(parsed)} entries for {req_id}; using first.", YELLOW))
                parsed[0]["id"] = req_id
                updated[req_id] = parsed[0]

    result = list(updated.values())
    _save_stage_output(result, stage=1, revision=revision)
    return result


# ── 4d: run targeted Stage 2 formalisation ─────────────────────────────────────

def _run_targeted_stage2(
    implicated_req_ids: list[str],
    current_stage2: list[dict],
    new_stage1: list[dict],
    revision: int,
    api_key: str | None,
    verbose: bool,
) -> list[dict]:
    """
    Re-runs Stage 2 for the implicated requirements only, using the updated
    Stage 1 output.  Merges results back into the full stage2 list and writes
    stage2_output.rN.json.

    Precondition: api_key is always set when this function is called from
    run_pass() — if it were absent, _run_targeted_stage1() would have already
    raised GuidanceRequired before reaching this point.  The api_key parameter
    is retained for clarity and defensive calling.
    """
    if not api_key:
        # Should not be reached in normal flow (stage1 raises first), but
        # guard defensively rather than fail with an opaque AttributeError.
        _write_guidance_file(
            {req_id: f"formalise updated Stage 1 output for {req_id}" for req_id in implicated_req_ids},
            revision,
            stage=2,
        )
        guidance_path = os.path.join(_PIPELINE_DIR, "stage4_guidance.json")
        raise GuidanceRequired(revision=revision, guidance_path=guidance_path)

    try:
        import anthropic
    except ImportError:
        print(c("  ERROR: anthropic package not installed.", BOLD))
        sys.exit(1)

    from skills.skill_02_formalizer import SYSTEM_PROMPT

    client  = anthropic.Anthropic(api_key=api_key)
    updated = {r["id"]: r for r in current_stage2}

    # Only the implicated requirements need re-formalisation
    implicated_stage1 = [r for r in new_stage1 if r["id"] in implicated_req_ids]

    for req in implicated_stage1:
        req_id = req["id"]
        if verbose:
            print(c(f"    Formalising Stage 2 for {req_id} …", DIM))

        user_prompt = (
            f"Formalise the following rewritten requirements from PR.AA.\n"
            f"Each entry already has precise SHALL statements — convert them to formal logic.\n\n"
            f"{json.dumps([req], indent=2)}"
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]

        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = [parsed]

        for item in parsed:
            if item.get("id") == req_id:
                updated[req_id] = item
                break
        else:
            if parsed:
                if len(parsed) > 1 and verbose:
                    print(c(f"    ⚠️  LLM returned {len(parsed)} entries for {req_id} (stage 2); using first.", YELLOW))
                parsed[0]["id"] = req_id
                updated[req_id] = parsed[0]

    result = list(updated.values())
    _save_stage_output(result, stage=2, revision=revision)
    return result


# ── File I/O helpers ────────────────────────────────────────────────────────────

def _save_stage_output(data: list[dict], stage: int, revision: int):
    """Write stage1_output.rN.json or stage2_output.rN.json."""
    os.makedirs(_PIPELINE_DIR, exist_ok=True)
    filename = f"stage{stage}_output.r{revision}.json"
    path = os.path.join(_PIPELINE_DIR, filename)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return path


def _write_guidance_file(req_guidance: dict[str, str], revision: int, stage: int):
    """
    Write stage4_guidance.json — the handoff file consumed by the OpenCode agent
    when ANTHROPIC_API_KEY is not set.  The agent reads this file, performs the
    targeted Stage 1/2 rewrite, writes the versioned output files, then resumes
    the pipeline with --from-files --revision N --remediate.
    """
    os.makedirs(_PIPELINE_DIR, exist_ok=True)
    path = os.path.join(_PIPELINE_DIR, "stage4_guidance.json")
    payload = {
        "revision": revision,
        "stage": stage,
        "instructions": (
            f"The Stage 4 feedback loop requires you to re-run Stage {stage} "
            f"for the following requirements, incorporating the guidance provided. "
            f"Write the result to "
            f".opencode/pipeline/stage{stage}_output.r{revision}.json "
            f"(merge with all other requirements from the current stage{stage} file). "
            f"Then run: python run.py --from-files --revision {revision} --remediate"
        ),
        "requirements": req_guidance,
        "resume_command": f"python run.py --from-files --revision {revision} --remediate",
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def _save_patch_log(patches: list[dict]):
    os.makedirs(_PIPELINE_DIR, exist_ok=True)
    path = os.path.join(_PIPELINE_DIR, "stage4_patches.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(patches, fh, indent=2, ensure_ascii=False)


# ── Core pass function ──────────────────────────────────────────────────────────

def run_pass(
    findings: list[dict],
    accumulated_patches: list[dict],
    pass_number: int,
    current_stage1: list[dict],
    current_stage2: list[dict],
    fix_ambiguities: bool = False,
    verbose: bool = True,
    selected_req_ids: list[str] | None = None,
) -> tuple[list[dict], list[dict], dict, list[dict], list[dict]]:
    """
    Runs one deep remediation pass (phases 4a–4d).

    Args:
        findings:             Current list of findings from Stage 3.
        accumulated_patches:  Patch log entries from all previous passes.
        pass_number:          1-based pass counter.
        current_stage1:       Full stage1 list (all requirements, current revision).
        current_stage2:       Full stage2 list (all requirements, current revision).
        fix_ambiguities:      If True, also target AMBIGUITY findings.
        verbose:              Print formatted output to terminal.
        selected_req_ids:     Requirement IDs in scope for this run.  Passed
                              through to the Stage 3 solver so check filtering
                              is consistent across baseline and remediation runs.

    Returns:
        (new_findings, new_patches, delta, new_stage1, new_stage2)

        delta = {
            "resolved":   list of check names resolved this pass,
            "new_issues": list of check names newly introduced this pass,
            "remaining":  list of check names still open after this pass,
        }

    Raises:
        GuidanceRequired: when ANTHROPIC_API_KEY is not set; the caller must
                          surface the handoff instructions and pause the loop.
    """
    from skills.skill_03_smt_solver import run as solve

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    target_kinds   = PHASE_GAP_KINDS | (PHASE_AMBIGUITY_KINDS if fix_ambiguities else set())
    open_findings  = [f for f in findings if f["kind"] in target_kinds]
    previously_open = {f["check"]: f["kind"] for f in findings if f["kind"] in ISSUE_KINDS}

    if not open_findings:
        if verbose:
            print(c("  No open findings to target.", DIM))
        return findings, accumulated_patches, {"resolved": [], "new_issues": [], "remaining": []}, current_stage1, current_stage2

    # ── 4a: identify implicated requirements ───────────────────────────────────
    req_to_findings = _identify_implicated(open_findings, fix_ambiguities)

    if verbose:
        label = "gaps + ambiguities" if fix_ambiguities else "gaps"
        print(c(f"  {len(open_findings)} open {label} implicate "
                f"{len(req_to_findings)} requirement(s): "
                f"{', '.join(sorted(req_to_findings.keys()))}", DIM))
        print()

    # ── Show pre-announcement plan ─────────────────────────────────────────────
    if verbose:
        print_patch_plan(open_findings, RULE_CATALOGUE)

    # ── 4b: build targeted guidance per requirement ────────────────────────────
    stage1_lookup = {r["id"]: r for r in current_stage1}
    req_guidance: dict[str, str] = {}
    for req_id, req_findings in req_to_findings.items():
        current_shall = stage1_lookup.get(req_id, {"id": req_id, "original": "", "rewritten": []})
        req_guidance[req_id] = _build_rewrite_guidance(req_id, req_findings, current_shall)

    # ── 4c: targeted Stage 1 rewrite ──────────────────────────────────────────
    if verbose:
        print(c(f"  Phase 4c — rewriting Stage 1 SHALL statements …", BOLD, CYAN))
        print()

    new_stage1 = _run_targeted_stage1(
        req_guidance=req_guidance,
        current_stage1=current_stage1,
        revision=pass_number,
        api_key=api_key,
        verbose=verbose,
    )

    if verbose:
        for req_id in sorted(req_to_findings.keys()):
            print(c(f"    ✔  stage1_output.r{pass_number}.json updated for {req_id}", GREEN))
        print()

    # ── 4d: targeted Stage 2 formalisation ────────────────────────────────────
    if verbose:
        print(c(f"  Phase 4d — re-formalising Stage 2 logic …", BOLD, CYAN))
        print()

    new_stage2 = _run_targeted_stage2(
        implicated_req_ids=list(req_to_findings.keys()),
        current_stage2=current_stage2,
        new_stage1=new_stage1,
        revision=pass_number,
        api_key=api_key,
        verbose=verbose,
    )

    if verbose:
        for req_id in sorted(req_to_findings.keys()):
            print(c(f"    ✔  stage2_output.r{pass_number}.json updated for {req_id}", GREEN))
        print()

    # ── Re-run Stage 3 against the new versioned files ─────────────────────────
    if verbose:
        print(rule("─"))
        print()
        print(c(f"  Validating — running Z3 against revision r{pass_number} …", BOLD, CYAN))
        print()

    # Build previous_findings dict for inline before/after annotations
    previous_findings_map = {f["check"]: f["kind"] for f in findings}

    new_findings = solve(
        formal=new_stage2,
        verbose=verbose,
        previous_findings=previous_findings_map,
        selected_req_ids=selected_req_ids,
    )

    # ── Compute delta ──────────────────────────────────────────────────────────
    new_open       = {f["check"] for f in new_findings if f["kind"] in ISSUE_KINDS}
    resolved       = sorted(previously_open.keys() - new_open)
    new_issues     = sorted(new_open - set(previously_open.keys()))
    remaining      = sorted(new_open)

    delta = {
        "resolved":   resolved,
        "new_issues": new_issues,
        "remaining":  remaining,
    }

    # ── Persist patch log ──────────────────────────────────────────────────────
    # Log one entry per (finding, requirement) pair.  When a finding implicates
    # multiple requirements, each is logged separately so the log reflects exactly
    # which requirement files were updated.  A finding is never logged twice for
    # the same requirement within the same pass.
    new_patch_entries = []
    seen_check_req: set[tuple[str, str]] = set()
    for req_id, req_findings in req_to_findings.items():
        for finding in req_findings:
            check_name = finding["check"]
            key = (check_name, req_id)
            if key in seen_check_req:
                continue
            seen_check_req.add(key)
            # Find matching guidance
            guidance_text = ""
            for substr, g in AXIOM_GUIDANCE_MAP.items():
                if substr in check_name:
                    guidance_text = g
                    break
            new_patch_entries.append({
                "pass":        pass_number,
                "check":       check_name,
                "kind":        finding["kind"],
                "fix_source":  "stage1_rewrite",
                "req_id":      req_id,
                "description": f"rewrote Stage 1 SHALL statements for {req_id}",
                "guidance":    guidance_text,
                "output_file": f"stage1_output.r{pass_number}.json",
            })

    all_patches = accumulated_patches + new_patch_entries
    _save_patch_log(all_patches)

    return new_findings, all_patches, delta, new_stage1, new_stage2


# ── Delta display ───────────────────────────────────────────────────────────────

def print_delta(delta: dict, pass_number: int):
    """Pretty-print the delta summary after a remediation pass."""
    print()
    print(c(f"  ── Pass {pass_number} delta ──────────────────────────────", BOLD, CYAN))
    resolved   = delta["resolved"]
    new_issues = delta["new_issues"]
    remaining  = delta["remaining"]

    if resolved:
        print(c(f"  ✅  Resolved this pass ({len(resolved)}):", BOLD, GREEN))
        for name in resolved:
            print(c(f"       • {name}", GREEN))
    else:
        print(c("  —   No new resolutions this pass.", DIM))

    if new_issues:
        print(c(f"  ❌  New issues introduced ({len(new_issues)}):", BOLD, RED))
        for name in new_issues:
            print(c(f"       • {name}", RED))

    if remaining:
        print(c(f"  ⚠️   Still open ({len(remaining)}):", YELLOW))
        for name in remaining:
            print(c(f"       • {name}", YELLOW))
    else:
        print(c("  ✅  No open issues remaining!", BOLD, GREEN))

    print()
