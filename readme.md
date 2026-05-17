# Requirements Engine
### NIST CSF 2.0 · LLM Rewriting · Formal Logic · SMT Solving

---

## Table of Contents

1. [Why This Exists](#1-why-this-exists)
2. [The Core Problem: Natural Language is Broken for Requirements](#2-the-core-problem-natural-language-is-broken-for-requirements)
3. [What This System Does](#3-what-this-system-does)
4. [Concepts You Need to Understand First](#4-concepts-you-need-to-understand-first)
5. [Pipeline Architecture](#5-pipeline-architecture)
6. [Stage 0 — Source Requirements](#6-stage-0--source-requirements)
7. [Stage 1 — LLM Requirement Rewriting](#7-stage-1--llm-requirement-rewriting)
8. [Stage 2 — Formal Representation](#8-stage-2--formal-representation)
9. [Stage 3 — SMT Solving with Z3](#9-stage-3--smt-solving-with-z3)
10. [Setup and Usage](#10-setup-and-usage)
11. [File Map and Component Reference](#11-file-map-and-component-reference)
12. [Extending the Engine](#12-extending-the-engine)
13. [Limitations and What Comes Next](#13-limitations-and-what-comes-next)

---

## 1. Why This Exists

Cybersecurity frameworks like NIST CSF 2.0 describe desired security outcomes in plain English. That is intentional — the authors want the framework to be readable by executives, auditors, policy writers, and engineers alike. But there is a cost: natural language is imprecise.

When a requirement says *"identities are proofed and bound to credentials based on the context of interactions"*, what does "context" mean? Who exactly must proof what, and when? What is the relationship between proofing and authentication? What happens to a hardware device that has no identity in the traditional sense?

These questions cannot be answered by reading the requirement more carefully. The ambiguity is structural — it is baked into the way natural language works. And in security, ambiguity is an attack surface. If two engineers implement the same requirement differently, the gap between their interpretations may be exactly where a breach occurs.

This engine was built to make that problem visible. It takes NIST CSF 2.0 outcomes through a four-stage pipeline:

1. An LLM rewrites the vague outcome into precise, testable criteria
2. Those criteria are translated into formal mathematical logic
3. An automated reasoning engine (Z3 SMT solver) runs proofs against the logic
4. The findings — gaps, ambiguities, missing implications — are surfaced in plain English

This is not a production compliance tool. It is a learning environment designed to help cybersecurity teams understand *why* natural language requirements fail under formal scrutiny, and what rigorous requirement engineering looks like.

---

## 2. The Core Problem: Natural Language is Broken for Requirements

Consider PR.AA-01:

> *"Identities and credentials for authorized users, services, and hardware are managed by the organization."*

Read it again. Now ask:

- What does "managed" mean? Does it require a CMDB? An IAM system? Manual records?
- "Authorized" — authorized by whom? Before or after credential issuance?
- If a hardware device uses a certificate, is the certificate the "credential"? Is the device the "identity"?
- What happens when a credential expires — is it still "managed"?
- Does "hardware" include IoT sensors? Cloud-based compute instances? Network switches?

None of these questions are answerable from the text. A security auditor checking for compliance will make judgment calls. A different auditor will make different ones. The requirement, as written, does not specify what evidence would constitute a pass or a fail.

This is the requirements engineering problem in security. It is not unique to NIST — it exists in ISO 27001, PCI-DSS, SOC 2, and virtually every framework written for a broad audience. The frameworks are intentionally technology-agnostic and organisation-agnostic, which means they cannot be precise about specifics. But specificity is exactly what implementation and verification require.

**The gap between "what the framework says" and "what your system actually does" is where risk lives.**

Formal methods provide a way to force precision. When you must express a requirement as a logical formula that a computer can reason about, every undefined term becomes an error, every missing link becomes visible, and every contradiction becomes provable.

---

## 3. What This System Does

The engine processes the six NIST CSF 2.0 PR.AA outcomes (Identity Management, Authentication, and Access Control) through four stages:

```
  NIST PR.AA Plain Text
         │
         ▼  Stage 0
  Display source requirements as published
         │
         ▼  Stage 1  [LLM — Claude API]
  Rewrite each outcome into structured SHALL statements
  with subject, object, condition, and testable indicator
         │
         ▼  Stage 2  [LLM — Claude API]
  Translate each rewritten requirement into:
    (a) Pseudo-logic  ∀ e ∈ Entity: has_credentials(e) → credentials_managed(e)
    (b) SMT-LIB2      (assert (forall ((e Entity)) (=> (has-credentials e) ...)))
         │
         ▼  Stage 3  [Z3 SMT Solver — Python API]
  Run six automated proofs against a formal domain model.
  Surface: consistency checks, gaps, ambiguities, broken implication chains.
         │
         ▼
  Terminal summary: findings by type, recommendations
```

Each stage is a discrete, independently runnable Python script. You can run the full pipeline or drop into any individual stage to study it in isolation.

---

## 4. Concepts You Need to Understand First

### NIST CSF 2.0

The NIST Cybersecurity Framework (CSF) 2.0 is a voluntary framework published by the US National Institute of Standards and Technology. It organises cybersecurity activities into six core functions:

- **Govern** — organisational cybersecurity risk management
- **Identify** — understanding assets and risks
- **Protect** — safeguards to manage risk
- **Detect** — finding cybersecurity events
- **Respond** — taking action after an event
- **Recover** — restoring capabilities after an incident

Each function contains categories, and each category contains outcomes — specific results that represent good cybersecurity practice. The outcomes are intentionally high-level. NIST does not prescribe *how* to achieve them; it describes *what* good looks like.

This engine focuses on the **PR.AA category** (Protect: Identity Management, Authentication, and Access Control), which contains six outcomes (PR.AA-01 through PR.AA-06). These outcomes form a logical cluster — they collectively describe how access to assets should be controlled — making them a good test case for cross-requirement analysis.

### Formal Methods

Formal methods is a field of computer science and mathematics concerned with specifying, developing, and verifying software and systems using mathematically rigorous techniques. The core idea is to express system properties as logical formulas, then use automated tools to check whether those formulas hold.

Formal methods have been applied successfully in:
- Aviation (flight control systems)
- Railway signalling (level crossing controllers)
- Cryptographic protocols (TLS verification)
- Microprocessor design (Intel's floating point units after the Pentium FDIV bug)
- Smart contracts and blockchain protocols

In security, formal methods are increasingly used to verify protocol correctness (e.g. the ProVerif and Tamarin tools for cryptographic protocol verification) and to analyse policy logic (e.g. automated analysis of firewall rules or access control policies).

This engine applies formal methods at the *requirements* level rather than the implementation level. Instead of verifying that a system correctly implements a requirement, we ask whether the requirements themselves are logically sound when read together.

### Satisfiability Modulo Theories (SMT)

A **satisfiability problem** asks: given a logical formula, does there exist an assignment of values to its variables that makes the formula true? The classic version is SAT (propositional satisfiability), which works with Boolean variables and connectives (AND, OR, NOT).

**SMT** extends SAT by adding background *theories* — mathematical structures with their own axioms and operations. Common SMT theories include:

- **Equality and uninterpreted functions** — functions with no defined meaning, just a name and a type signature. This is what this engine primarily uses.
- **Linear arithmetic** — reasoning about linear inequalities over integers or reals
- **Arrays** — reasoning about memory-like read/write structures
- **Bitvectors** — fixed-width integers, useful for hardware and low-level software

SMT solvers are decision procedures for these combined theories. Given a formula, an SMT solver will determine whether it is:

- **SAT** (satisfiable) — there exists some world in which the formula is true
- **UNSAT** (unsatisfiable) — no assignment of values can make the formula true; it is a logical contradiction
- **UNKNOWN** — the solver could not decide within its limits (rare for the theories used here)

The power of SMT for requirements analysis lies in how we frame questions:

- To check if two requirements **contradict** each other: encode both as axioms, add an assertion, and check satisfiability. If UNSAT, the combination is impossible — a contradiction.
- To check if a requirement **implies** a property: negate the property, add it to the axioms, check satisfiability. If UNSAT, the property always holds (the negation is impossible). If SAT, the property is not guaranteed — you have found a gap.
- To check if a term is **undefined**: show that the predicate representing it can simultaneously be true and false without violating any axiom. If SAT, the term is unconstrained — an ambiguity.

This encoding pattern is used in all six checks in this engine.

### Z3

Z3 is an SMT solver developed by Microsoft Research. It is one of the most widely used solvers in both academia and industry. Z3 supports Boolean satisfiability, quantifier-free and quantified first-order logic, linear arithmetic, bitvectors, arrays, and uninterpreted functions and sorts.

Z3 has a Python API (`z3-solver` on PyPI) that allows you to construct formulas programmatically using Python objects rather than writing SMT-LIB2 text. This engine uses the Python API for the actual solving, and uses the LLM to generate SMT-LIB2 text for educational display.

The central Z3 constructs used in this engine:

| Z3 construct | What it is | Example |
|---|---|---|
| `DeclareSort("X")` | An uninterpreted sort (type) | `Entity = DeclareSort("Entity")` |
| `Function("f", A, B)` | An uninterpreted function from sort A to sort B | `has_credentials = Function("has_credentials", Entity, BoolSort())` |
| `Const("x", A)` | A constant (free variable) of sort A | `e = Const("e", Entity)` |
| `ForAll([x], P(x))` | Universal quantification: P holds for all x | `ForAll([e], Implies(has_credentials(e), ...))` |
| `Implies(P, Q)` | Logical implication: if P then Q | — |
| `And(P, Q)` | Logical conjunction | — |
| `Not(P)` | Logical negation | — |
| `Solver()` | A solver instance that holds axioms | — |
| `solver.add(axiom)` | Assert an axiom into the solver | — |
| `solver.check()` | Run the solver; returns `sat`, `unsat`, or `unknown` | — |

---

## 5. Pipeline Architecture

```
requirements-engine/
│
├── run.py                      Orchestrator. Calls each stage in sequence.
│
├── data/
│   └── requirements.py         NIST PR.AA source data as a Python dict.
│                               Edit here to add or change requirements.
│
├── skills/
│   ├── skill_01_rewriter.py    Stage 1: LLM rewriting via Claude API.
│   │                           Input:  raw NIST requirement text
│   │                           Output: structured SHALL statements (JSON)
│   │
│   ├── skill_02_formalizer.py  Stage 2: LLM formalisation via Claude API.
│   │                           Input:  rewritten SHALL statements (from Stage 1)
│   │                           Output: pseudo-logic + SMT-LIB2 per requirement
│   │
│   └── skill_03_smt_solver.py  Stage 3: Z3 automated reasoning.
│                               Input:  SMT-LIB2 snippets (display only)
│                               Output: findings — gaps, ambiguities, contradictions
│
├── utils/
│   └── terminal.py             ANSI colour helpers, banner, finding formatters.
│                               No logic here — display only.
│
├── AGENT.md                    Claude Code agent instructions.
└── requirements.txt            Python dependencies: anthropic, z3-solver
```

The design principle is **separation of concerns**: each skill knows only its own stage. Skills do not call each other (except when run standalone, where the prerequisite is run automatically). The orchestrator in `run.py` wires them together and handles all display flow.

Each skill is independently invokable. This is intentional — it lets your team pause the pipeline at any stage to study the transformation in isolation.

---

## 6. Stage 0 — Source Requirements

The pipeline begins by loading and displaying the six NIST CSF 2.0 PR.AA requirements exactly as published. No transformation yet — just the raw text.

The requirements are stored in `data/requirements.py` as a structured Python dict. Each requirement has an `id` and a `text` field. The category-level metadata (domain, category name, description) is also stored here.

**PR.AA-01** — Identities and credentials for authorized users, services, and hardware are managed by the organization

**PR.AA-02** — Identities are proofed and bound to credentials based on the context of interactions

**PR.AA-03** — Users, services, and hardware are authenticated

**PR.AA-04** — Identity assertions are protected, conveyed, and verified

**PR.AA-05** — Access permissions, entitlements, and authorizations are defined in a policy, managed, enforced, and reviewed, and incorporate the principles of least privilege and separation of duties

**PR.AA-06** — Physical access to assets is managed, monitored, and enforced commensurate with risk

Read these carefully. Before you look at the analysis, try to identify: Which terms are undefined? Which requirements cross-reference each other implicitly? Where are the passive-voice constructions that hide who is responsible? The analysis in Stage 3 will make your intuitions precise.

---

## 7. Stage 1 — LLM Requirement Rewriting

**File:** `skills/skill_01_rewriter.py`
**Dependency:** Claude API (`ANTHROPIC_API_KEY`)
**Input:** `data/requirements.py`
**Output:** A list of JSON objects, one per requirement

### What the LLM does

The Claude API is given a system prompt that instructs it to act as a requirements engineer. For each NIST outcome, it produces a set of SHALL statements — a writing style drawn from IEEE 830, RFC 2119, and defence acquisition standards, where "SHALL" denotes a mandatory requirement.

Each SHALL statement is structured with five fields:

- **statement** — the requirement itself, in imperative form ("The organization SHALL...")
- **subject** — who or what bears the obligation
- **object** — what resource, asset, or entity is controlled
- **condition** — the circumstances under which the requirement applies
- **testable_indicator** — observable evidence that the statement has been satisfied

The testable indicator is the most important field for compliance purposes. A requirement without one cannot be audited — you cannot tell whether it has been met. The rewriting stage forces this evidence to be made explicit.

### Why structured JSON output

The system prompt instructs Claude to return valid JSON only. This is intentional. Structured output:

1. Passes cleanly to Stage 2 without manual parsing
2. Forces the LLM to be explicit about each field rather than burying obligations in flowing prose
3. Is diffable — you can compare two runs to see how the rewriting changes between API calls

### Example transformation

Original (PR.AA-01):
> *"Identities and credentials for authorized users, services, and hardware are managed by the organization."*

Rewritten (example output):
```json
{
  "id": "PR.AA-01.1",
  "statement": "The organization SHALL maintain a complete, current inventory of all identities and their associated credentials for human users, automated services, and hardware devices.",
  "subject": "Organization (Identity Management function)",
  "object": "All identities and credentials across users, services, and hardware",
  "condition": "At all times; inventory must be updated within 24 hours of any identity or credential lifecycle event",
  "testable_indicator": "IAM system or CMDB audit showing 100% coverage of active identities; reconciliation report showing no unregistered identities"
}
```

The rewriting is not perfect — LLMs introduce their own assumptions. Stage 3 will surface some of those. But the transformation from passive, unconstrained prose to active, structured, testable criteria is already a significant improvement.

---

## 8. Stage 2 — Formal Representation

**File:** `skills/skill_02_formalizer.py`
**Dependency:** Claude API (`ANTHROPIC_API_KEY`)
**Input:** Output of Stage 1 (rewritten SHALL statements)
**Output:** Two formal representations per requirement — pseudo-logic and SMT-LIB2

All six requirements are sent to Claude in a single API call. This matters because formal logic requires consistent naming — if PR.AA-01 introduces a predicate called `has_credentials` and PR.AA-02 also talks about credentials, both must use the same predicate name. Sending all requirements together allows the model to maintain that consistency.

### Pseudo-Logic

Pseudo-logic uses standard mathematical notation from first-order logic (FOL). It is not executable by any tool — it is a human-readable intermediate between natural language and machine-parseable syntax.

The notation:

| Symbol | Meaning | Example |
|---|---|---|
| `∀` | For all (universal quantification) | `∀ e ∈ Entity` — for every entity |
| `∃` | There exists (existential quantification) | `∃ a ∈ Asset` — some asset exists |
| `→` | Implies | `P → Q` — if P then Q |
| `∧` | And (conjunction) | `P ∧ Q` — both P and Q |
| `∨` | Or (disjunction) | `P ∨ Q` — P or Q or both |
| `¬` | Not (negation) | `¬P` — not P |

A **sort** (also called a type) is a named collection of things. In this domain, we have two primary sorts: `Entity` (users, services, hardware) and `Asset` (things that can be accessed). Sorts let us write formulas that say "for all entities" without listing every entity individually.

A **predicate** is a function that maps one or more sorts to a Boolean (true or false). `has_credentials(e)` is a predicate that is true if entity `e` has credentials. `has_access(e, a)` is a binary predicate that is true if entity `e` has access to asset `a`.

Example pseudo-logic for PR.AA-01:
```
∀ e ∈ Entity:
  has_credentials(e) → credentials_managed(e)
```

Read as: *"For every entity, if that entity has credentials, then those credentials are managed."*

### SMT-LIB2

SMT-LIB2 is the standard input language for SMT solvers, including Z3. It is a Lisp-like language based on S-expressions (nested parentheses). The same formula in SMT-LIB2:

```smt2
; Declare the Entity sort (an uninterpreted type)
(declare-sort Entity 0)

; Declare predicates as functions to Bool
(declare-fun has-credentials (Entity) Bool)
(declare-fun credentials-managed (Entity) Bool)

; PR.AA-01: if an entity has credentials, they must be managed
(assert
  (forall ((e Entity))
    (=> (has-credentials e)
        (credentials-managed e))))
```

The `0` in `(declare-sort Entity 0)` means the sort takes zero type parameters (it is not a generic type). The `=>` is SMT-LIB2's implication operator. `forall` introduces a universally quantified variable.

**Note:** The SMT-LIB2 generated by Stage 2 is displayed for educational purposes. The actual proofs in Stage 3 use the Z3 Python API, which constructs the same logical structures programmatically. The two representations are semantically equivalent — the Python API is just more ergonomic for a Python-based pipeline.

### Why show both representations

Pseudo-logic is readable by anyone with basic mathematical literacy. SMT-LIB2 is what the solver actually ingests. Displaying both side-by-side teaches the connection between human-readable formal notation and machine-parseable syntax — a translation that formal methods practitioners perform constantly.

---

## 9. Stage 3 — SMT Solving with Z3

**File:** `skills/skill_03_smt_solver.py`
**Dependency:** `z3-solver` Python package (no API key needed)
**Input:** SMT-LIB2 snippets from Stage 2 (displayed as reference); domain model is built internally
**Output:** Six findings — gaps, ambiguities, consistency results

### The Domain Model

Before running checks, the solver needs a formal model of the PR.AA domain. This model is built in `build_model()` and consists of two parts.

**Sorts** — the types of things in our world:
- `Entity` — encompasses users, services, and hardware (PR.AA-01 treats all three as having identities and credentials)
- `Asset` — physical or logical resources that can be accessed

**Predicates** — the properties and relationships we want to reason about:

| Predicate | Type signature | Meaning |
|---|---|---|
| `has_credentials` | Entity → Bool | Entity has credentials on record |
| `credentials_managed` | Entity → Bool | Those credentials are actively managed |
| `identity_proofed` | Entity → Bool | The entity's identity has been proofed |
| `identity_bound` | Entity → Bool | Identity has been bound to credentials |
| `is_authenticated` | Entity → Bool | Entity has been authenticated |
| `assertion_protected` | Entity → Bool | Identity assertions are protected |
| `assertion_verified` | Entity → Bool | Identity assertions are verified |
| `has_access` | Entity × Asset → Bool | Entity has access to an asset |
| `access_authorized` | Entity × Asset → Bool | That access is authorised |
| `access_in_policy` | Entity × Asset → Bool | Access is defined in a policy |
| `least_privilege_applied` | Entity × Asset → Bool | Least privilege applies |
| `sep_of_duties_applied` | Entity × Asset → Bool | Separation of duties applies |
| `access_reviewed` | Entity × Asset → Bool | Access has been reviewed |
| `is_physical_asset` | Asset → Bool | Asset is physical (not logical) |
| `physical_access_monitored` | Entity × Asset → Bool | Physical access is monitored |
| `risk_assessed` | Asset → Bool | Asset's risk has been assessed |

**Axioms** — the six requirements, encoded as universally-quantified implications:

```python
# PR.AA-01
ForAll([e], Implies(has_credentials(e), credentials_managed(e)))

# PR.AA-02
ForAll([e], Implies(has_credentials(e), And(identity_proofed(e), identity_bound(e))))

# PR.AA-03
ForAll([e, a], Implies(has_access(e, a), is_authenticated(e)))

# PR.AA-04
ForAll([e], Implies(is_authenticated(e), And(assertion_protected(e), assertion_verified(e))))

# PR.AA-05
ForAll([e, a], Implies(has_access(e, a),
    And(access_in_policy(e, a), access_authorized(e, a),
        least_privilege_applied(e, a), sep_of_duties_applied(e, a), access_reviewed(e, a))))

# PR.AA-06
ForAll([e, a], Implies(And(is_physical_asset(a), has_access(e, a)),
    And(physical_access_monitored(e, a), risk_assessed(a))))
```

### The Six Checks

Each check creates a fresh solver instance loaded with all six axioms, then adds additional assertions representing the scenario being tested.

---

#### Check 1 — Global Consistency

**Question:** Are all six requirements simultaneously satisfiable?

**Method:** Load all axioms into the solver. Call `check()`. If SAT, the requirements are consistent — there exists at least one possible world where all of them hold simultaneously.

**Expected result:** SAT

**Why this matters:** If the result were UNSAT, the requirements would contradict each other — no real-world system could satisfy all of them at once. That would be a critical finding requiring the framework authors to revise the requirements. The SAT result here is reassuring: the PR.AA requirements, as formally modelled, are not self-contradictory.

---

#### Check 2 — Authentication ↛ Credential Management

**Question:** Can an entity be authenticated without having managed credentials?

**Method:**
```python
solver.add(is_authenticated(e))         # entity is authenticated
solver.add(Not(has_credentials(e)))     # but has no credentials on record
```

**Expected result:** SAT (gap found)

**The gap:** PR.AA-03 requires authentication for access. PR.AA-01 requires credential management. But neither requirement says *authentication implies having credentials*. Z3 finds a satisfying model where an entity is authenticated (perhaps via a hardware token not registered in IAM, or a cached session) without appearing in the organisation's identity store.

**Real-world implication:** Service accounts, embedded system credentials, or hardware certificates provisioned outside the standard IAM process can be authenticated under PR.AA-03 while remaining invisible to the credential management controls of PR.AA-01. This is a common attack vector: shadow credentials that bypass the managed inventory.

**Missing axiom that would close the gap:**
```python
ForAll([e], Implies(is_authenticated(e), has_credentials(e)))
```

---

#### Check 3 — Access ↛ Identity Proofing

**Question:** Does having access to an asset guarantee that the accessing entity's identity was proofed?

**Method:**
```python
solver.add(has_access(e, a))            # entity has access
solver.add(Not(identity_proofed(e)))    # identity was never proofed
```

**Expected result:** SAT (gap found)

**The broken chain:** Trace the logic as written:
- `has_access(e, a)` → `is_authenticated(e)` (via PR.AA-03)
- `has_credentials(e)` → `identity_proofed(e)` (via PR.AA-02)

There is no axiom connecting `is_authenticated` to `has_credentials`. The proofing guarantee hangs off credential possession, but access only requires authentication. If an entity can be authenticated without possessing credentials (as Check 2 showed), then PR.AA-02's proofing requirement is unreachable from the access path for some entities.

**Real-world implication:** A user who accesses a system via a federated identity from a third-party provider might be "authenticated" in the technical sense, but their identity proofing occurred at the IdP, not under the organisation's control. PR.AA-02's requirement that *the organisation* proof identities may not be satisfied, but the access is technically compliant with PR.AA-03.

---

#### Check 4 — Separation of Duties Is Undefined

**Question:** Is `sep_of_duties_applied` a meaningful, constrained predicate, or is it vacuously asserted?

**Method:**
```python
e2 = Const("e2", Entity)
a2 = Const("a2", Asset)
solver.add(sep_of_duties_applied(e, a))         # SoD applies here
solver.add(Not(sep_of_duties_applied(e2, a2)))  # but not here
```

**Expected result:** SAT (ambiguity found)

**The ambiguity:** PR.AA-05 mandates that access controls "incorporate the principles of... separation of duties." In the formal model, `sep_of_duties_applied` is an *uninterpreted function* — it has a type signature but no axioms defining what makes it true or false. Z3 can simultaneously satisfy `sep_of_duties_applied(e, a) = True` and `sep_of_duties_applied(e2, a2) = False` without any contradiction, because nothing in the requirements constrains the predicate's meaning.

This is the formal equivalent of asking Z3 to check a requirement that says "the organisation SHALL apply X" without ever defining what X is. The solver can satisfy the formula in infinitely many ways, none of which correspond to a real security control.

**Real-world implication:** "Separation of duties" means different things in different contexts. In financial controls, it means no single person can both initiate and approve a transaction. In system administration, it means no one person can both write code and deploy it to production. The requirement, as written, does not say which meaning applies, how many roles must be separated, or what constitutes a conflicting duty.

---

#### Check 5 — Physical/Logical Access Boundary Ambiguity

**Question:** Does PR.AA-05's policy requirement cover physical access, or only logical access?

**Method:**
```python
solver.add(is_physical_asset(a))        # asset is physical
solver.add(has_access(e, a))            # entity has access to it
solver.add(Not(access_in_policy(e, a))) # but that access is not in policy
```

**Expected result:** UNSAT in this model (which surfaces the ambiguity)

**The ambiguity:** In this model, `has_access` is a single universal predicate covering both physical and logical access. Therefore, PR.AA-05's axiom applies to all access, and the check returns UNSAT — physical access without a policy is impossible.

But this is a *modelling choice*, not a fact about the requirements. The natural language of PR.AA-05 talks about "access permissions, entitlements, and authorizations" — language that typically refers to logical access in IAM systems. PR.AA-06 is the requirement that specifically addresses physical access. An organisation that models these as *separate predicates* (`has_logical_access` vs `has_physical_access`) would find that PR.AA-05 applies only to the former — and physical access would have no policy requirement, only a monitoring requirement under PR.AA-06.

**The finding:** The boundary between PR.AA-05 and PR.AA-06 is formally ambiguous. Organisations can derive a gap or not, depending on how they model "access." This is precisely the kind of interpretive ambiguity that leads to inconsistent implementations across organisations certified to the same framework.

---

#### Check 6 — Full Access Guarantee Chain

**Question:** Comprehensively, what does having access to an asset actually guarantee about the entity that has access?

**Method:**
```python
solver.add(has_access(e, a))
solver.add(Not(credentials_managed(e)))     # assert this is NOT guaranteed
```

**Expected result:** SAT (the guarantee is absent — gap confirmed)

**The chain analysis:** This check synthesises the findings from all previous checks into a complete audit of the access guarantee chain.

What `has_access(e, a)` **does** guarantee (via the axiom chain):

```
has_access(e, a)
    │
    ├─[PR.AA-03]─→  is_authenticated(e)
    │                   │
    │               [PR.AA-04]─→  assertion_protected(e)
    │                             assertion_verified(e)
    │
    └─[PR.AA-05]─→  access_in_policy(e, a)
                    access_authorized(e, a)
                    least_privilege_applied(e, a)
                    sep_of_duties_applied(e, a)   ← defined but unconstrained (Check 4)
                    access_reviewed(e, a)
```

What `has_access(e, a)` **does not** guarantee:
- `has_credentials(e)` — no axiom links authentication to credential possession
- `credentials_managed(e)` — cannot reach this without the above link
- `identity_proofed(e)` — cannot reach this without credentials

The credential and proofing requirements (PR.AA-01, PR.AA-02) exist in the framework but are disconnected from the access enforcement chain (PR.AA-03 through PR.AA-06). An implementation can be fully compliant with the latter group while leaving the former as dead letters for some classes of entities.

---

### Reading the Findings

| Symbol | Kind | What it means | Z3 result |
|---|---|---|---|
| ✅ | SAT | No contradiction or gap at this check | `sat` (desired here) |
| ⚠️  | GAP | A required implication between requirements is missing | `sat` (counterexample exists) |
| 🔍 | AMBIGUITY | A predicate is formally undefined or unconstrained | `sat` (vacuously satisfiable) |
| ❌ | UNSAT | A contradiction — two requirements conflict | `unsat` (unexpected here) |

The finding type is determined by what the check is testing. A SAT result is sometimes good (Check 1 — consistency is desired) and sometimes bad (Checks 2, 3, 6 — a counterexample to a desired property exists). The check's docstring always explains which interpretation applies.

---

## 10. Setup and Usage

### Prerequisites

- Python 3.11 or later
- An Anthropic API key (for Stages 1 and 2 only)

### Install

```bash
git clone <repo>
cd requirements-engine
pip install -r requirements.txt
```

### Set your API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Run the full pipeline

```bash
python run.py
```

### Run offline — Z3 only, no API calls

Stages 1 and 2 are replaced with stub data. Stage 3 runs with real Z3 proofs. Useful for air-gapped environments, demos, or studying the solver in isolation.

```bash
python run.py --no-llm
```

### Run a single skill

Each skill is independently executable. Skills 1 and 2 require an API key. Skill 3 has no external dependencies beyond `z3-solver`.

```bash
# Stage 1 only: LLM rewriting
python skills/skill_01_rewriter.py

# Stage 2 only: formal logic generation (runs Stage 1 automatically as prerequisite)
python skills/skill_02_formalizer.py

# Stage 3 only: Z3 solver (no API key, no prerequisites)
python skills/skill_03_smt_solver.py
```

### Claude Code orchestration

If you are using Claude Code (the CLI agent), the `AGENT.md` file contains full instructions for orchestrating the pipeline. Claude Code can run individual skills, add new requirements, add new Z3 checks, and swap in different NIST categories.

---

## 11. File Map and Component Reference

```
requirements-engine/
│
├── run.py
│     Orchestrator. Calls Stages 0–3 in sequence.
│     Accepts --no-llm flag to skip API calls.
│     Entry point for the full pipeline.
│
├── AGENT.md
│     Claude Code agent instructions.
│     Describes tasks, extension patterns, command reference.
│
├── requirements.txt
│     anthropic>=0.25.0   — Claude API client
│     z3-solver>=4.12.0   — Z3 SMT solver Python bindings
│
├── data/
│   └── requirements.py
│         NIST_PR_AA dict with framework metadata and six requirements.
│         Edit here to add requirements or swap NIST categories.
│
├── skills/
│   ├── skill_01_rewriter.py
│   │     Calls Claude API with a structured system prompt.
│   │     Returns: list of rewritten requirement dicts (JSON).
│   │     System prompt enforces: SHALL statements, five required fields,
│   │     JSON-only output, atomic conditions.
│   │
│   ├── skill_02_formalizer.py
│   │     Calls Claude API with all rewritten requirements in one call
│   │     (to ensure consistent predicate naming across requirements).
│   │     Returns: list of formal representation dicts, each with
│   │     pseudo_logic, smt_lib2, sorts_used, predicates_used.
│   │
│   └── skill_03_smt_solver.py
│         build_model(): declares sorts, predicates, and six axioms using Z3 Python API.
│         check_01 – check_06: individual proof functions, each returning a finding dict.
│         run(): executes all checks, optionally displaying SMT-LIB2 reference.
│         CHECKS list: controls which checks run and in what order.
│         CHECK_REQUIREMENT_MAP: maps each check to its PR.AA scope for display.
│
└── utils/
    └── terminal.py
          ANSI colour constants and formatting helpers.
          print_banner(), print_stage(), print_finding(), print_summary()
          print_smt_block(): renders a bordered code block with colour
          print_shall(): renders structured SHALL statements
          No business logic — display only.
```

---

## 12. Extending the Engine

### Add a new Z3 check

Open `skills/skill_03_smt_solver.py`. Write a function with this signature:

```python
def check_07_my_new_check(m: dict) -> dict:
    """
    Describe what you are testing and why.
    State the expected result and what it means.
    """
    e, a = m["e"], m["a"]
    s = _solver_with_axioms(m["axioms"])

    # To check if property P is guaranteed by the axioms:
    # Assert Not(P) and check satisfiability.
    # If UNSAT: P is always guaranteed.
    # If SAT:   P is not guaranteed — counterexample exists (gap).
    s.add(m["has_access"](e, a))
    s.add(Not(m["some_predicate"](e)))

    result = s.check()
    if result == sat:
        return {
            "kind": "GAP",     # GAP | AMBIGUITY | UNSAT | SAT
            "check": "Short description of this check",
            "detail": "Detailed explanation of the finding and real-world implications.",
        }
    return {
        "kind": "SAT",
        "check": "Short description",
        "detail": "No gap found — property is guaranteed.",
    }
```

Then register it:

```python
CHECKS = [
    check_01_global_consistency,
    # ...
    check_07_my_new_check,
]

CHECK_REQUIREMENT_MAP = {
    # ...
    check_07_my_new_check: "PR.AA-03 × PR.AA-05",
}
```

### Add a new predicate to the domain model

In `build_model()`, declare a new `Function` and add it to the returned dict:

```python
time_limited_access = Function("time_limited_access", Entity, Asset, BoolSort())

return {
    # ... existing entries ...
    "time_limited_access": time_limited_access,
}
```

### Add a new requirement axiom

Add the axiom to the `axioms` list in `build_model()`, then run Check 1 to confirm global consistency is maintained:

```python
ax_new = ForAll(
    [e, a],
    Implies(
        And(high_risk_asset(a), has_access(e, a)),
        time_limited_access(e, a),
    ),
)

axioms = [ax_pr_aa_01, ax_pr_aa_02, ..., ax_new]
```

### Swap to a different NIST category

1. Create `data/requirements_detect.py` following the same structure as `data/requirements.py`, populated with outcomes from another CSF category (e.g. DE.CM — Continuous Monitoring).
2. Update the import in `run.py`: `from data.requirements_detect import NIST_DE_CM as NIST_PR_AA`
3. Rebuild the domain model in `skill_03_smt_solver.py` for the new category's concepts.
4. Design new checks relevant to that category's logical structure.

---

## 13. Limitations and What Comes Next

### Limitations of this engine

**The formal model is a hand-crafted approximation.** The Z3 domain model in Stage 3 represents one reasonable interpretation of PR.AA. Different formal modellers would make different choices about which predicates to include, how to decompose compound concepts, and what the axioms should say. The findings are real, but they reflect *this model* — not a unique ground truth about the requirements.

**LLM output is non-deterministic.** Stages 1 and 2 will produce slightly different output on each run. The structure is stable (the JSON schema is enforced by the prompt), but the specific wording of SHALL statements and the exact pseudo-logic notation will vary. Treat each run as one analysis, not a canonical answer.

**The SMT-LIB2 from Stage 2 is for display only.** The Stage 3 solver uses the Z3 Python API, not the LLM-generated SMT-LIB2. Using LLM-generated SMT-LIB2 directly would introduce syntax errors and hallucinated predicate names that cause the solver to fail. A production system would need a validation step — either a parser that checks the LLM output before passing it to Z3, or constrained generation that guarantees syntactic validity.

**Uninterpreted functions are a simplification.** Real access control systems have complex structure: role hierarchies, attribute-based policies, temporal constraints, delegation chains. This model treats all predicates as uninterpreted (no internal structure), which means it cannot reason about whether "least privilege" is satisfied given a specific role assignment. More expressive modelling would require richer theories.

**This engine does not verify implementations.** It analyses requirements, not systems. Formal verification of an actual access control implementation would require a different approach — typically model checking (exploring all system states) or deductive verification (proving implementation code meets a specification).

### What comes next

**Feedback loop.** The gaps and ambiguities found in Stage 3 could be fed back into Stage 1 as additional constraints — iterating the rewriting process until the formal model is gap-free. Each finding would generate a new sub-requirement, which is rewritten, formalised, and re-checked.

**Cross-category analysis.** The most interesting findings often sit at the boundary between NIST categories. For example, the boundary between PR.AA (identity and access) and DE.CM (continuous monitoring) has its own implicit dependencies. Extending the engine to load multiple categories and check their interactions would reveal inter-category gaps.

**LLM-generated Z3 Python code.** A more sophisticated Stage 2 could instruct the LLM to generate executable Z3 Python code, validate it with a syntax checker, and pass it directly to Stage 3. This would make the pipeline fully dynamic — any requirement could generate its own checks, not just the pre-designed six.

**Model-based test generation.** Once a formal model exists, Z3 can generate concrete test cases by producing satisfying models. After a SAT result, Z3's `model()` call returns specific values that satisfy the formula — these could be translated into test scenarios for a real access control system.

**Integration with policy languages.** Formal access control models like RBAC and ABAC have their own formal representations. Linking this engine's output to a concrete policy language (XACML, Open Policy Agent's Rego, Cedar) would bridge the gap between requirement analysis and implementation, closing the loop from framework outcome to verifiable policy.