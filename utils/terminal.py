"""
utils/terminal.py — ANSI terminal output helpers for the Requirements Engine.
Keeps display logic out of skill files so each skill focuses on logic only.
"""

# ── ANSI colour codes ────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

BLACK   = "\033[30m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
WHITE   = "\033[37m"

BG_BLUE  = "\033[44m"
BG_BLACK = "\033[40m"


def c(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes."""
    return "".join(codes) + str(text) + RESET


def rule(char: str = "─", width: int = 72, color: str = DIM) -> str:
    return c(char * width, color)


def print_banner():
    print()
    print(c("╔══════════════════════════════════════════════════════════════════════╗", CYAN, BOLD))
    print(c("║         REQUIREMENTS ENGINE  ·  NIST CSF 2.0 Edition               ║", CYAN, BOLD))
    print(c("║         LLM Rewriting  →  Formal Logic  →  SMT Solving (Z3)        ║", CYAN))
    print(c("╚══════════════════════════════════════════════════════════════════════╝", CYAN, BOLD))
    print()


def print_stage(number: int, title: str, subtitle: str = ""):
    print()
    print(rule("═"))
    tag  = c(f" STAGE {number} ", BOLD, BG_BLUE, WHITE)
    name = c(f"  {title}", BOLD, CYAN)
    print(f"{tag}{name}")
    if subtitle:
        print(c(f"  {subtitle}", DIM))
    print(rule("─"))
    print()


def print_requirement_header(req_id: str, req_text: str):
    print(c(f"▶ {req_id}", BOLD, YELLOW))
    print(c(f"  {req_text}", DIM))
    print()


def print_sub(label: str, content: str, indent: int = 2):
    pad = " " * indent
    print(c(f"{pad}{label}:", BOLD, BLUE))
    for line in content.strip().split("\n"):
        print(f"{pad}  {line}")
    print()


def print_shall(statements: list[dict]):
    for s in statements:
        sid   = c(s.get("id", ""), BOLD, MAGENTA)
        stmt  = s.get("statement", "")
        ind   = s.get("testable_indicator", "")
        print(f"    {sid}  {stmt}")
        if ind:
            print(c(f"          ↳ Testable via: {ind}", DIM))
    print()


def print_finding(kind: str, description: str, detail: str = "", previous_kind: str | None = None):
    icons = {"SAT": "✅", "GAP": "⚠️ ", "AMBIGUITY": "🔍", "UNSAT": "❌", "INFO": "ℹ️ "}
    colors = {
        "SAT": GREEN, "GAP": YELLOW, "AMBIGUITY": YELLOW,
        "UNSAT": RED, "INFO": BLUE,
    }
    icon  = icons.get(kind, "•")
    color = colors.get(kind, WHITE)
    label = c(f"[{kind}]", BOLD, color)
    print(f"  {icon}  {label}  {description}")
    if detail:
        for line in detail.strip().split("\n"):
            print(c(f"           {line}", DIM))
    # Inline before/after annotation when comparing against a previous pass
    _failing_kinds = {"GAP", "AMBIGUITY", "UNSAT"}
    if previous_kind is not None and previous_kind != kind:
        prev_icon  = icons.get(previous_kind, "•")
        prev_color = colors.get(previous_kind, WHITE)
        prev_label = c(f"[{previous_kind}]", BOLD, prev_color)
        print(c(f"           ↳ was {prev_icon} {prev_label} — closed this revision", GREEN))
    elif previous_kind is not None and previous_kind in _failing_kinds and kind in _failing_kinds:
        # Only annotate "still open" when both old and new are failing kinds
        print(c(f"           ↳ still open", YELLOW))
    print()


def print_patch_plan(open_findings: list[dict], rule_catalogue: list[tuple]) -> None:
    """
    Print a pre-announcement block listing every planned fix before anything
    is applied.  Shows the finding, the axiom being introduced (formal notation),
    and a plain-English rationale so the audience understands what will change
    and why before the solver re-runs.
    """
    if not open_findings:
        return

    count = len(open_findings)
    plural = "fix" if count == 1 else "fixes"
    print(c(f"  ┌─ Planned {plural} — {count} finding(s) targeted {'─' * 30}", DIM))
    print(c("  │", DIM))

    for finding in open_findings:
        check_name = finding.get("check", "")
        kind       = finding.get("kind", "")
        kind_icon  = "⚠️ " if kind == "GAP" else "🔍"
        print(c(f"  │  {kind_icon} ", DIM) + c(check_name, YELLOW))

        # Look up the matching rule-catalogue entry
        matched_desc    = None
        matched_axiom   = None
        matched_rationale = None
        for substr, _factory, description, _source in rule_catalogue:
            if substr in check_name:
                matched_desc = description
                # Extract the axiom hint — only when a colon separator is present
                if "→" in description and ":" in description:
                    matched_axiom = description.split(":", 1)[-1].strip()
                break

        if matched_axiom:
            print(c(f"  │     Axiom:     {matched_axiom}", CYAN))
        elif matched_desc:
            print(c(f"  │     Fix:       {matched_desc}", CYAN))
        else:
            print(c("  │     Fix:       (no rule-based fix — LLM guidance will be used)", YELLOW))

        # Plain-English rationale drawn from the finding detail (first two lines)
        detail = finding.get("detail", "")
        if detail:
            first_lines = detail.strip().split("\n")[:2]
            for line in first_lines:
                print(c(f"  │     Rationale: {line.strip()}", DIM))
        print(c("  │", DIM))

    print(c(f"  └{'─' * 62}", DIM))
    print()


def print_scoreboard(history: list[dict]) -> None:
    """
    Print a compact progress table across all revisions (baseline + rN passes).

    Each entry in history is:
        {"label": "Baseline" | "r1" | ..., "SAT": n, "GAP": n, "AMBIGUITY": n, "UNSAT": n}
    """
    if not history:
        return

    # Use fixed-width plain-text column headers to avoid emoji terminal-width issues
    col_w = 10
    print()
    print(c("  ┌─ Progress scoreboard " + "─" * 46, DIM))
    header = f"  {'Revision':<12}{'SAT':>{col_w}}{'Gaps':>{col_w}}{'Ambig':>{col_w}}{'Unsat':>{col_w}}"
    print(c(header, BOLD))
    print(c("  " + "─" * 52, DIM))

    prev = None
    for entry in history:
        label = entry["label"]
        row = f"  {label:<12}"
        for key in ("SAT", "GAP", "AMBIGUITY", "UNSAT"):
            val  = entry[key]
            cell = str(val)
            # Mark improvement with ✓
            if prev is not None:
                if key == "SAT" and val > prev["SAT"]:
                    cell += "✓"
                elif key in ("GAP", "AMBIGUITY", "UNSAT") and val < prev[key]:
                    cell += "✓"
            row += f"{cell:>{col_w}}"
        # Colour the row: green if all issues zero, yellow if improved, white otherwise
        issues       = entry["GAP"] + entry["AMBIGUITY"] + entry["UNSAT"]
        baseline_issues = history[0]["GAP"] + history[0]["AMBIGUITY"] + history[0]["UNSAT"]
        color = GREEN if issues == 0 else (YELLOW if issues < baseline_issues else WHITE)
        print(c(row, color))
        prev = entry

    print(c("  └" + "─" * 52, DIM))
    print()


def print_smt_block(title: str, content: str, color: str = WHITE):
    print(c(f"  ┌─ {title}", DIM))
    for line in content.strip().split("\n"):
        print(c(f"  │  ", DIM) + c(line, color))
    print(c("  └" + "─" * 60, DIM))
    print()


def print_summary(findings: list[dict]):
    print()
    print(rule("═"))
    print(c("  ANALYSIS SUMMARY", BOLD, CYAN))
    print(rule("─"))
    counts = {"SAT": 0, "GAP": 0, "AMBIGUITY": 0, "UNSAT": 0}
    for f in findings:
        k = f.get("kind", "INFO")
        if k in counts:
            counts[k] += 1

    print(f"  {c('✅', GREEN)}  Consistent checks : {c(str(counts['SAT']),   BOLD, GREEN)}")
    print(f"  {c('⚠️ ', YELLOW)} Gaps identified    : {c(str(counts['GAP']),   BOLD, YELLOW)}")
    print(f"  {c('🔍', YELLOW)} Ambiguities        : {c(str(counts['AMBIGUITY']), BOLD, YELLOW)}")
    print(f"  {c('❌', RED)}  Contradictions     : {c(str(counts['UNSAT']), BOLD, RED)}")
    print()
    print(c("  Next steps: feed gaps & ambiguities back into Stage 1 for refinement.", DIM))
    print(rule("═"))
    print()
