"""
skills/skill_03_smt_solver.py — STAGE 3: SMT Solving with Z3
──────────────────────────────────────────────────────────────
Runs automated reasoning proofs against a formal model of the
selected NIST requirements using the Z3 SMT solver (Python API).

Two model-building paths:

  build_model(formal)
      Production path.  Parses the SMT-LIB2 strings produced by
      skill_02_formalizer and constructs Z3 axioms from them.
      Used by run.py --from-files and the Stage 4 feedback loop.
      Gaps that are properly closed in the Stage 1/2 artefacts are
      confirmed closed by Z3 in the same pass.

  build_reference_model()
      Regression/standalone path.  Hard-coded axioms mirroring the
      six NIST PR.AA requirements as published.  Used only when this
      file is executed directly (python skills/skill_03_smt_solver.py)
      so the solver can be exercised in isolation without pipeline
      artefacts.  Not used in any end-to-end or production run.

Checks are scoped to the selected requirements:

  CHECK_REQUIREMENT_MAP maps each check function to the frozenset of
  requirement IDs that must all be in scope for the check to run.
  run() accepts selected_req_ids and filters accordingly.

  check_00_requirement_consistency always runs regardless of scope —
  it tests internal consistency of the axioms derived from whatever
  requirements the user selected.

Can be run standalone (uses build_reference_model, all checks):
    python skills/skill_03_smt_solver.py
"""

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.terminal import (
    c, BOLD, CYAN, DIM, YELLOW, GREEN, RED, WHITE,
    print_stage, print_finding, print_smt_block, rule,
)

try:
    from z3 import (
        DeclareSort, Function, BoolSort, Const, ForAll, Implies,
        And, Not, Solver, sat, unsat, parse_smt2_string,
    )
except ImportError:
    print("z3-solver not installed. Run:  pip install z3-solver")
    sys.exit(1)


# ── Canonical sorts ────────────────────────────────────────────────────────────
# Declared once at module level so every model-building path and every check
# function shares the same Z3 sort objects.  Z3 treats each DeclareSort("X")
# call as a new distinct sort, so module-level constants are required for
# unification across axiom sets.
Entity = DeclareSort("Entity")
Asset  = DeclareSort("Asset")
Duty   = DeclareSort("Duty")


# ── Canonical predicate declarations ──────────────────────────────────────────
# These mirror the vocabulary enforced by skill_02_formalizer.py's SYSTEM_PROMPT.
# Declared once at module level and reused by both model-building paths so that
# check functions always hold references to the same Z3 function objects,
# regardless of which path built the axioms.

# Entity → Bool
has_credentials          = Function("has_credentials",          Entity, BoolSort())
credentials_managed      = Function("credentials_managed",      Entity, BoolSort())
identity_proofed         = Function("identity_proofed",         Entity, BoolSort())
identity_bound           = Function("identity_bound",           Entity, BoolSort())
is_authenticated         = Function("is_authenticated",         Entity, BoolSort())
assertion_protected      = Function("assertion_protected",      Entity, BoolSort())
assertion_verified       = Function("assertion_verified",       Entity, BoolSort())

# Entity × Asset → Bool
has_access               = Function("has_access",               Entity, Asset, BoolSort())
access_authorized        = Function("access_authorized",        Entity, Asset, BoolSort())
access_in_policy         = Function("access_in_policy",         Entity, Asset, BoolSort())
least_privilege_applied  = Function("least_privilege_applied",  Entity, Asset, BoolSort())
sep_of_duties_applied    = Function("sep_of_duties_applied",    Entity, Asset, BoolSort())
access_reviewed          = Function("access_reviewed",          Entity, Asset, BoolSort())
physical_access_monitored = Function("physical_access_monitored", Entity, Asset, BoolSort())

# Asset → Bool
is_physical_asset        = Function("is_physical_asset",        Asset,  BoolSort())
risk_assessed            = Function("risk_assessed",            Asset,  BoolSort())

