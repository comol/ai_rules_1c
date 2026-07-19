# v8unpack — pointer to standalone skill

**Canonical source:** `content/skills/v8unpack-cf/SKILL.md` (or its installed copy under the active tool's skills directory).

This file is intentionally a thin pointer. Unpack / rebuild of CF, CFE, and EPF binaries without the 1C platform is owned by the standalone **`v8unpack-cf`** skill — commands, source layout, version checks, and limitations live there.

**When to use:** you only have a binary artifact and no infobase / Designer / `ibcmd`. For platform-based extraction from a running infobase use the `getconfigfiles` rule instead.

**Dependency:** `pip install v8unpack` (verify with `python -m v8unpack --help`).
