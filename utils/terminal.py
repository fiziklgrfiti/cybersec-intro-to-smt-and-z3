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


def print_finding(kind: str, description: str, detail: str = ""):
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