# Duty sort — supports concrete SoD modelling.  Uninterpreted in the baseline
# reference model (no conflict pairs declared), which intentionally preserves
# the Check 4 ambiguity signal until an agent-produced model registers duties.
#
# Entity × Asset × Duty → Bool
duty_of        = Function("duty_of",        Entity, Asset, Duty, BoolSort())

# Duty × Duty → Bool
conflicts_with = Function("conflicts_with", Duty,   Duty,        BoolSort())

# Quantifier variables — shared across all checks
_e = Const("e", Entity)
_a = Const("a", Asset)
_d = Const("d", Duty)

# The canonical model dict shape returned by both build_* functions.
# Check functions receive this dict and reference predicates by key.
_CANONICAL_MODEL_KEYS = {
    "Entity": Entity, "Asset": Asset, "Duty": Duty, "e": _e, "a": _a, "d": _d,
    "has_credentials": has_credentials,
    "credentials_managed": credentials_managed,
    "identity_proofed": identity_proofed,
    "identity_bound": identity_bound,
    "is_authenticated": is_authenticated,
    "assertion_protected": assertion_protected,
    "assertion_verified": assertion_verified,
    "has_access": has_access,
    "access_authorized": access_authorized,
    "access_in_policy": access_in_policy,
    "least_privilege_applied": least_privilege_applied,
    "sep_of_duties_applied": sep_of_duties_applied,
    "access_reviewed": access_reviewed,
    "is_physical_asset": is_physical_asset,
    "physical_access_monitored": physical_access_monitored,
    "risk_assessed": risk_assessed,
    "duty_of": duty_of,
    "conflicts_with": conflicts_with,
}


# ── Production model: dynamic from Stage 2 SMT-LIB2 output ────────────────────

def build_model(
    formal: list[dict],
    extra_axioms: list[Any] | None = None,
) -> dict:
    """
    Production path.  Builds the Z3 domain model by parsing the SMT-LIB2
    strings produced by skill_02_formalizer for each selected requirement.

    Each requirement's smt_lib2 field is parsed with z3.parse_smt2_string(),
    which returns a list of Z3 assertion objects.  These become the axioms
    the solver reasons over.

    Because the canonical sorts (Entity, Asset) and predicate functions are
    declared at module level, Z3 unifies them with any same-named declarations
    inside the parsed SMT-LIB2 strings — so check functions can reference
    predicates by their module-level Python variables as usual.

    Args:
        formal:       Stage 2 output list — one dict per requirement, each
                      containing at minimum an "id" and "smt_lib2" field.
        extra_axioms: Optional additional Z3 expressions to layer on top
                      (additive only — existing axioms are never mutated).

    Returns:
        Model dict with the same shape as build_reference_model().
    """
    axioms: list[Any] = []

    for entry in formal:
        req_id  = entry.get("id", "unknown")
        smt_src = entry.get("smt_lib2", "").strip()
        if not smt_src:
            if True:  # always warn — empty SMT-LIB2 is unexpected
                print(c(f"  ⚠️  {req_id}: smt_lib2 is empty — no axioms loaded for this requirement.", YELLOW))
            continue
        try:
            parsed = parse_smt2_string(smt_src)
            axioms.extend(parsed)
        except Exception as exc:  # noqa: BLE001
            print(c(f"  ⚠️  {req_id}: failed to parse SMT-LIB2 ({exc}). "
                    "Skipping axioms for this requirement.", YELLOW))

    if extra_axioms:
        axioms = axioms + list(extra_axioms)

    return {**_CANONICAL_MODEL_KEYS, "axioms": axioms}


# ── Regression/standalone model: hard-coded PR.AA axioms ──────────────────────

