# Security Hardening Findings

This document summarizes the vulnerabilities discovered during the `glc_v1` migration, the security invariants they violated, and the patches implemented to secure the system.

## 1. Unauthenticated Webhook Gateway Bypass (Middleware)
- **Finding**: The global HTTP authentication middleware in `glc/main.py` included a generic regex in `ALLOWLIST_PATHS` (`^/v1/channels/[^/]+/webhook$`) to let third-party provider webhooks bypass the `install_token` check. This needlessly exposed the Gateway's internal endpoints to unauthenticated traffic from the internet, increasing the attack surface.
- **Invariant Broken**: "Sockets must enforce authorization mapping" / "All control flows must validate their inputs" (Authorization Bypass / Attack Surface).
- **Fix**: We decentralized the webhook receivers. Instead of routing external webhooks through the Gateway, each adapter was deployed as its own independent Modal web endpoint (`@app.function`). We then commented out the webhook regex in `ALLOWLIST_PATHS`, locking down the Gateway middleware so that *every* route (except `/healthz`) strictly requires the `install_token`.

## 2. Adapter Container Isolation & Secrets Exposure
- **Finding**: Adapters were originally running in the same process and environment as the main Gateway. This meant a compromised adapter could read the entire process environment, leaking sensitive global secrets like the `GLC_INSTALL_TOKEN`, OpenAI keys, Anthropic keys, and database credentials.
- **Invariant Broken**: "The Gateway runs isolated from the Adapters" / "Processes must run with the least privilege possible" (Environment Secrets Exposure).
- **Fix**: We isolated each adapter into its own independent Modal container (`@app.function`). We also explicitly split the environment injection so that LLM keys and the master `install_token` are exclusively bound to the Gateway container. The isolated adapters now only receive the bare minimum configuration needed to run.

## 3. Audit Log SQL Injection
- **Finding**: The `glc.audit.store.record_action()` method used naive Python f-strings (`f"{action}"`, `f"{context}"`) to dynamically construct SQL queries for `execute()`. An attacker sending a malicious message (e.g., `' -- `) could execute arbitrary SQLite commands or drop tables.
- **Invariant Broken**: "All data flowing into the database must be sanitized against injection" (Input Validation).
- **Fix**: Refactored the database execution in `glc/audit/store.py` to use parameterized queries (`?`) for all variables, ensuring inputs are strictly treated as data rather than executable statements.

## 4. Forged Audit Logs via Unkeyed Hashing
- **Finding**: The audit log chain's integrity relied on a simple SHA-256 hash of the previous row. An attacker with code execution could arbitrarily calculate the hash and append forged logs to the database, breaking the chain of trust.
- **Invariant Broken**: "Cryptographic signatures must be tied to a secret to prevent forgery" (Audit Authenticity).
- **Fix**: Replaced the plain SHA-256 hash with an **HMAC-SHA256** signature keyed by the Gateway's highly restricted `install_token`. Without the token, an attacker cannot forge the `curr_hash`.

## 5. Install Token Leaked to Shared Volume Disk
- **Finding**: A legacy development fallback in `glc.config.get_or_create_install_token()` would read from or write the generated install token to the shared filesystem (`/data/glc/install_token`). Any component or adapter with volume access could read the master token.
- **Invariant Broken**: "Data must not leak via shared volumes or filesystem state" (Filesystem Secrets / Least Privilege).
- **Fix**: Stripped the disk read/write logic out of `glc/config.py`. The token is now strictly injected via the `GLC_INSTALL_TOKEN` environment variable from a Modal Secret, completely removing it from the filesystem. We also purged the leaked token from the Modal volume.

## 6. Pairing Store Database Exposure
- **Finding**: The `PairingStore` logic and connection pool were exposed in the globally importable `glc.security.pairing` module. If an attacker achieved Remote Code Execution (RCE) in an adapter, they could import the module and call `force_pair_owner()` directly to elevate their own trust.
- **Invariant Broken**: "The Gateway runs isolated from the Adapters" (Separation of Concerns).
- **Fix**: Moved the `PairingStore` class and SQLite logic to an internal Gateway module (`glc.routes.pairing_store`). Adapters now lack the Python path to import it, effectively securing the database behind the Gateway process boundary.

## 7. Policy Engine Process Co-location
- **Finding**: The policy engine (`glc.policy.engine`) ran in the same process space as the gateway and adapters. An attacker with RCE could simply monkey-patch the `evaluate()` function in memory to bypass security constraints.
- **Invariant Broken**: "Processes must run with the least privilege possible" (Process Isolation / Defense in Depth).
- **Fix**: Separated the policy engine into a discrete `@app.function` (`policy_engine`) on Modal. It now runs in a completely isolated container, requiring remote RPC from the gateway to execute tools.

## 8. Channel Spoofing via WebSocket Headers
- **Finding**: The WebSocket endpoint in `glc.routes.channels` implicitly trusted the `env.channel` field sent by the adapter. An attacker controlling the Discord adapter could construct a message claiming to be from Telegram, bypassing channel-specific boundaries.
- **Invariant Broken**: "Sockets must enforce authorization mapping" (Route-Level Authorization).
- **Fix**: Added an explicit verification check on the `/v1/channels/{name}` route to ensure the incoming payload's `env.channel` exactly matches the authenticated `name` parameter on the socket URL. Mismatches force an immediate socket closure.

## 9. Root Execution & Unrestricted Syscalls
- **Finding**: Adapters and the Gateway ran as the `root` user within their Modal containers without any syscall filtering. An attacker could use `os.kill` to terminate the process or `ptrace` to manipulate memory.
- **Invariant Broken**: "Processes must run with the least privilege possible" (Sandbox Isolation).
- **Fix**: Created an unprivileged `appuser` and invoked `os.setuid`/`os.setgid` at runtime to drop privileges. Deployed a strict `seccomp` filter (`glc.security.sandbox`) using `libseccomp2` to block dangerous syscalls (`SYS_kill`, `SYS_execve`, `SYS_ptrace`) at the kernel level before the application starts processing data.
