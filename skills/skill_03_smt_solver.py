"""
skills/skill_03_smt_solver.py — STAGE 3: SMT Solving with Z3
──────────────────────────────────────────────────────────────
Runs automated reasoning proofs against a formal model of the
NIST PR.AA requirements using the Z3 SMT solver (Python API).

The model encodes six requirement axioms and runs six targeted
checks designed to surface:
  • Global consistency   (are the requirements contradictory?)
  • Gaps                 (missing links between requirements)
  • Ambiguities          (undefined or unconstrained terms)
  • Implication chains   (what does "access" truly guarantee?)

NOTE: The formal model here is intentionally crafted to produce
educational findings. The SMT-LIB2 output from skill_02 is
displayed for learning; the Z3 Python API runs the actual proofs.

Can be run standalone:
    python skills/skill_03_smt_solver.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.terminal import (
    c, BOLD, CYAN, DIM, YELLOW, GREEN, RED, MAGENTA, WHITE,
    print_stage, print_finding, print_smt_block, rule,
)

try:
    from z3 import (
        DeclareSort, Function, BoolSort, Const, ForAll, Implies,
        And, Or, Not, Solver, sat, unsat, unknown,
    )
except ImportError:
    print("z3-solver not installed. Run:  pip install z3-solver")
    sys.exit(1)


# ── Domain model ───────────────────────────────────────────────────────────────
def build_model():
    """
    Declares sorts, predicates, and requirement axioms for the PR.AA domain.
    Returns a dict of all Z3 objects for use in checks.
    """
    # ── Sorts ──────────────────────────────────────────────────────────────────
    # Entity covers users, services, and hardware (PR.AA-01, -02, -03)
    Entity = DeclareSort("Entity")
    Asset  = DeclareSort("Asset")

    # ── Predicates (uninterpreted functions → Bool) ────────────────────────────
    # Credential & identity (PR.AA-01, -02)
    has_credentials          = Function("has_credentials",          Entity, BoolSort())
    credentials_managed      = Function("credentials_managed",      Entity, BoolSort())
    identity_proofed         = Function("identity_proofed",         Entity, BoolSort())
    identity_bound           = Function("identity_bound",           Entity, BoolSort())
    # Authentication (PR.AA-03)
    is_authenticated         = Function("is_authenticated",         Entity, BoolSort())
    # Identity assertions (PR.AA-04)
    assertion_protected      = Function("assertion_protected",      Entity, BoolSort())
    assertion_verified       = Function("assertion_verified",       Entity, BoolSort())
    # Access control (PR.AA-05)
    has_access               = Function("has_access",               Entity, Asset, BoolSort())
    access_authorized        = Function("access_authorized",        Entity, Asset, BoolSort())
    access_in_policy         = Function("access_in_policy",         Entity, Asset, BoolSort())
    least_privilege_applied  = Function("least_privilege_applied",  Entity, Asset, BoolSort())
    sep_of_duties_applied    = Function("sep_of_duties_applied",    Entity, Asset, BoolSort())
    access_reviewed          = Function("access_reviewed",          Entity, Asset, BoolSort())
    # Physical access (PR.AA-06)
    is_physical_asset        = Function("is_physical_asset",        Asset,  BoolSort())
    physical_access_monitored = Function("physical_access_monitored", Entity, Asset, BoolSort())
    risk_assessed            = Function("risk_assessed",            Asset,  BoolSort())

    # ── Quantifier variables ───────────────────────────────────────────────────
    e = Const("e", Entity)
    a = Const("a", Asset)

    # ── Requirement axioms ─────────────────────────────────────────────────────
    # PR.AA-01: All entities with credentials have those credentials managed
    ax_pr_aa_01 = ForAll(
        [e],
        Implies(has_credentials(e), credentials_managed(e)),
    )

    # PR.AA-02: Credentials imply identity was proofed AND bound
    ax_pr_aa_02 = ForAll(
        [e],
        Implies(
            has_credentials(e),
            And(identity_proofed(e), identity_bound(e)),
        ),
    )

    # PR.AA-03: Access to any asset requires authentication
    ax_pr_aa_03 = ForAll(
        [e, a],
        Implies(has_access(e, a), is_authenticated(e)),
    )

    # PR.AA-04: Authentication requires assertions are protected AND verified
    ax_pr_aa_04 = ForAll(
        [e],
        Implies(
            is_authenticated(e),
            And(assertion_protected(e), assertion_verified(e)),
        ),
    )

    # PR.AA-05: Access requires policy, authorisation, least privilege, SoD, review
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

    # PR.AA-06: Physical asset access is monitored and the asset's risk is assessed
    ax_pr_aa_06 = ForAll(
        [e, a],
        Implies(
            And(is_physical_asset(a), has_access(e, a)),
            And(physical_access_monitored(e, a), risk_assessed(a)),
        ),
    )

    axioms = [
        ax_pr_aa_01, ax_pr_aa_02, ax_pr_aa_03,
        ax_pr_aa_04, ax_pr_aa_05, ax_pr_aa_06,
    ]

    return {
        "Entity": Entity, "Asset": Asset, "e": e, "a": a,
        "axioms": axioms,
        # predicates
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
    }


# ── Checks ─────────────────────────────────────────────────────────────────────
def _solver_with_axioms(axioms) -> Solver:
    s = Solver()
    s.add(*axioms)
    return s


def check_01_global_consistency(m: dict) -> dict:
    """
    CHECK 1 — Global Consistency
    Are all six requirements simultaneously satisfiable?
    Expected: SAT  (they are not contradictory with each other)
    """
    s = _solver_with_axioms(m["axioms"])
    result = s.check()
    if result == sat:
        return {
            "kind": "SAT",
            "check": "Global Consistency (all 6 requirements together)",
            "detail": "All PR.AA-01 through PR.AA-06 axioms are simultaneously\n"
                      "satisfiable — no internal contradiction exists across the set.",
        }
    return {
        "kind": "UNSAT",
        "check": "Global Consistency (all 6 requirements together)",
        "detail": f"UNEXPECTED: Requirements are mutually inconsistent. Z3 result: {result}",
    }


def check_02_authentication_credential_gap(m: dict) -> dict:
    """
    CHECK 2 — Gap: Authentication ↛ Credential Management
    Can an entity be authenticated WITHOUT having managed credentials?
    PR.AA-03 requires authentication for access.
    PR.AA-01 requires credential management.
    But NEITHER requirement links them: no axiom says  is_authenticated → has_credentials.

    Expected: SAT  (the gap exists — authentication is possible without managed credentials)
    Finding: ⚠️ GAP — services or hardware can be authenticated via certificates or tokens
             without those credentials appearing in the organisation's credential inventory.
    """
    e = m["e"]
    s = _solver_with_axioms(m["axioms"])
    # Assert a counterexample: e is authenticated but has no credentials
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
    Does 'has_access' guarantee identity was proofed (PR.AA-02)?

    Chain as written:  has_access → is_authenticated  (PR.AA-03)
                       has_credentials → identity_proofed  (PR.AA-02)
    Missing link:      is_authenticated → has_credentials  (not in any requirement)

    Therefore:  has_access does NOT guarantee identity_proofed.
    Expected:   SAT (gap — the chain is broken)
    """
    e, a = m["e"], m["a"]
    s = _solver_with_axioms(m["axioms"])
    # Assert: entity has access but identity was never proofed
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
        "check": "Access → Identity Proofing chain is complete.",
        "detail": "No gap found.",
    }