def build_reference_model(extra_axioms: list[Any] | None = None) -> dict:
    """
    Regression/standalone path.  Hard-codes the six NIST PR.AA requirement
    axioms directly in Python.  Used only when this module is executed
    standalone (python skills/skill_03_smt_solver.py) so the solver can be
    exercised without pipeline artefacts.

    This model is intentionally designed to surface the known gaps (Checks 2,
    3, 6) and ambiguities (Checks 4, 5) for educational purposes.  It is NOT
    used in any end-to-end or production run — build_model() is used there.

    Args:
        extra_axioms: Optional additional Z3 expressions (additive only).

    Returns:
        Model dict with the same shape as build_model().
    """
    e, a = _e, _a

    # PR.AA-01: all entities with credentials have those credentials managed
    ax_pr_aa_01 = ForAll(
        [e],
        Implies(has_credentials(e), credentials_managed(e)),
    )

    # PR.AA-02: credentials imply identity was proofed AND bound
    ax_pr_aa_02 = ForAll(
        [e],
        Implies(
            has_credentials(e),
            And(identity_proofed(e), identity_bound(e)),
        ),
    )

    # PR.AA-03: access to any asset requires authentication
    ax_pr_aa_03 = ForAll(
        [e, a],
        Implies(has_access(e, a), is_authenticated(e)),
    )

    # PR.AA-04: authentication requires assertions are protected AND verified
    ax_pr_aa_04 = ForAll(
        [e],
        Implies(
            is_authenticated(e),
            And(assertion_protected(e), assertion_verified(e)),
        ),
    )

    # PR.AA-05: access requires policy, authorisation, least privilege, SoD, review
    ax_pr_aa_05 = ForAll(
        [e, a],
        Implies(
            has_access(e, a),
            And(
                access_in_policy(e, a),
                access_authorized(e, a),
                least_privilege_applied(e, a),
                sep_of_duties_applied(e, a),
                access_reviewed(e, a),
            ),
        ),
    )

    # PR.AA-06: physical asset access is monitored and the asset's risk is assessed
    ax_pr_aa_06 = ForAll(
        [e, a],
        Implies(
            And(is_physical_asset(a), has_access(e, a)),
            And(physical_access_monitored(e, a), risk_assessed(a)),
        ),
    )

    axioms: list[Any] = [
        ax_pr_aa_01, ax_pr_aa_02, ax_pr_aa_03,
        ax_pr_aa_04, ax_pr_aa_05, ax_pr_aa_06,
    ]

    if extra_axioms:
        axioms = axioms + list(extra_axioms)

    return {**_CANONICAL_MODEL_KEYS, "axioms": axioms}


# ── Checks ─────────────────────────────────────────────────────────────────────

def _solver_with_axioms(axioms) -> Solver:
    s = Solver()
    if axioms:
        s.add(*axioms)
    return s


def check_00_requirement_consistency(m: dict, req_ids: list[str]) -> dict:
    """
    CHECK 0 — Internal consistency of selected requirement(s).
    Always runs regardless of scope.

    Are the axioms derived from the selected requirement(s) simultaneously
    satisfiable?  Expected: SAT — no requirement should contradict itself.

    If UNSAT, the SHALL statements produced by Stage 1 and formalised in
    Stage 2 contain a logical contradiction.  This is a critical finding
    requiring the Stage 1 rewriting to be revised.
    """
    label = ", ".join(sorted(req_ids))
    s = _solver_with_axioms(m["axioms"])
    result = s.check()
    if result == sat:
        return {
            "kind": "SAT",
            "check": f"Internal consistency ({label})",
            "detail": (
                f"The axioms derived from {label} are satisfiable — "
                "no self-contradiction exists within the selected requirement(s)."
            ),
        }
    return {
        "kind": "UNSAT",
        "check": f"Internal consistency ({label})",
        "detail": (
            f"CRITICAL: the axioms for {label} are mutually contradictory. "
            "No system could satisfy all SHALL statements simultaneously. "
            "Review the Stage 1 rewriting for logical conflicts."
        ),
    }


