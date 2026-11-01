# Third-party notice — support-guard hook

`support-guard.mjs` in this folder is a port of `hooks/support-guard.mjs` and
`hooks/common/support-state.mjs` of Nikolay-Shirokov/cc-1c-skills.

- Upstream: <https://github.com/Nikolay-Shirokov/cc-1c-skills>
- Ported from commit: `2e75b0f483eb020e9f09562d1a7be1982bc5ac6e`
- Licence: MIT

Local modifications are listed in the file header: `.dev.env` opt-in
(`SUPPORT_GUARD_HOOK`) and reaction (`SUPPORT_GUARD`) instead of
`.v8-project.json`, support-state decoding aligned with the PowerShell guard of
the vendored `1c-metadata-manage` tools (fail-closed on an unreadable state),
dump-scope filtering, and warnings shown to the user. `support-guard.sh` is not
upstream code.

```
MIT License

Copyright (c) 2025-2026 Nick Shirokov

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
