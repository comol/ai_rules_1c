---
name: mermaid-diagrams
description: "Mermaid diagrams that render across viewers and stay agent-parseable. Use when drawing a flowchart, sequence, state or other diagram in Markdown or docs."
---

# Mermaid Diagrams Skill

## Compatibility Rules (Read First)
- Prefer `graph LR`/`graph TB` for flowcharts; some renderers fail on `flowchart` keyword.
- Quote labels containing spaces/special characters: `A["Text (x|y) |"]`.
- **Do not use literal `\n` inside labels** — Mermaid does not interpret such line breaks. Use `<br/>` for line breaks.
- Advanced types like `quadrantChart`, `sankey-beta`, `requirementDiagram`, `gitGraph` may not be available. Use provided flowchart fallbacks.
- Code fences must start at column 0 with language `mermaid`.

## ASCII/Unicode Sidecar (Human-Readable Raw Markdown)
To optimize for quick human scanning in raw Markdown and robust parsing by agents, always ship an ASCII/Unicode sidecar immediately below each Mermaid block.

Policy:
- MUST include a monospace, text-only diagram right under the Mermaid block using fenced code with language `text`.
- MUST keep Mermaid and sidecar in sync (same nodes/edges, same labels where feasible). If they diverge, treat Mermaid as the source of truth and update the sidecar.
- SHOULD limit width to ~80 columns for readability in diffs and terminals.
- SHOULD use simple line art characters (ASCII first; Unicode box-drawing optional when environment supports it).
- MAY add a one-line caption above the pair: `Diagram: <name> (<type>)`.

Recommended primitives:
- Boxes: `[Name]`, `(Name)`, `+-----+\n| N |\n+-----+`
- Flows: `-->`, decisions as `{cond?}` lines, lists with `-`.
- Sequence (text-based): `Actor -> Actor: message` with indented lifelines.

Example (Flowchart):
```mermaid
graph LR
  A["Start"] --> B{Auth?}
  B -->|Yes| C["Dashboard"]
  B -->|No|  D["Login"]
```
```text
Diagram: Auth flow (flowchart)
  [Start] --> {Auth?}
      {Auth?} -- Yes --> [Dashboard]
      {Auth?} -- No  --> [Login]
```

Example (Text-based Sequence):
```mermaid
sequenceDiagram
  participant U as User
  participant W as WebApp
  U->>W: Open
  W-->>U: OK
```
```text
Diagram: Happy path (sequence)
  User -> WebApp : Open
  WebApp -> User : OK
```

## Working Templates (Renderer-Compatible)

### Flowchart
```mermaid
graph LR
  A["Start"] --> B{Auth?}
  B -->|Yes| C["Dashboard"]
  B -->|No|  D["Login"]
  C --> E["Settings"]
```

### Sequence
```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant W as WebApp
  participant API
  U->>W: Open
  W->>API: GET /status
  API-->>W: 200
  W-->>U: OK
```

### Class
```mermaid
classDiagram
  class User {
    +String id
    +String name
    +login(): bool
  }
  class Order {
    +String id
    +Decimal total
    +submit()
  }
  User "1" o-- "*" Order
```

### State (v2)
```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Loading : fetch
  Loading --> Ready : ok
  Loading --> Error : fail
  state Ready {
    [*] --> Viewing
    Viewing --> Editing : edit
    Editing --> Viewing : save
  }
  Error --> Idle : retry
```

### ER (Entity-Relationship)
```mermaid
erDiagram
  USER ||--o{ ORDER : places
  ORDER ||--|{ ORDER_LINE : contains
  PRODUCT ||--o{ ORDER_LINE : referenced
  USER {
    string id
    string email
  }
  PRODUCT {
    string id
    string name
    float price
  }
```

### Journey (User Journey)
```mermaid
journey
  title Checkout UX
  section Browse
    "See product": 5: User
    "Add to cart": 4: User
  section Payment
    "Enter card": 2: User
    "3DS confirm": 2: User
  section Result
    "Success page": 5: User
```

### Gantt
```mermaid
gantt
  title Release Plan
  dateFormat  YYYY-MM-DD
  section Dev
  Spec  :done,   des1, 2025-10-01,2025-10-05
  Impl  :active, des2, 2025-10-06,2025-10-20
  Tests :        des3, 2025-10-21, 7d
  section Release
  Freeze :milestone, m1, 2025-10-28, 0d
  Deploy :crit,    des4, 2025-10-29, 1d
```

### Pie (compatible syntax)
```mermaid
pie
  title Traffic by Source
  "Direct"  : 35
  "Organic" : 45
  "Ads"     : 20
```

### Quadrant — flowchart fallback
```mermaid
graph TB
  Q1["Quick Wins<br/>High Impact - Low Effort<br/><br/>- Improve UX"]
  Q2["Major Projects<br/>High Impact - High Effort<br/><br/>- Rewrite Core"]
  Q3["Fill-ins<br/>Low Impact - Low Effort<br/><br/>- Docs polish"]
  Q4["Thankless<br/>Low Impact - High Effort<br/><br/>- Legacy migration"]

  Q1 --> Q2
  Q1 --> Q3
  Q2 --> Q4
  Q3 --> Q4
```

### Requirement — flowchart fallback
```mermaid
graph LR
  R1["Requirement: PCI-DSS compliant"]
  T1["Test: PCI checklist"]
  SVC["Service"]

  SVC -- satisfies --> R1
  T1  -- verifies  --> R1
```

### Sankey — flowchart fallback (weights on edges)
```mermaid
graph LR
  Checkout["Checkout"] -->|100| PSP["PSP"]
  PSP -->|60|  Settled["Settled"]
  PSP -->|40|  Declined["Declined"]
```

### Git graph — flowchart fallback (simple DAG)
```mermaid
graph LR
  A["init"] --> B["feat-A"]
  A --> C["fix-1"]
  B --> D["merge"]
  C --> D
```

## When to Use Which Diagram
- Flowchart: General flows, decisions, and data movement in specs and PRDs.
- Sequence: Interactions over time between actors/services (APIs, requests, responses).
- Class: Domain models and static structure; useful for entity attributes and relations.
- State: Lifecycle of an entity/component (idle -> loading -> ready/error, nested states).
- ER: Database/logical data model with cardinalities.
- Journey: User experience across steps/sections (great for PRD acceptance flows).
- Gantt: Scheduling, releases, and dependencies by dates.
- Pie: Simple composition/ratios; prefer tables when precision matters.
- Quadrant (fallback): Prioritization matrix (Impact/Effort) without experimental chart support.
- Requirement (fallback): Traceability between requirements, tests, and system elements.
- Sankey (fallback): Convey relative volumes along a path when `sankey` is unavailable.
- Git graph (fallback): Small branch/merge DAGs when `gitGraph` is unavailable.

## Troubleshooting
- If a diagram fails to render, try:
  1) Replace `flowchart` with `graph` and simplify shapes.
  2) Quote node texts.
  3) Test in `https://mermaid.live` to isolate environment issues.
  4) Fall back to the templates above for maximum compatibility.