def check_01_global_consistency(m: dict) -> dict:
    """
    CHECK 1 — Global consistency across all selected requirements.
    Are all selected requirement axioms simultaneously satisfiable?
    Expected: SAT (they should not contradict each other).
    """
    s = _solver_with_axioms(m["axioms"])
    result = s.check()
    if result == sat:
        return {
            "kind": "SAT",
            "check": "Global Consistency (all selected requirements together)",
            "detail": "All selected requirement axioms are simultaneously satisfiable — "
                      "no internal contradiction exists across the set.",
        }
    return {
        "kind": "UNSAT",
        "check": "Global Consistency (all selected requirements together)",
        "detail": f"UNEXPECTED: selected requirements are mutually inconsistent. Z3 result: {result}",
    }


def check_02_authentication_credential_gap(m: dict) -> dict:
    """
    CHECK 2 — Gap: Authentication ↛ Credential Management
    Can an entity be authenticated WITHOUT having managed credentials?

    PR.AA-03 requires authentication for access.
    PR.AA-01 requires credential management.
    The gap: neither requirement links them — no axiom asserts
    is_authenticated(e) → has_credentials(e).

    Expected: SAT (gap exists — closed only when the linking axiom is present)
    """
    e = m["e"]
    s = _solver_with_axioms(m["axioms"])
    s.add(m["is_authenticated"](e))
    s.add(Not(m["has_credentials"](e)))
    result = s.check()
    if result == sat:
        return {
            "kind": "GAP",
            "check": "PR.AA-03 + PR.AA-01: Authentication ↛ Credential Management",
            "detail": "A satisfying model exists where an entity is authenticated\n"
                      "yet has no entry in the organisation's credential inventory.\n"
                      "Missing axiom: is_authenticated(e) → has_credentials(e)\n"
                      "Risk: hardware tokens or service accounts may bypass PR.AA-01.",
        }
    return {
        "kind": "SAT",
        "check": "PR.AA-03 + PR.AA-01: Authentication → Credential Management",
        "detail": "Authentication implies credential management (no gap).",
    }


def check_03_access_to_identity_proofing_chain(m: dict) -> dict:
    """
    CHECK 3 — Gap: Access ↛ Identity Proofing
    Does has_access(e, a) guarantee identity_proofed(e)?

    Chain as written:  has_access → is_authenticated       (PR.AA-03)
                       has_credentials → identity_proofed  (PR.AA-02)
    Missing link:      is_authenticated → has_credentials  (no requirement asserts this)

    Expected: SAT (gap — chain is broken; closed when the linking axiom is present)
    """
    e, a = m["e"], m["a"]
    s = _solver_with_axioms(m["axioms"])
    s.add(m["has_access"](e, a))
    s.add(Not(m["identity_proofed"](e)))
    result = s.check()
    if result == sat:
        return {
            "kind": "GAP",
            "check": "PR.AA-03 + PR.AA-02: Access ↛ Identity Proofing",
            "detail": "has_access(e) does NOT imply identity_proofed(e).\n"
                      "PR.AA-03 links access to authentication.\n"
                      "PR.AA-02 links credentials to proofing.\n"
                      "But no requirement links authentication to credentials.\n"
                      "The proofing guarantee is broken for entities without explicit credentials.",
        }
    return {
        "kind": "SAT",
        "check": "PR.AA-03 + PR.AA-02: Access → Identity Proofing chain is complete.",
        "detail": "No gap found.",
    }


