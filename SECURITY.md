# FableForge Security Policy

## Supported Versions

We maintain security updates for the following versions of FableForge projects:

| Version | Supported          | Notes                                    |
| ------- | ------------------ | ---------------------------------------- |
| 0.2.x   | :white_check_mark: | Current release — actively maintained    |
| 0.1.x   | :white_check_mark: | Security patches only                    |
| < 0.1.0 | :x:                | No longer supported                     |

Each sub-project within the FableForge monorepo follows the same versioning
and support policy. See individual `pyproject.toml` files for version numbers.

## Reporting a Vulnerability

### Where to Report

**Do NOT report security vulnerabilities through public GitHub issues.**

Instead, report them through one of these channels:

| Channel                           | Use For                                    |
| --------------------------------- | ------------------------------------------ |
| **GitHub Security Advisories**    | All vulnerabilities (preferred method)     |
| **security@fableforge.ai**       | All vulnerabilities (encrypted via PGP)   |
| **HackerOne**                     | Responsible disclosure (coming soon)      |

### GitHub Security Advisories (Preferred)

1. Navigate to [github.com/KingLabsA/anvil/security/advisories/new](https://github.com/KingLabsA/anvil/security/advisories/new)
2. Fill in the advisory form with:
   - A clear description of the vulnerability
   - Steps to reproduce
   - Affected versions
   - Potential impact
3. Submit the advisory. The security team will be notified immediately.

### Email (PGP-Encrypted)

For sensitive vulnerabilities, send an encrypted email to **security@fableforge.ai**.

Our PGP key fingerprint:
```
A4B2 8C9D E1F0 3A7B 5C6D  8E9F 0A1B 2C3D 4E5F 6A7B
```

You can retrieve our public key from:

```bash
gpg --keyserver keys.openpgp.org --recv-key 0A1B2C3D4E5F6A7B
```

Or download it directly from: [https://fableforge.ai/.well-known/pgp-key.asc](https://fableforge.ai/.well-known/pgp-key.asc)

### What to Include

Please include as much of the following information as possible:

1. **Description** — A clear description of the vulnerability
2. **Impact** — What an attacker could achieve (data leakage, RCE, DoS, etc.)
3. **Affected components** — Which FableForge project(s) are affected
4. **Reproduction steps** — Detailed steps to reproduce the issue
5. **Proof of concept** — Code, commands, or screenshots demonstrating the issue
6. **Suggested fix** — If you have ideas for how to address the vulnerability
7. **Disclosure timeline** — Your preferred timeline for public disclosure

## Response Timeline

We take security seriously and commit to the following response timelines:

| Phase                      | Timeframe         | Description                                          |
| -------------------------- | ----------------- | ---------------------------------------------------- |
| **Acknowledgment**         | 24 hours          | You will receive confirmation that we received your report |
| **Initial Assessment**     | 72 hours          | We will triage the report and provide an initial severity assessment |
| **Status Update**          | 7 days            | You will receive a progress update with findings    |
| **Patch Development**      | 7–14 days         | Critical and High severity patches are developed    |
| **Patch Release**          | 14–30 days        | Patches are released after validation               |
| **Public Disclosure**      | 90 days           | Coordinated disclosure after patch is available     |

### Severity and Timeline Priority

- **Critical** (RCE, auth bypass, data exfiltration): Patch within 7 days
- **High** (privilege escalation, significant data exposure): Patch within 14 days
- **Medium** (limited impact, requires specific conditions): Patch within 30 days
- **Low** (minor info leakage, cosmetic issues): Patch in next release cycle

## Severity Classification

We use the following severity levels, based on CVSS v3.1 scoring:

### Critical (CVSS 9.0–10.0)

Vulnerabilities that allow:
- Remote code execution without authentication
- Complete system takeover or data exfiltration
- Authentication bypass leading to full access
- Any issue affecting the integrity of the Anvil verification pipeline
  (since self-verification is our core value proposition)

**Response:** Immediate hotfix release; all other work is deprioritized.

### High (CVSS 7.0–8.9)

Vulnerabilities that allow:
- Privilege escalation (regular user → admin)
- Significant data exposure (PII, secrets, API keys)
- Denial of service affecting production deployments
- Bypass of the permission/guardrail system with real-world impact

**Response:** Emergency patch within 14 days; backported to supported versions.

### Medium (CVSS 4.0–6.9)

Vulnerabilities that allow:
- Limited data exposure (non-sensitive metadata)
- Denial of service under specific conditions
- Bypass of non-critical security controls
- Cross-site scripting or injection with limited scope

**Response:** Patch in next scheduled release; backported if straightforward.

### Low (CVSS 0.1–3.9)

Vulnerabilities that allow:
- Minor information leakage (version numbers, error messages)
- Local attacks requiring physical access or existing privileges
- Cosmetic issues with minimal security impact

**Response:** Addressed in regular release cycles; no backport guarantee.

## Disclosure Policy

### Coordinated Disclosure

We practice **coordinated disclosure**. Here is our commitment:

1. **We will never publicly disclose** a vulnerability before a patch is available,
   unless the vulnerability is already publicly known.
2. **We will credit reporters** who follow responsible disclosure, unless they
   request anonymity.
3. **We will work with you** on the disclosure timeline, balancing the need for
   user protection with the time required to develop and test a fix.
4. **We will publish** a security advisory on GitHub within 90 days of the
   initial report, regardless of patch status, unless the reporter requests
   an extension.

### When We May Disclose Early

- The vulnerability is already publicly known or being actively exploited.
- The vulnerability affects a critical component (verification pipeline,
  permission system) where delays pose significant risk to users.
- We have been unable to reach the reporter for 30+ days after the 72-hour
  acknowledgment window.

## Scope

### In Scope

- The FableForge monorepo and all 21 sub-projects:
  - Anvil (core agent engine)
  - VerifyLoop (verification & repair)
  - ErrorRecovery (error classification & handling)
  - AgentSwarm (multi-agent orchestration)
  - AgentRuntime (runtime infrastructure)
  - AgentSkills (skill system)
  - AgentConstitution (value alignment)
  - AgentCurriculum (training curriculum)
  - AgentFuzzer (testing agent robustness)
  - AgentProfiler (profiling & cost analysis)
  - AgentTelemetry (observability)
  - BenchAgent (benchmark framework)
  - CostOptimizer (LLM cost reduction)
  - ShellWhisperer (shell benchmark model)
  - ReasonCritic (critique & refinement model)
  - FableForge-14B (base language model)
  - Fable5-Dataset (benchmark dataset)
  - TraceCompiler (trace optimization)
  - TrajectoryDistiller (training data extraction)
  - TraceViz (trace visualization)
  - AgentDev (VS Code extension)

- All GitHub Actions workflows
- Docker images published to ghcr.io
- PyPI packages under the `fableforge` and `anvil-agent` namespaces
- The FableForge website (fableforge.ai)
- API endpoints at api.fableforge.ai

### Out of Scope

- Third-party dependencies (report to the dependency maintainer)
- Social engineering attacks
- Denial of service against fableforge.ai infrastructure
- Issues in forked repositories not yet merged
- Theoretical vulnerabilities without proof of concept
- Vulnerabilities in outdated or unsupported versions

## Security Best Practices for Contributors

### For Code Contributors

1. **Never commit secrets** — Use environment variables or secret management.
   Our CI checks for accidental secret exposure using `gitleaks`.

2. **Validate all inputs** — Especially in the Anvil engine, where agent
   prompts are processed. Sanitize before passing to LLM APIs.

3. **Use the permission system** — When adding new tools or agents, always
   integrate with `PermissionManager`. Never bypass permission checks.

4. **Run `anvil verify`** — Before every PR, run the verification pipeline
   to catch code quality and security issues.

5. **Dependency updates** — Use `pip-audit` and `safety` to check for known
   vulnerabilities in dependencies. Update in a timely manner.

### For Model Trainers

1. **Training data** — Ensure training data is free of leaked secrets, PII,
   and content under restrictive licenses.

2. **Model evaluation** — Run `BenchAgent` before release to verify the model
   doesn't produce harmful outputs at scale.

3. **Constitutional constraints** — All fine-tuned models must pass the
   `AgentConstitution` alignment checks.

## Security Audit History

| Date       | Auditor             | Scope                    | Result                              |
| ---------- | ------------------- | ------------------------ | ----------------------------------- |
| 2024-11    | Internal Team       | Anvil v0.1.0             | 2 Medium, 4 Low findings (all fixed)|
| 2025-01    | Community Review    | Permission System          | 1 High, 3 Medium findings (all fixed)|
| 2025-03    | Internal Team       | Multi-Agent v0.2.0        | 0 Critical, 1 Medium finding (fixed) |
| 2025-05    | Planned             | Full ecosystem audit       | Upcoming                            |

## Security Contact

For any security-related questions or concerns:

- **Email:** security@fableforge.ai
- **GitHub:** [@fableforge/security](https://github.com/orgs/fableforge/teams/security)
- **Discord:** #security channel on [discord.gg/fableforge](https://discord.gg/fableforge)

Thank you for helping keep FableForge and our users safe.
