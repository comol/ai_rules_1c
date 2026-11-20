# Third-party notices — `form-ordinary`

This skill is vendored from a third-party project. The notice below is
reproduced as the licence requires; it applies to every file of this directory
except this notice and travels with every copy of the skill, including installed
ones (`<tool>/skills/form-ordinary/NOTICE.md`).

## dreamadv81/form-ordinary

- Upstream: <https://github.com/dreamadv81/form-ordinary>
- Pinned commit: `a0f52949cb98217a9e6416ee2a007307b48af816` (2026-11-16,
  «перестановка страниц панели и формы»)
- Licence: MIT

Vendored: the upstream `form-ordinary/` directory, byte for byte from the pinned
commit (`git archive <commit> form-ordinary`). Not vendored: the upstream
`README.md` (installation for a bare Claude Code setup; the installer of this
ruleset places the skill), `.gitignore`, and `LICENSE` (its text is reproduced
below). Upstream does not publish its test suite (it runs on forms of real
configurations); `frm_json.py selftest` is the shipped self-check.

**Local changes — `SKILL.md` only:**

- the frontmatter `description` is replaced by a short English trigger
  description (the ruleset caps skill descriptions; upstream's Russian one is
  several times longer);
- a section *Ruleset integration* is inserted after the frontmatter: scope
  against `1c-metadata-manage` and `v8unpack-cf`, runtime, the support /
  repository gates and the evidence level.

Everything else — the rest of `SKILL.md`, `FORMAT.md`, `docs/`, `schema/`,
`frm_json.py`, `frm_codec/` — is upstream's and stays in Russian, as upstream
wrote it; do not translate or edit it here, so that a re-sync stays a clean copy.

**Platform pictures are not under the MIT licence.** The images in
`frm_codec/data/platform_pictures/` are taken from the 1C:Enterprise 8.3.27
platform; their rights belong to 1C (фирма «1С»), as upstream states.

### Re-sync

1. `git archive <new commit> form-ordinary | tar -x` into an empty directory.
2. Replace this directory's files with it, keeping `NOTICE.md`; re-apply the two
   `SKILL.md` changes above.
3. `py -3 -B content/skills/form-ordinary/frm_json.py selftest` must end with
   «Самопроверка пройдена»; run `tools/validate-rules.ps1`.
4. Update the pinned commit here and in `References.md`.

### MIT License

```text
MIT License

Copyright (c) 2026 dreamadv81

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
