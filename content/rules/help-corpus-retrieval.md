---
description: Retrieving routed 1C standards from `1C-docs-mcp` — the `standards` tool, the `standards(name="…") §N` reference form, paging, unavailable server. Load when following a `standards(name=…)` reference for the first time in a session.
alwaysApply: false
category: tooling
---

# Retrieving the routed standards from the Help MCP corpus

Fourteen of the detailed domain standards in `content/rules/` carry headings without bodies. Their normative text is one document each in the **`1c-standards`** collection of the Help MCP server (`1C-docs-mcp`), and this file is the single description of how to get it. The routed files point here instead of repeating the contract.

## The tool is `standards`, not `docsearch`

`1C-docs-mcp` holds four kinds of content and reaches them with four tools. The standards collection is **read whole rather than sampled**, so it has its own tool:

```
standards()                          → the catalogue: every standard, its name and declared description
standards(name="anti-patterns")      → that standard, entire
standards(query="именование ролей")  → search inside the standards only
```

Optional on all three forms: `max_chars`, `max_items`, `detail_level` (`detailed` | `compact`), `cursor`.

**`docsearch` and `docinfo` cannot reach the standards.** They serve the platform syntax reference and the platform prose; their `scope` parameter (`syntax` | `docs` | `all`) does not select this collection, and there is **no `corpus` parameter on any tool of this server**. A call like `docsearch(query=..., corpus="...")` is an unknown-argument error, and it is exactly the guessed-parameter defect `AGENTS.md → MCP Tool Calling → C.4` forbids.

The sibling collection `formatspec` works identically over the 1C file-format specifications (form / role / DCS / MXL / extension on-disk XML) — useful next to `metadata-xml-workarounds.md` and the `1c-metadata-manage` skill.

## Naming a standard

`name` accepts three spellings, case-insensitively:

- the **short name** — the file stem of the routed rule, for example `dev-standards-architecture` or `anti-patterns`;
- the **`doc_id`** copied exactly from a previous answer; treat it as opaque, never construct it from a call or a filesystem path;
- the document's own **title**.

A name the collection does not hold answers `not_found` **and lists every standard it does hold** — so a misspelling costs one call, not a guessing loop. When you do not know which rule governs the work, `standards()` (the catalogue) is cheaper than guessing at names.

## Prefer whole documents; mind the paging

- **Know which rule governs → `standards(name=…)`.** These rules are written to be loaded before the work starts; one call gets the whole rule. Do **not** issue one `standards(query=…)` per section — that is more calls for less text, and it returns matched passages rather than the rule.
- **Do not know which rule → `standards(query=…)` once**, then fetch the rule it points at by name.
- **A document larger than `max_chars` is paged, not cut.** The response carries `collection.parts` and `next_cursor`; continue until you have the parts you need. A first page is not the rule — treat a truncated retrieval the same way you would treat half a file.
- **Retrieved text stays in context.** Re-requesting the same standard against unchanged state is forbidden by `AGENTS.md → MCP Tool Calling → C.1` like any other repeat.

## Retrieve before you apply

A reference of the form `standards(name="anti-patterns") §3 → "Subquery in SELECT"` anywhere in the ruleset is an instruction to call exactly that — `standards(name="anti-patterns")` — and read the named section; the routed file on disk reproduces only the headings so that such references resolve. A heading is a **retrieval target, not a summary**: acting on a section title without reading the text behind it is inventing the rule, not following it. Reconstructing a standard from its heading — or from training-data memory of "how 1C is usually written" — is a defect.

## When the server is not exposed

**Runtime retrieval of routed standards is MCP-only.** Do not substitute GitHub / raw URLs, local source copies, other search tools, headings, or model memory for `standards`. This applies equally when the tool is absent, returns `unavailable` / `error`, or cannot return a required document. Do not request permission to bypass it.

1. **State the gap once** when the standard is first needed, naming the document and the actual retrieval failure.
2. **Continue independent work** using the always-on and available un-routed rules. Their requirements and the availability rules of `verification-gates.md` still apply.
3. **Keep the dependent requirement unverified.** Do not claim compliance with a standard you could not read. If its content is necessary to choose or validate the change, leave that part blocked until MCP retrieval is available; explain the specific dependency in the delivery report. An unrelated unavailable standard does not stop the task.
4. **Record the limitation under Risks**, for example: *"Standard `<name>` not retrieved — `1C-docs-mcp` not exposed; `<dependent check>` remains unverified."*

Editing the standards is distinct from runtime retrieval: maintainers edit the bodies in the `1C-docs-mcp` repository (`data/corpora/1c-standards/content/standards/`), outside this ruleset. That does not make any source directory a fallback for applying standards to a 1C development task.

## Where the corpus comes from

The collection ships **inside the `1C-docs-mcp` image** — nothing is mounted or indexed per project. If `standards` is absent from the session's tool schema while `docsearch` is present, the image predates the collection tools; `/checkmcp` reports that case.

The bodies are authored **in the `1C-docs-mcp` repository** — `data/corpora/1c-standards/content/standards/<stem>.md`, one file per routed standard, with `content.lock.json` beside them recording each document's hash. This ruleset holds only the routers in `content/rules/` (retrieval instructions and headings); editing a router does not update the corpus body, and editing a body does not update a router's heading tree — `tools/validate-rules.ps1 -StandardsDir <path>` checks that the two trees still agree.

**A merged edit is not evidence of a deployed corpus update.** The maintainer's sync contract records the source commit, body hashes, and resulting image identity, then verifies retrieval from that image. Runtime consumers use only identifiers and provenance actually returned by the connected server; do not invent version parameters or infer a deployed revision from the local checkout. If correspondence with a changed standard matters and cannot be established, report corpus freshness as unverified.

## Success criteria

- ✅ Standards fetched with `standards`, never with `docsearch` / `docinfo` and never with a `corpus` argument.
- ✅ The governing rule fetched whole by name; `query` used to *find* a rule, not to read one section at a time.
- ✅ Paged documents followed to the parts actually needed.
- ✅ No section applied from its heading alone.
- ✅ MCP-only runtime retrieval; source bodies used only for ruleset maintenance.
- ✅ Unavailable content stated once, dependent requirements left blocked / unverified, and independent work continued.