def check_04_separation_of_duties_undefined(m: dict) -> dict:
    """
    CHECK 4 — Ambiguity: Separation of Duties is an unconstrained predicate
    PR.AA-05 asserts sep_of_duties_applied(e, a) for all access,
    but the model contains NO axiom defining what sep_of_duties_applied means
    or what it entails.  Z3 treats it as vacuously satisfiable.

    Finding: 🔍 AMBIGUITY — SoD is required but never formally defined.
    """
    e, a = m["e"], m["a"]
    s = _solver_with_axioms(m["axioms"])
    # Can sep_of_duties_applied be True AND False for different entities simultaneously?
    e2 = Const("e2", m["Entity"])
    a2 = Const("a2", m["Asset"])
    s.add(m["sep_of_duties_applied"](e, a))
    s.add(Not(m["sep_of_duties_applied"](e2, a2)))
    result = s.check()
    if result == sat:
        return {
            "kind": "AMBIGUITY",
            "check": "PR.AA-05: Separation of Duties — undefined predicate",
            "detail": "sep_of_duties_applied is simultaneously True for one (entity, asset)\n"
                      "pair and False for another, with no contradiction.\n"
                      "The requirement states SoD must be incorporated but never defines:\n"
                      "  • What constitutes a 'duty'\n"
                      "  • How many principals are required for separation\n"
                      "  • What actions conflict and must be separated\n"
                      "Recommendation: add sub-requirements defining SoD criteria.",
        }
    return {
        "kind": "SAT",
        "check": "PR.AA-05: Separation of Duties",
        "detail": "SoD predicate is consistent.",
    }


