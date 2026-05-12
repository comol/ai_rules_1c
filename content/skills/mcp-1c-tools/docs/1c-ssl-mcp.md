# 1c-ssl-mcp — tool catalog

Search across the Standard Subsystems Library (БСП / SSL).

> Load this file only if the `1c-ssl-mcp` server is actually available in the current session.

| Tool | Purpose | When to use |
|---|---|---|
| **ssl_search** | Search SSL / БСП functions | Find a ready-made standard library function to reuse before writing your own |

## Notes

- Before writing a new function, check whether БСП already provides one — this is the first step in the "Writing New Code" playbook.
- Good candidates for search: users, files, data exchange, digital signature, internet support, object versioning, uploads / downloads, scheduled jobs.
- If a БСП function is found — proceed to its documentation (`docinfo` / `helpsearch`) and use it instead of a custom implementation.
