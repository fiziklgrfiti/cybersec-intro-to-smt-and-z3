# Additional Literature Guide
## Understanding Z3, Formal Verification, and Automated Reasoning
### A Bridge from Curious Beginner to Technical Reader

---

> **Who this is for.** You are comfortable with computers and maybe know a little programming. You have not yet studied logic, algorithms, or theoretical computer science at university. This guide takes the two research papers that underpin the Z3 solver — the tool at the heart of Stage 3 of this requirements engine — and translates them into language you can actually follow. Each section tells you what you will understand by the end of it, and then points you to the exact part of the original papers where you can go deeper.

---

## Table of Contents

1. [The Big Picture: What Problem Are We Actually Solving?](#1-the-big-picture-what-problem-are-we-actually-solving)
2. [What Is a Solver? The Puzzle-Solving Analogy](#2-what-is-a-solver-the-puzzle-solving-analogy)
3. [The Language of Logic: How We Write Things Down Precisely](#3-the-language-of-logic-how-we-write-things-down-precisely)
4. [Sorts and Types: Keeping Things Organised](#4-sorts-and-types-keeping-things-organised)
5. [Predicates and Functions: Asking Yes/No Questions](#5-predicates-and-functions-asking-yesno-questions)
6. [Quantifiers: Saying "For All" and "There Exists"](#6-quantifiers-saying-for-all-and-there-exists)
7. [Theories: The Solver's Subject-Matter Expertise](#7-theories-the-solvers-subject-matter-expertise)
   - Equality and Uninterpreted Functions
   - Arithmetic
   - Arrays
   - Bit-Vectors
8. [SAT and UNSAT: The Two Verdicts](#8-sat-and-unsat-the-two-verdicts)
9. [SMT-LIB2: The Solver's Native Language](#9-smt-lib2-the-solvers-native-language)
10. [How the Solver Thinks: CDCL — Guess, Learn, Backtrack](#10-how-the-solver-thinks-cdcl--guess-learn-backtrack)
11. [Congruence Closure: Chaining Equalities Together](#11-congruence-closure-chaining-equalities-together)
12. [Models: What a Satisfying Answer Actually Looks Like](#12-models-what-a-satisfying-answer-actually-looks-like)
13. [Unsatisfiable Cores: Why Something Is Impossible](#13-unsatisfiable-cores-why-something-is-impossible)
14. [Quantifier Instantiation: Reasoning About "For All" Cases](#14-quantifier-instantiation-reasoning-about-for-all-cases)
15. [Tactics: Pre-Processing Before the Solver Runs](#15-tactics-pre-processing-before-the-solver-runs)
16. [How This Connects to the Requirements Engine](#16-how-this-connects-to-the-requirements-engine)
17. [Your Reading Path: Where to Go Next in the Papers](#17-your-reading-path-where-to-go-next-in-the-papers)

---

## 1. The Big Picture: What Problem Are We Actually Solving?

### Learning Outcomes
By the end of this section you will understand:
- Why computers can help check whether logical statements are consistent
- The difference between checking facts manually and checking them automatically
- Why this matters in cybersecurity and software engineering

---

Imagine you are a referee in a debate competition. Two teams each make a set of claims. Your job is to decide: do these claims contradict each other? Could both teams possibly be right at the same time, or is one of them making a logically impossible argument?

For a human, this is hard when there are hundreds of claims, each depending on the others in complex ways. You might miss a contradiction buried on page forty of the argument. But a computer — given the right tools — can check this systematically, exhaustively, and quickly.

That is exactly what an SMT solver does. SMT stands for **Satisfiability Modulo Theories**. It is a program that takes a collection of logical statements and answers one question:

> **Is there any possible world where all of these statements are true at the same time?**

If yes: **SAT** (satisfiable). The solver can even show you what that world looks like.

If no: **UNSAT** (unsatisfiable). The statements are contradictory — no possible world could satisfy all of them simultaneously.

This capability turns out to be extraordinarily useful:

- In **software verification**: "Is it possible for this program to crash? Could it ever reach this bad state?" The solver checks whether a crash scenario is logically consistent with the program's rules.
- In **hardware design**: "Could these two circuits ever produce conflicting outputs?" The solver checks whether a conflict is achievable.
- In **cybersecurity requirements analysis** (this project): "Do these six NIST requirements logically cover each other, or do they leave gaps that could be exploited?"

Z3 is Microsoft Research's implementation of an SMT solver. It is one of the most widely used in the world, and the two papers referenced in this guide are the definitive technical descriptions of how it works.

---

## 2. What Is a Solver? The Puzzle-Solving Analogy

### Learning Outcomes
By the end of this section you will understand:
- What it means to "solve" a logical formula
- The difference between trying solutions manually and systematic automated search
- Why solvers are faster than exhaustive guessing

---

Think about a Sudoku puzzle. The rules of Sudoku are a set of constraints:
- Each row must contain the digits 1–9 exactly once
- Each column must contain the digits 1–9 exactly once
- Each 3×3 box must contain the digits 1–9 exactly once
- Some cells are already filled in

A Sudoku solver takes these constraints and finds an assignment of digits to empty cells that satisfies all of them simultaneously. If no such assignment exists, the puzzle is unsolvable.

An SMT solver works on exactly this principle, but instead of digits in cells, it works with:
- **Variables** (unknowns that need to be assigned values)
- **Constraints** (rules that the assignments must satisfy)
- **Theories** (mathematical structures that give meaning to the constraints)

The genius of modern SMT solvers is that they do not try every possible combination of values. That would be hopelessly slow — even a 9×9 Sudoku has 9^81 possible filled grids. Instead, solvers use **smart search**: they make educated guesses, follow the logical consequences of each guess, and when they find a contradiction, they learn from it and backtrack intelligently to avoid exploring the same dead ends again.

This smart search strategy is called **CDCL** (Conflict Driven Clause Learning), and it is the engine inside Z3. We will explain it fully in Section 10.

### Going deeper in the papers
The opening of *Programming Z3* (Section 1, Introduction) gives the same overview in more technical language. Once you have finished this guide, that introduction will make much more sense.

---

## 3. The Language of Logic: How We Write Things Down Precisely

### Learning Outcomes
By the end of this section you will understand:
- What a logical formula is
- The basic building blocks: atoms, connectives, and formulas
- Why computers need a formal language rather than plain English

---

Natural language is ambiguous. The sentence "the user is authorised and authenticated or their session is valid" is genuinely unclear: does the "or" apply to the whole thing, or just to "authenticated"? Different people reading it will parse it differently.

Formal logic removes that ambiguity by using a precise grammar. The basic building blocks are:

**Atoms** are the smallest statements that can be true or false. In our requirements engine, atoms include things like:
- `has_credentials(alice)` — Alice has credentials
- `is_authenticated(alice)` — Alice is authenticated
- `has_access(alice, database)` — Alice has access to the database

**Connectives** combine atoms into larger formulas:

| Symbol | Name | Meaning | Example |
|---|---|---|---|
| `¬` | NOT | the opposite | `¬is_authenticated(alice)` means "Alice is NOT authenticated" |
| `∧` | AND | both must be true | `has_credentials(alice) ∧ is_authenticated(alice)` |
| `∨` | OR | at least one must be true | `is_authenticated(alice) ∨ session_valid(alice)` |
| `→` | IMPLIES | if the left is true, the right must be too | `has_access(alice, db) → is_authenticated(alice)` |
| `↔` | IF AND ONLY IF | both are true or both are false | `authorised(alice) ↔ in_policy(alice) ∧ least_privilege(alice)` |

**Quantifiers** let us make statements about groups of things rather than just individuals (we cover these fully in Section 6).

The reason we need this formal language for an SMT solver is simple: computers cannot reason with ambiguity. Every connective has an exact, unambiguous meaning. This is what allows the solver to check formulas mechanically and reliably.

### Going deeper in the papers
*Programming Z3*, Section 2 ("Logical Interfaces to Z3"), covers this in detail, including how to write these formulas using Z3's Python API. The section on "Terms and Formulas" (Section 2.3) explains how Z3 represents formulas internally.

---

## 4. Sorts and Types: Keeping Things Organised

### Learning Outcomes
By the end of this section you will understand:
- What a "sort" is in logic and why we need them
- How sorts prevent meaningless comparisons
- What the built-in sorts in Z3 are

---

In everyday language, some comparisons just do not make sense. You would not ask "is this colour heavier than that number?" The question is meaningless because colours and numbers are different *kinds* of things.

Formal logic handles this with **sorts** (also called *types*). A sort is a named category of things. Before you can use a variable in a formula, you declare what sort it belongs to. Then the solver can reject formulas that mix incompatible sorts.

Z3 comes with several **built-in sorts**:

| Sort | What it represents | Example |
|---|---|---|
| `Bool` | True or false | the result of `is_authenticated(alice)` |
| `Int` | Whole numbers (...-2, -1, 0, 1, 2...) | a count of failed login attempts |
| `Real` | Decimal numbers | a risk score like 0.73 |
| `BitVec(n)` | An n-bit binary number | a memory address in a 64-bit system |
| `String` | Text | a username |

You can also **declare your own sorts** for things that do not naturally fit any built-in category. This is what the requirements engine does:

```python
Entity = DeclareSort("Entity")   # a new sort for users, services, hardware
Asset  = DeclareSort("Asset")    # a new sort for things that can be accessed
```

By declaring `Entity` and `Asset` as distinct sorts, we prevent the solver from ever confusing them. A formula that tries to apply `has_access(some_asset, some_entity)` (backwards — an asset accessing an entity) would be a type error that Z3 would reject immediately.

Sorts are one of the most important reasons formal logic is more reliable than natural language for requirements analysis. They act as an automatic sanity check on the structure of your statements.

### Going deeper in the papers
*Programming Z3*, Section 2.1 ("Sorts") covers built-in and declared sorts. *Z3 Internals*, Section 4.1 ("Terms and Formulas") explains how sorts are represented inside Z3's memory.

---

## 5. Predicates and Functions: Asking Yes/No Questions

### Learning Outcomes
By the end of this section you will understand:
- What a predicate is and how it differs from a function
- What "uninterpreted" means and why it matters for modelling
- How predicates become the building blocks of requirements

---

A **function** takes one or more inputs and produces an output. You have seen functions in maths: `f(x) = x²` takes a number and returns its square.

In formal logic, functions work the same way but their inputs and outputs are *sorts*. A function `has_credentials` that takes an `Entity` and returns a `Bool` (true or false) is called a **predicate** — a function that asks a yes/no question about its input.

```python
has_credentials = Function("has_credentials", Entity, BoolSort())
```

Read this as: "`has_credentials` is a function that takes one `Entity` and returns `Bool`."

When you write `has_credentials(alice)`, you are asking the question "does Alice have credentials?" The solver then determines whether that should be true or false based on the axioms you have given it.

### What does "uninterpreted" mean?

Here is a crucial concept. In Z3, a function can be **interpreted** (it has a specific, built-in mathematical meaning, like `+` for addition) or **uninterpreted** (it is just a name with a type signature — you give it meaning by adding axioms).

When we declare `has_credentials = Function("has_credentials", Entity, BoolSort())`, we are creating an **uninterpreted function**. Z3 does not know what `has_credentials` means — it just knows that it takes an `Entity` and returns `Bool`. The meaning comes from the axioms we add.

This is enormously powerful for requirements modelling. We are not modelling a specific system where we know exactly who has credentials. We are modelling the *logical structure* of the requirements — what things imply other things — without committing to any particular implementation. The solver can then tell us whether the structure is consistent, regardless of which specific users or systems are involved.

Think of it this way: a traffic law that says "drivers must stop at red lights" is an uninterpreted rule. It applies to any driver, any car, any intersection. We are not modelling Alice's specific car — we are modelling the logical structure of the law. Uninterpreted functions let us do the same thing for cybersecurity requirements.

### Going deeper in the papers
*Programming Z3*, Section 2.2 ("Signatures") introduces interpreted and uninterpreted functions. Section 3.1 ("EUF: Equality and Uninterpreted Functions") explains the full theory of what you can reason about with uninterpreted functions.

---

## 6. Quantifiers: Saying "For All" and "There Exists"

### Learning Outcomes
By the end of this section you will understand:
- What universal and existential quantification mean
- Why quantifiers are needed to express requirements about all entities
- The difference between a statement about one thing and a statement about everything

---

So far we have been talking about specific things: `has_credentials(alice)`. But requirements rarely talk about specific individuals. They talk about *all* users, *every* service, *any* asset. To express this, we need **quantifiers**.

### The Universal Quantifier: ∀ (For All)

`∀ e ∈ Entity: has_credentials(e) → credentials_managed(e)`

Read this as: "**For every** entity `e`, if `e` has credentials, then those credentials are managed."

This is a statement about *all* entities — every user, every service, every hardware device — not just Alice. This is exactly what PR.AA-01 says: credential management applies to *all* authorised entities, not just some of them.

In Z3's Python API:

```python
e = Const("e", Entity)   # e is a representative entity (a placeholder)
ForAll([e], Implies(has_credentials(e), credentials_managed(e)))
```

The `ForAll` tells Z3 that whatever it picks for `e`, the implication must hold.

### The Existential Quantifier: ∃ (There Exists)

`∃ e ∈ Entity: has_credentials(e) ∧ ¬credentials_managed(e)`

Read this as: "**There exists** at least one entity `e` that has credentials but whose credentials are *not* managed."

This is the form we use to *find counterexamples*. In Check 2 of the requirements engine, we ask: "Is there some entity that is authenticated but has no managed credentials?" If the solver finds one — if it returns SAT — we have found a gap.

### Why quantifiers matter for requirements

Without quantifiers, you would have to write out every individual case:
- "Alice must be authenticated"
- "Bob must be authenticated"  
- "Service-X must be authenticated"
- ...

That is obviously impractical for real systems. Quantifiers let you write one rule that covers every case, and let the solver reason about all of them at once.

### Going deeper in the papers
*Programming Z3*, Section 2.4 ("Quantifiers and Lambda binding") introduces quantifiers with examples. Section 6.1.3 ("E-matching based quantifier instantiation") and Section 6.1.4 ("Model-Based Quantifier Instantiation") explain how Z3 actually handles `ForAll` statements internally — this is one of the harder problems in automated reasoning.

---

## 7. Theories: The Solver's Subject-Matter Expertise

### Learning Outcomes
By the end of this section you will understand:
- What a "theory" means in the context of SMT solving
- Why different theories handle different kinds of problems
- The four main theories used in practice

---

An SMT solver is not just one reasoning engine — it is a *collection* of specialised engines, each expert in a different area of mathematics. These engines are called **theories**. When Z3 processes a formula, it identifies which theories are needed and coordinates between them.

Think of it like a hospital. A patient (the formula) comes in with multiple conditions. Rather than having one generalist doctor, there are specialists: a cardiologist for the heart, a neurologist for the brain, an orthopaedic surgeon for bones. They share information and together treat the whole patient. Z3's theories work the same way.

### Theory 1: Equality and Uninterpreted Functions (EUF)

This is the most fundamental theory. It handles:
- **Equality**: if `a = b` and `b = c`, then `a = c` (transitivity)
- **Congruence**: if `f(a) = something` and `a = b`, then `f(b) = something`

EUF is the theory used by the requirements engine. All our predicates (`has_credentials`, `is_authenticated`, etc.) are uninterpreted functions, and the axioms we write are EUF constraints.

The key insight of EUF: you can prove things about the *relationships* between predicates — "if A then B", "A and B are inconsistent" — without needing to know what A and B specifically mean.

### Theory 2: Arithmetic

This theory handles numbers. Z3 has several arithmetic sub-theories:
- **Linear Real Arithmetic (LRA)**: equations and inequalities with real numbers, where variables are only added or multiplied by constants (no `x × y`)
- **Linear Integer Arithmetic (LIA)**: same but with whole numbers
- **Non-linear arithmetic**: includes `x × y`, `x²`, etc. — much harder to solve

In the requirements engine, we do not use arithmetic directly. But arithmetic becomes essential when requirements include concepts like "at least 3 failed login attempts", "access must be reviewed within 90 days", or "the risk score must be below 0.5".

### Theory 3: Arrays

This theory handles mappings from keys to values — essentially, the logic of lookup tables. An array `A` supports two operations:
- `A[i]` — look up the value at index `i`
- `Store(A, i, v)` — create a new array identical to `A` except position `i` now holds `v`

This is useful for modelling things like: "the access control list maps each (user, resource) pair to either `allow` or `deny`."

### Theory 4: Bit-Vectors

Computer memory is made of bits — zeros and ones. Bit-vectors are fixed-width binary numbers, and Z3's bit-vector theory can reason about them exactly as a real computer does, including overflow, wrapping, and bitwise operations.

This theory is essential when verifying properties of actual software or hardware, where numbers have finite size and can overflow. For requirements analysis at the policy level (like this project), bit-vectors are not usually needed, but they are indispensable for verifying actual implementations.

### How theories combine

The real power of SMT is the *combination* of theories. A single formula can involve arrays of integers with uninterpreted functions over them. Z3 has a formal procedure (called the Nelson-Oppen combination) for safely combining theories that are "disjoint" (they do not share any function symbols except equality). The result is a combined solver that can handle real-world problems that mix multiple mathematical domains.

### Going deeper in the papers
*Programming Z3*, Section 3 covers all theories with worked examples in Python. The most important for this project is Section 3.1 (EUF). *Z3 Internals*, Section 3 provides the same material at a deeper algorithmic level. The description of Nelson-Oppen combination (Section 6.1.2 of *Programming Z3*) is important if you want to understand how multiple theories are combined correctly.

---

## 8. SAT and UNSAT: The Two Verdicts

### Learning Outcomes
By the end of this section you will understand:
- What SAT and UNSAT mean precisely
- How the same result (SAT) can mean different things depending on the question asked
- Why UNSAT is actually a *proof* that something is impossible

---

Every call to `solver.check()` in Z3 returns one of three answers:

| Verdict | Meaning |
|---|---|
| `sat` | Satisfiable — there exists at least one assignment of values that makes all the formulas true simultaneously |
| `unsat` | Unsatisfiable — no possible assignment could make all the formulas true at the same time |
| `unknown` | The solver ran out of time or resources before deciding (rare for the theories used here) |

### SAT is good news or bad news, depending on what you asked

This is the trickiest part for newcomers. SAT does not always mean "everything is fine." It depends entirely on what question you put to the solver.

**SAT as good news (Check 1 in the requirements engine):**
We ask: "Do all six PR.AA requirements hold simultaneously?" We want SAT — it means the requirements are internally consistent, not contradictory.

**SAT as bad news (Check 2 in the requirements engine):**
We ask: "Can an entity be authenticated without having managed credentials?" We want UNSAT (that would mean it is *impossible* to be authenticated without managed credentials — the requirement is enforced). But we get SAT — meaning the solver found a scenario where an entity *is* authenticated and *does not* have managed credentials. That is a gap.

### UNSAT is a proof

When a solver returns UNSAT, it is not just saying "I couldn't find an example." It is providing a **proof** that no example exists — that the statement is *logically impossible* given the axioms. This is a much stronger claim than a human saying "I looked hard and couldn't find one." The solver has exhausted the entire logical space.

This is why formal verification is more trustworthy than testing. Testing can show that a bug exists (by finding an example). UNSAT can show that a certain class of bug cannot exist, for any possible input, for all time.

### The negation trick

A key technique for using solvers is the **negation trick**. To prove that some property P always holds (is a theorem), you instead ask the solver: "Is it possible for P to be false?" If the solver returns UNSAT, then P being false is impossible — which means P must always be true. You have proved P.

In Check 6 of the requirements engine, we want to know: "Does `has_access` guarantee `credentials_managed`?" We assert `has_access(e, a)` and `NOT credentials_managed(e)` and check satisfiability. We get SAT — meaning the solver found a scenario where an entity has access but does not have managed credentials. The guarantee does not hold.

### Going deeper in the papers
The introduction to *Programming Z3* (Section 1) discusses the role of SAT and UNSAT. *Z3 Internals*, Section 2 describes how the solver works internally to reach these verdicts.

---

## 9. SMT-LIB2: The Solver's Native Language

### Learning Outcomes
By the end of this section you will understand:
- What SMT-LIB2 is and why it exists
- How to read basic SMT-LIB2 syntax
- How SMT-LIB2 connects to Z3's Python API

---

Imagine you need to send the same problem to five different experts who each speak a different language. You would want a common language — an *interlingua* — that all of them understand. For SMT solvers, that common language is **SMT-LIB2**.

SMT-LIB2 is a text-based format for writing formulas that any standards-compliant SMT solver can read. It is designed to be:
- Precise (no ambiguity)
- Tool-neutral (not specific to Z3, CVC5, or any one solver)
- Human-readable (with practice)

The syntax looks like Lisp or Scheme — everything is in parentheses, and the operator comes first.

### Reading basic SMT-LIB2

Here is the SMT-LIB2 version of PR.AA-01:

```smt2
; Declare a new uninterpreted sort called Entity
(declare-sort Entity 0)

; Declare predicates (functions to Bool)
(declare-fun has-credentials (Entity) Bool)
(declare-fun credentials-managed (Entity) Bool)

; Assert the axiom: for every entity e,
; if e has credentials then those credentials are managed
(assert
  (forall ((e Entity))
    (=> (has-credentials e)
        (credentials-managed e))))

; Ask the solver: is this satisfiable?
(check-sat)
```

The parentheses-heavy style (called S-expressions) is the same used in Lisp, one of the oldest programming languages. Once you are used to it, it reads naturally: `(=> A B)` means "A implies B", `(and A B)` means "A and B", `(not A)` means "not A".

### SMT-LIB2 vs the Python API

Z3 can be controlled either through SMT-LIB2 text files, or through its Python API (which is what this project uses). The Python API is more ergonomic for building tools — you can use variables, loops, and functions. But the underlying logic is identical. In fact, you can print out the SMT-LIB2 equivalent of any Python-based Z3 state:

```python
s = Solver()
s.add(ForAll([e], Implies(has_credentials(e), credentials_managed(e))))
print(s.sexpr())   # prints the SMT-LIB2 representation
```

In this project, Stage 2 uses Claude to generate SMT-LIB2 for display and education. Stage 3 uses the Python API for the actual proofs. Both represent the same logical content.

### Going deeper in the papers
*Programming Z3*, Section 2 shows Python and SMT-LIB2 side by side for the same formulas. The SMT-LIB2 standard is referenced throughout both papers. If you want to write your own formulas from scratch, the Z3 guide at https://microsoft.github.io/z3guide is a good interactive starting point.

---

## 10. How the Solver Thinks: CDCL — Guess, Learn, Backtrack

### Learning Outcomes
By the end of this section you will understand:
- What CDCL means and why it is the dominant approach to SAT solving
- How conflict-driven learning makes search dramatically faster
- Why solvers are much smarter than exhaustive guessing

---

The naive approach to checking satisfiability is brute force: try every possible combination of true/false assignments to every variable. For a formula with 100 Boolean variables, that is 2^100 combinations — more than the number of atoms in the observable universe. Clearly, brute force is not viable.

Modern solvers use a strategy called **CDCL: Conflict Driven Clause Learning**. It has three key phases:

### Phase 1: Decide (make a guess)

The solver picks a variable that has not yet been assigned and guesses a value for it (true or false). This is a **decision**. Decisions create branches in the search.

Think of it like exploring a maze: at a junction, you pick a direction and walk until you either reach the exit or hit a dead end.

### Phase 2: Propagate (follow the logical consequences)

Once a variable is assigned, many other variables may become forced by logical necessity. For example, if you know `P → Q` is true and `P` is true, then `Q` must also be true. The solver propagates all such forced assignments automatically and quickly.

This is called **unit propagation**, and it eliminates huge chunks of the search space without any guessing.

### Phase 3: Conflict and Learn (find dead ends and learn from them)

Sometimes the propagation reveals a contradiction — two things that cannot both be true. This is called a **conflict**. 

The crucial insight of CDCL is what happens next. Rather than just backtracking one step, the solver **analyses the conflict** to find the minimal set of decisions that caused it. It then adds this analysis as a new rule (a **learned clause**) that prevents the same dead end from being explored again, no matter what other decisions are made later.

This is the "learning" in CDCL. The solver gets smarter as it searches. Early conflicts teach it rules that prune later search. A solver that has been running for ten seconds has accumulated many learned rules and is much more powerful than it was at second one.

### An example

Suppose we have:
- `P → Q` (if P is true, Q must be true)
- `P → ¬Q` (if P is true, Q must be false)

If the solver decides `P = true`, propagation immediately gives both `Q = true` (from rule 1) and `Q = false` (from rule 2). Contradiction. The solver learns: "P cannot be true." It adds `¬P` as a rule and immediately eliminates all branches where `P = true`. No human had to point this out — the solver discovered it automatically.

### CDCL(T): Adding Theory Solvers

Standard CDCL handles only Boolean (propositional) formulas. The "(T)" in CDCL(T) stands for "Theories" — the extension that handles all the non-Boolean reasoning (arithmetic, arrays, uninterpreted functions, etc.).

In CDCL(T), the SAT solver handles the propositional structure and case splits. Theory solvers run in parallel and check whether the current assignment is consistent with their theory. If the arithmetic theory solver finds that the current assignment implies `x > 5` and `x < 3` simultaneously, it raises a conflict, just like a propositional contradiction. The CDCL engine learns from it and backtracks.

This cooperation between the SAT core and theory solvers is the fundamental architecture of Z3, and of most modern SMT solvers.

### Going deeper in the papers
*Programming Z3*, Section 6.1.1 ("CDCL(T): SAT + Theories") explains this with a worked example and actual Python code that simulates a simple CDCL(T) solver. This is one of the most educational parts of the paper. *Z3 Internals*, Section 2.1 provides the same material with more mathematical formalism and detail about the internal state transitions.

---

## 11. Congruence Closure: Chaining Equalities Together

### Learning Outcomes
By the end of this section you will understand:
- What congruence closure is and why it is needed
- How the solver deduces new equalities automatically
- Why this matters for reasoning about requirements

---

You know from primary school mathematics that equality is **transitive**: if `a = b` and `b = c`, then `a = c`. This seems obvious. But for a computer to reason about it automatically, across thousands of equalities in complex formulas, requires a dedicated algorithm.

**Congruence closure** is that algorithm. It extends transitivity to functions: if `a = b`, then `f(a) = f(b)` for any function `f`. This is the **congruence rule** — equal inputs produce equal outputs.

### Why does this matter?

Consider the formula:
- `a = b`
- `f(a) ≠ f(b)`

Is this satisfiable? Intuitively, no: if `a` and `b` are the same thing, applying any function to both must give the same result. Congruence closure detects this automatically:

1. The solver knows `a = b` (given)
2. Congruence rule: since `a = b`, we get `f(a) = f(b)`
3. But we also have `f(a) ≠ f(b)` (given)
4. Contradiction → UNSAT

The solver uses a data structure called **union-find** to track which things are known to be equal. Merging two equivalence classes is fast (nearly constant time). The challenge is applying congruence rules correctly when merging: any time two nodes `f(x)` and `f(y)` have their arguments `x` and `y` merged, `f(x)` and `f(y)` must also be merged.

### Connection to requirements analysis

Congruence closure is the core reasoning engine behind the PR.AA analysis. When we encode requirements as universal axioms and ask Z3 to check whether certain properties follow, it is congruence closure that chains the implications together:

- PR.AA-03: `has_access(e, a) → is_authenticated(e)`
- PR.AA-04: `is_authenticated(e) → assertion_protected(e)`
- Therefore: `has_access(e, a) → assertion_protected(e)` (congruence closure chains these)

Check 6 of the requirements engine uses this chaining to produce the full audit of what `has_access` does and does not guarantee.

### Going deeper in the papers
*Programming Z3*, Section 3.1 ("EUF: Equality and Uninterpreted Functions") covers congruence closure with examples. Section 3.1.1 ("Congruence Closure") gives the formal definition. *Z3 Internals*, Section 3.2 is the definitive technical treatment, including the E-Node data structure, the merge algorithm, and how backtracking works.

---

## 12. Models: What a Satisfying Answer Actually Looks Like

### Learning Outcomes
By the end of this section you will understand:
- What a model is in formal logic
- How Z3 represents a model
- What models tell us about gaps and counterexamples

---

When the solver returns SAT, it is not just saying "yes, this is possible." It can also show you *specifically what possibility it found*. This specific example is called a **model**.

A model is an assignment of concrete values to all variables and functions that makes every formula true. Think of it as the solver producing a "witness" — a specific scenario that satisfies all the requirements.

### An example model

If you ask Z3 "is there some integer `x` such that `x > 3` and `x < 10`?", it might return:

```
SAT
Model: x = 4
```

The model `x = 4` is a witness — a concrete example that satisfies both conditions. Other valid models would be `x = 5`, `x = 7`, etc.

For uninterpreted functions, models look a little different. Z3 produces a **lookup table** — a list of specific input-output pairs that define the function for the cases it needs to consider:

```
f = [0 → 3, 3 → 0, else → 1]
```

This means: `f(0) = 3`, `f(3) = 0`, and for any other input, `f` returns 1. This is a concrete interpretation of an uninterpreted function that satisfies all the axioms.

### Models as counterexamples

In the requirements analysis context, models are most useful as **counterexamples** — they show us the specific gap or ambiguity the solver found.

When Check 2 (Authentication ↛ Credential Management) returns SAT, Z3 has found a specific entity `e` that is authenticated but has no managed credentials. The model would show you this entity. Even though in our uninterpreted-function model it is an abstract value like `Entity!val!0`, in a real implementation it would correspond to a specific class of system entity — for example, a hardware device using an X.509 certificate that was provisioned outside the IAM system.

### Going deeper in the papers
*Programming Z3*, Section 4.5 ("Models") covers how to access and interpret models from the Python API. *Z3 Internals*, Section 5 ("Model Construction") gives a deep technical explanation of how Z3 builds models from satisfying states. This is worth reading once you are comfortable with the basics.

---

## 13. Unsatisfiable Cores: Why Something Is Impossible

### Learning Outcomes
By the end of this section you will understand:
- What an unsatisfiable core is
- How cores explain *why* something is contradictory
- How cores help improve requirements

---

When the solver returns UNSAT, it can also tell you *why*. Specifically, it can identify the **minimal subset** of your axioms that together cause the impossibility. This is called an **unsatisfiable core** (or unsat core).

### An analogy

Imagine you are debugging a set of rules for a game, and you discover the rules are contradictory. An unsat core is like a friend who says: "You don't need to look at all 200 rules. Just rules 3, 17, and 42 — those three together are the problem. All the others are fine."

The core helps you pinpoint exactly which requirements are in tension, rather than leaving you to search through all of them.

### How cores are used in requirements analysis

In the requirements engine, if two requirements actually contradicted each other (which the PR.AA requirements do not, as Check 1 confirms), an unsat core would tell you exactly which two (or more) requirements are in conflict. You could then bring those specific requirements to the framework authors and say: "These requirements, as written, cannot both be satisfied simultaneously. Here is the proof."

This is far more actionable than a vague feeling that "something seems off about requirements 3 and 5."

### Minimal cores vs. any core

Z3 will by default return *a* core, not necessarily the *smallest* core. The smallest possible core (the one where removing any single element makes it satisfiable) is called a **minimal unsatisfiable core** or **MUC**. Finding minimal cores is computationally harder, but produces cleaner explanations. The *Programming Z3* paper includes an algorithm for finding minimal cores.

### Going deeper in the papers
*Programming Z3*, Section 4.4 ("Cores") and Section 5.4 ("All Cores and Correction Sets") cover unsatisfiable cores in depth, including the MARCO algorithm for enumerating all minimal cores. *Z3 Internals*, Section 6 covers the technical infrastructure for producing cores and certificates.

---

## 14. Quantifier Instantiation: Reasoning About "For All" Cases

### Learning Outcomes
By the end of this section you will understand:
- Why reasoning about "for all" statements is hard for computers
- The two main strategies Z3 uses to handle quantifiers
- Why quantifier reasoning sometimes fails or times out

---

Handling universal quantifiers (`ForAll`) is one of the hardest problems in automated reasoning. The challenge is fundamental: `ForAll([e], P(e))` says that `P` holds for *every* possible entity — but there are infinitely many possible entities. You cannot check them all.

Z3 uses two main strategies to handle this:

### Strategy 1: E-matching (Pattern-based instantiation)

E-matching works by looking at the *structure* of the quantified formula and finding ground (specific) terms in the current formula that match the pattern.

For example, if we have the axiom:
```
ForAll([e, a], Implies(has_access(e, a), is_authenticated(e)))
```

And elsewhere in the formula we have the specific fact `has_access(alice, database)`, then E-matching recognises that `alice` can substitute for `e` and `database` for `a`. It then creates the specific instance:
```
Implies(has_access(alice, database), is_authenticated(alice))
```

This specific statement is then handed to the solver as a ground (quantifier-free) fact, which is much easier to reason about.

E-matching is fast and predictable, but it is **incomplete** — it might miss valid instantiations if the pattern does not match any existing ground term.

### Strategy 2: Model-Based Quantifier Instantiation (MBQI)

MBQI works differently. After finding a satisfying assignment to the quantifier-free part of the formula, it checks whether that assignment also satisfies the quantified formulas. If not, it extracts an instantiation that would fix the violation, adds it as a new constraint, and tries again.

MBQI is more powerful than E-matching for certain formula classes, and can actually decide satisfiability for fragments like EPR (Effectively Propositional Reasoning), UFBV (Uninterpreted Functions + Bit-Vectors), and the Array Property Fragment. These are named classes of formulas where MBQI is guaranteed to terminate with the correct answer.

### Why quantifiers can cause timeouts

For formulas outside the decidable fragments, quantifier instantiation may not terminate. The solver keeps creating new instances, each of which potentially creates new ground terms that trigger more instances — an infinite loop. Z3 has heuristics to detect and limit this, but for complex quantified formulas, timeouts are a real possibility.

This is not a bug — it is a fundamental limitation. The problem of deciding all first-order logic formulas is **undecidable** (proven by Turing in the 1930s). SMT solvers are working around this undecidability with smart heuristics, not solving it.

### Going deeper in the papers
*Programming Z3*, Sections 6.1.3 and 6.1.4 explain E-matching and MBQI respectively, with worked examples. *Z3 Internals*, Section 7 gives the most complete treatment of quantifier reasoning in Z3, including E-matching code trees, inverted path indexing, and the decidable fragments supported by MBQI. Section 9.2.5 addresses common user problems with quantifiers.

---

## 15. Tactics: Pre-Processing Before the Solver Runs

### Learning Outcomes
By the end of this section you will understand:
- What a tactic is and why pre-processing helps
- Common tactics and what they do
- Why the order of tactics matters

---

Before Z3's core solver tackles a formula, it often applies a sequence of **pre-processing transformations** called **tactics**. These simplify the formula, eliminate variables, and put it in a form that the solver can handle more efficiently.

Think of tactics as a preparation stage, like a chef doing mise en place before cooking: chopping vegetables, measuring spices, pre-heating the oven. None of these steps cook the food, but they make the actual cooking much faster and more reliable.

### Common tactics and what they do

**`simplify`**: Performs algebraic simplifications. Rewrites `x + 0` as `x`, `True ∧ P` as `P`, `P ∨ False` as `P`. Fast, and nearly always worth running.

**`propagate-values`**: If the formula contains a direct assignment like `x = 5`, it replaces all other occurrences of `x` with `5` and removes the equality. This can dramatically shrink the formula.

**`solve-eqs`**: Finds variables that appear in exactly one equality and solves for them. If `y = x + 3` and `y` appears only here, it eliminates `y` by substituting `x + 3` everywhere.

**`elim-uncnstr`**: Removes variables that appear only once in the formula. A variable that appears in only one constraint has so much freedom that it can usually be assigned any value — so the solver does not need to reason about it at all.

**`qe-light`**: Light-weight quantifier elimination. Removes simple quantified formulas that can be easily resolved.

### Why tactic order matters

Tactics interact. Running `simplify` before `propagate-values` might be less effective than the reverse, because simplification might miss opportunities that only appear after value propagation has removed some variables. Finding the best tactic order for a given class of formulas is an art — and for some tools (like Alive2, the compiler verification tool discussed in the *Z3 Internals* paper), it took significant experimentation to find an order an order of magnitude faster than Z3's defaults.

### Going deeper in the papers
*Programming Z3*, Section 7 ("Tactics") covers tactic basics, how to compose tactics, and parallel solving. *Z3 Internals*, Section 8 provides a comprehensive classification of all Z3 tactics and a fascinating case study of how the Alive2 LLVM verification tool customised its tactic pipeline. Section 8.1 ("A use case of tactics from Alive2") is particularly worth reading — it shows a real engineering team working through the process of optimising SMT performance for their specific application.

---

## 16. How This Connects to the Requirements Engine

### Learning Outcomes
By the end of this section you will understand:
- How each concept in this guide maps to a specific part of the requirements engine
- What Z3 is actually doing when it runs checks on the PR.AA requirements
- How to read the Z3 Python code in `skill_03_smt_solver.py` with new understanding

---

Now that you have the conceptual vocabulary, let us map every Z3 concept back to the requirements engine. Open `skills/skill_03_smt_solver.py` and read it alongside this section.

### `DeclareSort("Entity")` and `DeclareSort("Asset")`
These are **sorts** (Section 4). We are creating two new uninterpreted types. Everything in our model is either an entity (users, services, hardware) or an asset (things that can be accessed). Using separate sorts prevents the solver from accidentally treating them as interchangeable.

### `Function("has_credentials", Entity, BoolSort())`
This is an **uninterpreted predicate** (Section 5). It asks the yes/no question "does this entity have credentials?" The solver does not know *how* credentials work — it only knows the type signature and the axioms we give it.

### `Const("e", Entity)` and `Const("a", Asset)`
These are **free variables** — placeholders used inside `ForAll` statements. They represent "some arbitrary entity" and "some arbitrary asset."

### `ForAll([e], Implies(has_credentials(e), credentials_managed(e)))`
This is a **universally quantified axiom** (Section 6) encoding PR.AA-01. It says: for every entity, having credentials implies those credentials are managed. Z3 will use E-matching and MBQI (Section 14) to reason about this statement.

### `Solver()` and `solver.add(axiom)`
A `Solver` is Z3's interface (Section 2). We create one, load all six requirement axioms into it using `add()`, and then check satisfiability. Internally, Z3 is running CDCL(T) (Section 10) with the EUF theory solver (Section 7) handling the congruence closure (Section 11).

### `solver.check()` returning `sat`
This is the verdict (Section 8). In Checks 2, 3, and 6, we get `sat` when we assert a counterexample. The `sat` means Z3 found a model (Section 12) — a specific scenario — where an entity has access without managed credentials, without identity proofing, etc.

### The findings (`"kind": "GAP"`, `"kind": "AMBIGUITY"`)
These are our interpretations of Z3's verdicts. The solver itself just says `sat` or `unsat`. We interpret the meaning of that verdict based on what question we asked:
- `sat` in response to "can this bad scenario exist?" → GAP
- `sat` in response to "is the undefined predicate inconsistent?" → AMBIGUITY
- `sat` in response to "are all requirements consistent?" → good, no contradiction
- `unsat` would indicate a CONTRADICTION (which does not occur for PR.AA)

---

## 17. Your Reading Path: Where to Go Next in the Papers

### Learning Outcomes
By the end of this section you will understand:
- Which parts of the papers to read first, second, and last
- What level of mathematical background each section assumes
- How to build a reading plan over weeks or months

---

Both papers are available freely online:
- **Programming Z3**: https://z3prover.github.io/papers/programmingz3.html
- **Z3 Internals**: https://z3prover.github.io/papers/z3internals.html

Here is a suggested reading path based on progressive difficulty:

---

### Week 1–2: Foundations (accessible after reading this guide)

**From Programming Z3:**
- Section 1 (Introduction) — you now have the vocabulary to follow this
- Section 2.1–2.3 (Sorts, Signatures, Terms and Formulas) — reinforces Sections 4 and 5 of this guide
- Section 3.1 (EUF) — reinforces Section 7 and 11 of this guide
- Section 4.1–4.5 (Incrementality, Scopes, Models) — reinforces Sections 8 and 12

**Milestone**: you should be able to write simple Z3 Python scripts for logical puzzles, declare sorts and functions, add axioms, and check satisfiability.

---

### Week 3–4: Intermediate (requires Python familiarity)

**From Programming Z3:**
- Section 3.2 (Arithmetic) — introduces the numerical theories
- Section 4.4 and 4.6.6 (Cores and Consequences) — introduces unsat cores from Section 13
- Section 5.1 (Blocking evaluations) — a useful technique for enumerating all solutions
- Section 6.1.1 (CDCL(T)) — reinforces Section 10; includes working Python code

**From Z3 Internals:**
- Section 2.1 (CDCL(T)) — more mathematical but important for deep understanding
- Section 3.1 (Boolean Theories) — how bit-vectors are handled internally

**Milestone**: you should understand the CDCL(T) architecture, be able to extract and interpret models and cores, and write non-trivial Z3 queries.

---

### Week 5–6: Advanced (requires comfort with logic notation)

**From Programming Z3:**
- Section 6.1.3–6.1.4 (E-matching and MBQI) — reinforces Section 14
- Section 7 (Tactics) — reinforces Section 15
- Section 8 (Optimization) — introduces objective functions; useful for requirements with priorities

**From Z3 Internals:**
- Section 3.2 (Equality and Uninterpreted Functions) — the definitive description of congruence closure
- Section 3.3 (Arithmetic) — the full description of Z3's arithmetic solvers
- Section 7 (Quantifiers) — deep treatment of E-matching and MBQI

**Milestone**: you should understand Z3's internal architecture well enough to diagnose performance problems and select appropriate tactics for new problem classes.

---

### Long-term: Research level

**From Z3 Internals:**
- Section 4 (Data-structure and algorithm internals) — implementation details
- Section 5 (Model Construction) — how models are built from satisfying states
- Section 6 (Certificates and Unsatisfiable Cores) — proof production and validation
- Section 8.1 (Alive2 case study) — real-world performance engineering

**Milestone**: you are ready to read research papers on SMT solving, formal verification, and automated reasoning, and potentially to contribute to or extend Z3.

---

### Recommended companion resources

| Resource | Why |
|---|---|
| https://microsoft.github.io/z3guide | Interactive Z3 tutorial in the browser — no installation needed |
| https://yurichev.com/writings/SAT_SMT_by_example.pdf | Hundreds of worked examples using Z3's Python API |
| The Z3 GitHub repository (github.com/z3prover/z3) | Source code, issues, examples, documentation |
| _Logic in Computer Science_ by Huth and Ryan | A university-level textbook that covers propositional and predicate logic thoroughly |

---

*This guide was written to accompany the Requirements Engine project. The source papers it references are written by the creators of Z3 at Microsoft Research and represent the definitive technical documentation for the solver. Working through this guide, then the papers, then modifying the requirements engine to add new checks is a complete self-study path from curious beginner to competent SMT practitioner.*