def check_04_separation_of_duties(m: dict) -> dict:
    """
    CHECK 4 — Ambiguity: Separation of Duties has no registered conflict pairs.

    Asks: given has_access(e, a), can the conflicts_with register be entirely
    empty?  In the baseline reference model it can (SAT → AMBIGUITY), because
    no duty pairs are declared and sep_of_duties_applied is vacuously asserted.

    Once an agent-produced model adds a definitional axiom linking
    sep_of_duties_applied to duty_of/conflicts_with (i.e. access requires at
    least one registered conflict pair), the combined assertion becomes
    contradictory (UNSAT → resolved).

    Expected outcome progression:
      baseline / no Duty axioms  →  SAT    (AMBIGUITY)
      with duty_of/conflicts_with definitional axiom  →  UNSAT  (resolved)
    """
    e, a = m["e"], m["a"]
    d1   = Const("d1", m["Duty"])
    d2   = Const("d2", m["Duty"])
    s    = _solver_with_axioms(m["axioms"])
    s.add(m["has_access"](e, a))
    s.add(ForAll([d1, d2], Not(m["conflicts_with"](d1, d2))))
    result = s.check()
    if result == sat:
        return {
            "kind": "AMBIGUITY",
            "check": "PR.AA-05: Separation of Duties — undefined predicate",
            "detail": "The conflicts_with register can be empty even when access is granted.\n"
                      "No duty pairs have been formally defined — sep_of_duties_applied is vacuous.\n"
                      "The requirement states SoD must be incorporated but never defines:\n"
                      "  • What constitutes a 'duty'\n"
                      "  • Which duty combinations conflict\n"
                      "  • That at least one conflict pair must exist for any guarded access\n"
                      "Recommendation: add duty_of/conflicts_with axioms defining the conflict register.",
        }
    return {
        "kind": "UNSAT",
        "check": "PR.AA-05: Separation of Duties",
        "detail": "Conflict register is required — the model cannot satisfy has_access "
                  "without at least one conflicts_with pair.  SoD ambiguity resolved.",
    }


def check_05_physical_logical_access_boundary(m: dict) -> dict:
    """
    CHECK 5 — Ambiguity: Physical/Logical access boundary between PR.AA-05 and PR.AA-06.
    PR.AA-05 requires access_in_policy for all has_access.
    PR.AA-06 addresses physical access separately.

    In a unified model (has_access covers both), PR.AA-05 applies to physical assets
    and the check returns UNSAT.  But implementations that split has_access into
    separate logical/physical predicates will create a gap.

    Expected: UNSAT in a unified model (which surfaces the ambiguity)
    """
    e, a = m["e"], m["a"]
    s = _solver_with_axioms(m["axioms"])
    s.add(m["is_physical_asset"](a))
    s.add(m["has_access"](e, a))
    s.add(Not(m["access_in_policy"](e, a)))
    result = s.check()
    if result == unsat:
        return {
            "kind": "AMBIGUITY",
            "check": "PR.AA-05 vs PR.AA-06: Physical/Logical access boundary",
            "detail": "In this model, has_access covers both physical and logical,\n"
                      "so PR.AA-05 policy requirement applies to physical assets.\n"
                      "HOWEVER: the natural language of PR.AA-05 mentions 'permissions\n"
                      "and entitlements' (logical) while PR.AA-06 covers 'physical access'\n"
                      "separately. Implementations that model these as DISTINCT predicates\n"
                      "will create a gap where physical access bypasses policy checks.\n"
                      "Recommendation: explicitly state whether PR.AA-05 scope includes physical.",
        }
    return {
        "kind": "GAP",
        "check": "PR.AA-05 vs PR.AA-06: Physical access may bypass policy",
        "detail": "Physical access is possible without access_in_policy.",
    }