def check_05_physical_logical_access_boundary(m: dict) -> dict:
    """
    CHECK 5 — Ambiguity: Physical access and PR.AA-05 policy scope
    PR.AA-05 requires access_in_policy for all has_access.
    PR.AA-06 adds monitoring for physical assets.

    But: is 'has_access' in PR.AA-05 the same predicate covering physical assets?
    In this model, YES — has_access is universal.
    However, the natural language of PR.AA-05 ('logical access') vs PR.AA-06
    ('physical access') implies they may be separate — but the text doesn't say so.

    Check: can a physical asset be accessed without being in policy?
    With our model: UNSAT (good — PR.AA-05 covers it)
    BUT: if organisations model them as separate predicates, the gap re-appears.
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
    CHECK 6 — Implication chain: What does 'has_access' truly guarantee?
    This traces the complete chain of guarantees flowing from has_access(e, a):

      has_access(e,a) →  [PR.AA-03]  is_authenticated(e)
                      →  [PR.AA-04]  assertion_protected(e) ∧ assertion_verified(e)
                      →  [PR.AA-05]  access_in_policy ∧ access_authorized ∧ least_privilege ∧ ...
                      →  [PR.AA-06]  (if physical) physical_access_monitored ∧ risk_assessed

    NOT guaranteed (because of gap from check_02 and check_03):
      has_access does NOT guarantee: has_credentials, credentials_managed, identity_proofed

    We test: does has_access imply credentials_managed? Expected: SAT (not guaranteed = gap)
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
        "check": "Access chain is complete.",
        "detail": "has_access implies credentials_managed.",
    }


# ── Orchestrator ───────────────────────────────────────────────────────────────
CHECKS = [
    check_01_global_consistency,
    check_02_authentication_credential_gap,
    check_03_access_to_identity_proofing_chain,
    check_04_separation_of_duties_undefined,
    check_05_physical_logical_access_boundary,
    check_06_full_access_guarantee_chain,
]

CHECK_REQUIREMENT_MAP = {
    check_01_global_consistency:                "PR.AA-01 – PR.AA-06",
    check_02_authentication_credential_gap:     "PR.AA-01 × PR.AA-03",
    check_03_access_to_identity_proofing_chain: "PR.AA-02 × PR.AA-03",
    check_04_separation_of_duties_undefined:    "PR.AA-05",
    check_05_physical_logical_access_boundary:  "PR.AA-05 × PR.AA-06",
    check_06_full_access_guarantee_chain:       "PR.AA-01 – PR.AA-06",
}


def run(formal: list[dict] | None = None, verbose: bool = True) -> list[dict]:
    """
    Runs all Z3 checks against the PR.AA domain model.

    Args:
        formal:  Output from skill_02_formalizer.run() — used to display
                 SMT-LIB2 snippets alongside results (optional, display only)
        verbose: If True, prints formatted output to terminal

    Returns:
        List of finding dicts  {kind, check, detail}
    """
    model = build_model()

    if verbose and formal:
        _print_smt_lib2_reference(formal)

    findings = []
    for i, check_fn in enumerate(CHECKS, 1):
        finding = check_fn(model)
        findings.append(finding)

        if verbose:
            req_scope = CHECK_REQUIREMENT_MAP.get(check_fn, "")
            print(c(f"  Check {i}  ·  scope: {req_scope}", DIM))
            print_finding(
                finding["kind"],
                finding["check"],
                finding.get("detail", ""),
            )

    return findings


def _print_smt_lib2_reference(formal: list[dict]):
    """
    Display a condensed SMT-LIB2 reference from skill_02 so engineers can
    see the connection between the displayed logic and the solver.
    """
    print(c("  SMT-LIB2 from Stage 2 (reference — solver uses Z3 Python API):", BOLD))
    print()
    for f in formal[:2]:  # Show first two to keep output digestible
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


# ── Standalone entry point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    from utils.terminal import print_summary

    print_stage(
        3,
        "SMT SOLVING  (Z3)",
        "Running automated reasoning proofs against the PR.AA formal model",
    )
    findings = run(formal=None, verbose=True)
    print_summary(findings)
