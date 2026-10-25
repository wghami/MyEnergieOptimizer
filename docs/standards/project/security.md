# Security — MyEnergyOptimizer

The application accepts **user-written logic programs**, **uploaded files** and **arbitrarily
large simulation requests**, and it calls **external weather APIs**. Each threat has a mitigation
and tests in `tests/security/` (TST-8).

| ID | Threat | Mitigation | Test |
|---|---|---|---|
| MEO-SEC-1 | **Code execution through ASP.** clingo runs embedded code (`#script (python)`, `#script (lua)`) and calls external functions (`@f(...)`). | A `RuleSanitiser` works on clingo's parsed AST, not on regexes, and rejects `#script`, `#include`, `@`-terms and `#external` before any program reaches SmartMDAO or clingo. Programs generated from a `RuleSpec` are sanitised too (defence in depth). | every forbidden construct, plus obfuscated variants (comments, whitespace, case) |
| MEO-SEC-2 | **Solver resource exhaustion** (grounding blow-up, endless search). | Size limits on programs and fact spaces; SmartMDAO `budget_seconds`; each simulation runs in a child process with a hard wall clock and a memory limit (SEC-5). | pathological programs end with a typed error |
| MEO-SEC-3 | **Oversized simulations.** | Validated limits: maximum steps, assets per site, sites, and concurrent jobs per client (SEC-1). | boundary values ±1 |
| MEO-SEC-4 | **Path traversal** through profile references or file names. | Profiles are referenced by registry ID, never by path. Uploads get server-generated names inside a configured root, and resolved paths are checked with `is_relative_to(root)` (SEC-2). | `../`, absolute paths, symlinks, URL-encoded variants |
| MEO-SEC-5 | **Malicious uploads.** | Maximum size, strict CSV schema (columns, types, monotonic timestamps), no pickle or arbitrary parquet from users. | malformed, oversized and wrong-type files |
| MEO-SEC-6 | **SSRF** through weather sources. | Base URLs for NASA POWER, PVGIS and Open-Meteo come from settings, never from requests; users send only validated coordinates. The HTTP client has timeouts and refuses cross-host redirects. | requests carrying URL fields are rejected |
| MEO-SEC-7 | **Formula injection** in CSV exports. | Escaping per SEC-6. | round-trip test |