def check_06_full_access_guarantee_chain(m: dict) -> dict:
    """
    CHECK 6 — Implication chain: what does has_access truly guarantee?

    Traces the complete chain from has_access(e, a):
      → is_authenticated          (PR.AA-03)
      → assertion_protected/verified (PR.AA-04)
      → access_in_policy, access_authorized, least_privilege,
        sep_of_duties, access_reviewed  (PR.AA-05)
      → physical_access_monitored, risk_assessed  (PR.AA-06, if physical)

    Tests whether has_access → credentials_managed.
    Expected: SAT (gap — closed when the full chain is bridged)
    """
    e, a = m["e"], m["a"]
    s = _solver_with_axioms(m["axioms"])
    s.add(m["has_access"](e, a))
    s.add(Not(m["credentials_managed"](e)))
    result = s.check()
    if result == sat:
        return {
            "kind": "GAP",
            "check": "Full access guarantee chain: has_access ↛ credentials_managed",
            "detail": "CHAIN ANALYSIS — has_access guarantees:\n"
                      "  ✅  is_authenticated          (via PR.AA-03)\n"
                      "  ✅  assertion_protected       (via PR.AA-04)\n"
                      "  ✅  assertion_verified        (via PR.AA-04)\n"
                      "  ✅  access_in_policy          (via PR.AA-05)\n"
                      "  ✅  access_authorized         (via PR.AA-05)\n"
                      "  ✅  least_privilege_applied   (via PR.AA-05)\n"
                      "  ✅  sep_of_duties_applied     (via PR.AA-05 — but undefined, see Check 4)\n"
                      "  ⚠️   has_credentials          NOT guaranteed (missing link)\n"
                      "  ⚠️   credentials_managed      NOT guaranteed (missing link)\n"
                      "  ⚠️   identity_proofed         NOT guaranteed (broken chain)\n"
                      "The credential and proofing guarantees are DETACHED from the access chain.",
        }
    return {
        "kind": "SAT",
        "check": "Full access guarantee chain: has_access → credentials_managed",
        "detail": "has_access implies credentials_managed — the full chain is intact.",
    }


# ── Check registry ─────────────────────────────────────────────────────────────

CHECKS = [
    check_01_global_consistency,
    check_02_authentication_credential_gap,
    check_03_access_to_identity_proofing_chain,
    check_04_separation_of_duties,
    check_05_physical_logical_access_boundary,
    check_06_full_access_guarantee_chain,
]

# Maps each check to the frozenset of requirement IDs that must ALL be in
# scope for the check to run.  A check is skipped when any of its required
# requirement IDs are not in the selected set.
CHECK_REQUIREMENT_MAP: dict = {
    check_01_global_consistency:                frozenset({"PR.AA-01", "PR.AA-02", "PR.AA-03", "PR.AA-04", "PR.AA-05", "PR.AA-06"}),
    check_02_authentication_credential_gap:     frozenset({"PR.AA-01", "PR.AA-03"}),
    check_03_access_to_identity_proofing_chain: frozenset({"PR.AA-02", "PR.AA-03"}),
    check_04_separation_of_duties:              frozenset({"PR.AA-05"}),
    check_05_physical_logical_access_boundary:  frozenset({"PR.AA-05", "PR.AA-06"}),
    check_06_full_access_guarantee_chain:       frozenset({"PR.AA-01", "PR.AA-02", "PR.AA-03", "PR.AA-04", "PR.AA-05", "PR.AA-06"}),
}

# Human-readable scope labels used for terminal display only.
CHECK_DISPLAY_LABEL: dict = {
    check_01_global_consistency:                "PR.AA-01 – PR.AA-06",
    check_02_authentication_credential_gap:     "PR.AA-01 × PR.AA-03",
    check_03_access_to_identity_proofing_chain: "PR.AA-02 × PR.AA-03",
    check_04_separation_of_duties:              "PR.AA-05",
    check_05_physical_logical_access_boundary:  "PR.AA-05 × PR.AA-06",
    check_06_full_access_guarantee_chain:       "PR.AA-01 – PR.AA-06",
}


# ── Orchestrator ───────────────────────────────────────────────────────────────

def run(
    formal: list[dict] | None = None,
    verbose: bool = True,
    extra_axioms: list[Any] | None = None,
    previous_findings: dict[str, str] | None = None,
    selected_req_ids: list[str] | None = None,
) -> list[dict]:
    """
    Runs Z3 checks against the domain model for the selected requirements.

    Args:
        formal:            Stage 2 output list.  When provided, the model is
                           built dynamically from the SMT-LIB2 strings
                           (production path).  When None, build_reference_model()
                           is used (standalone/regression path).
        verbose:           If True, prints formatted output to terminal.
        extra_axioms:      Optional additional Z3 expressions (additive only).
        previous_findings: Optional dict mapping check name → prior kind string.
                           When supplied, each result is annotated with a
                           before/after indicator so the audience can track
                           which checks changed across remediation passes.
        selected_req_ids:  List of requirement IDs selected by the user (e.g.
                           ["PR.AA-01"]).  Only checks whose required scope is
                           a subset of this list are run.  When None, all
                           checks run (backwards-compatible default).

    Returns:
        List of finding dicts  {kind, check, detail}.
        check_00 (internal consistency) is always the first entry.
    """
    # Build the domain model
    if formal is not None:
        model = build_model(formal, extra_axioms=extra_axioms)
    else:
        model = build_reference_model(extra_axioms=extra_axioms)

    # Determine the effective selected set for check filtering
    if selected_req_ids is not None:
        selected = frozenset(selected_req_ids)
    else:
        # Default: treat all known requirement IDs as selected (run all checks)
        selected = frozenset().union(*CHECK_REQUIREMENT_MAP.values())

    if verbose and formal:
        _print_smt_lib2_reference(formal)

    findings: list[dict] = []

    # Check 0 — always runs; label uses the selected IDs
    req_ids_for_label = sorted(selected_req_ids) if selected_req_ids else sorted(selected)
    finding_0 = check_00_requirement_consistency(model, req_ids_for_label)
    findings.append(finding_0)
    if verbose:
        print(c(f"  Check 0  ·  scope: {', '.join(req_ids_for_label)}", DIM))
        prior_kind = (
            previous_findings.get(finding_0["check"])
            if previous_findings else None
        )
        print_finding(
            finding_0["kind"],
            finding_0["check"],
            finding_0.get("detail", ""),
            previous_kind=prior_kind,
        )

    # Checks 1–N — filtered to those whose scope ⊆ selected
    skipped = 0
    for i, check_fn in enumerate(CHECKS, 1):
        required_scope = CHECK_REQUIREMENT_MAP.get(check_fn, frozenset())
        if not required_scope.issubset(selected):
            skipped += 1
            continue

        finding = check_fn(model)
        findings.append(finding)

        if verbose:
            label = CHECK_DISPLAY_LABEL.get(check_fn, "")
            print(c(f"  Check {i}  ·  scope: {label}", DIM))
            prior_kind = (
                previous_findings.get(finding["check"])
                if previous_findings else None
            )
            print_finding(
                finding["kind"],
                finding["check"],
                finding.get("detail", ""),
                previous_kind=prior_kind,
            )

    if verbose and skipped:
        print(c(
            f"  {skipped} check(s) skipped — their required requirements are not all in scope.\n"
            f"  To run them, include the additional requirement IDs with --requirements.",
            DIM,
        ))
        print()

    return findings


def _print_smt_lib2_reference(formal: list[dict]):
    """Display a condensed SMT-LIB2 reference so the audience can see the
    connection between the Stage 2 formal output and the Z3 axioms."""
    print(c("  SMT-LIB2 from Stage 2 (parsed by Z3 to build the domain model):", BOLD))
    print()
    for f in formal[:2]:  # show first two to keep output digestible
        label = f"{f['id']} SMT-LIB2 snippet"
        snippet_lines = f.get("smt_lib2", "").strip().split("\n")[:8]
        snippet = "\n".join(snippet_lines)
        if len(f.get("smt_lib2", "").strip().split("\n")) > 8:
            snippet += "\n  … (truncated)"
        print_smt_block(label, snippet, color="\033[33m")
    print(c("  Full SMT-LIB2 for all requirements available from Stage 2 output.", DIM))
    print()
    print(rule("─"))
    print()
    print(c("  Running Z3 checks …", DIM))
    print()


# ── Standalone entry point — uses build_reference_model() ─────────────────────
if __name__ == "__main__":
    from utils.terminal import print_summary

    print_stage(
        3,
        "SMT SOLVING  (Z3)  [standalone / regression mode]",
        "Using build_reference_model() — hard-coded PR.AA axioms, all checks",
    )
    # Pass formal=None so run() falls back to build_reference_model()
    # and selected_req_ids=None so all checks run.
    findings = run(formal=None, verbose=True, selected_req_ids=None)
    print_summary(findings)
