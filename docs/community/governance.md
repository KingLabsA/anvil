# FableForge Project Governance

This document defines the governance structure, decision-making processes, and community policies for the FableForge ecosystem. It applies to all projects under the FableForge organization.

---

## Table of Contents

1. [Project Roles](#project-roles)
2. [Decision-Making Process](#decision-making-process)
3. [Release Process](#release-process)
4. [Security Vulnerability Reporting](#security-vulnerability-reporting)
5. [Code of Conduct](#code-of-conduct)
6. [How to Become a Maintainer](#how-to-become-a-maintainer)

---

## Project Roles

### BDFL — Benevolent Dictator for Life

The BDFL is the final authority on all project decisions. This role exists to break deadlocks and provide long-term vision alignment. The BDFL should rarely need to exercise authority; most decisions should be made through consensus or the RFC process.

**Responsibilities:**
- Set and communicate the long-term project vision
- Break deadlocks when consensus cannot be reached
- Make final calls on architectural direction and project scope
- Approve or veto governance changes
- Ensure the project stays true to its mission and values

**Current BDFL:** The FableForge founding team (listed in the repository's CODEOWNERS file)

**Authority:**
- Can override any decision by the Maintainer team
- Can promote or remove Maintainers
- Can modify this governance document
- Can archive or sunset projects

---

### Maintainer

Maintainers are trusted contributors who have demonstrated sustained, high-quality contributions and excellent judgment. They are responsible for the day-to-day health of the project.

**Responsibilities:**
- Review and merge pull requests
- Triage issues and set priorities
- Enforce the Code of Conduct
- Participate in RFC discussions and votes
- Release new versions (see Release Process)
- Mentor new contributors
- Maintain project documentation and CI/CD pipelines

**How appointed:**
- Nominated by an existing Maintainer
- Approved by a majority of current Maintainers
- No veto from the BDFL
- Must have at least 20 merged PRs across FableForge projects, or equivalent sustained contribution

**Authority:**
- Merge PRs (after required approvals)
- Close issues as wontfix or out-of-scope
- Set milestones and labels
- Approve or reject RFCs (see Decision-Making Process)
- Remove Contributors who violate the Code of Conduct

**Maintainer expectations:**
- Review at least 2 PRs per week
- Participate in at least 1 RFC discussion per month
- Respond to issue triage requests within 48 hours
- If inactive for 60+ days without notice, moved to Emeritus status

**Emeritus Maintainers:**
Maintainers who step back from active duty become Emeritus Maintainers. They retain the title and recognition but no longer have merge access. They can return to active Maintainer status by request.

---

### Contributor

Contributors are anyone who has submitted and had merged at least one pull request to a FableForge project. They are the lifeblood of the project.

**Responsibilities:**
- Follow the contribution guidelines (CONTRIBUTING.md)
- Write tests for their changes
- Respond to review feedback promptly
- Maintain their contributed code (bug fixes, updates) for a reasonable period

**Rights:**
- Contributor role on Discord
- Listed in the project's CONTRIBUTORS file
- Eligible to become a Maintainer (see How to Become a Maintainer)

---

### Community Member

Community members are anyone who uses, discusses, or advocates for FableForge. No code contribution is required.

**Rights:**
- Participate in discussions (Discord, GitHub Discussions)
- File bug reports and feature requests
- Provide feedback on RFCs
- Attend community events and office hours

---

## Decision-Making Process

FableForge uses a tiered decision-making framework based on the scope and impact of the change.

### Tier 1: Trivial Changes (Maintainer Decision)

**Applies to:** Bug fixes, documentation updates, test additions, code style changes, dependency version bumps.

**Process:**
1. Contributor opens a PR
2. One Maintainer reviews and approves
3. Maintainer merges

**No RFC required.** These changes do not affect public APIs, architecture, or project scope.

---

### Tier 2: Standard Changes (PR + Review)

**Applies to:** New features, minor API additions, performance improvements, refactors that change internal behavior but not public APIs.

**Process:**
1. Contributor opens a PR (preferably after a GitHub Discussion or issue to validate the idea)
2. Two Maintainers review and approve
3. Maintainer merges

**No RFC required**, but a linked issue or discussion is expected so the change has community visibility.

---

### Tier 3: Significant Changes (RFC Required)

**Applies to:** Breaking API changes, new modules or projects, major architectural shifts, changes to supported Python versions, changes to the build system, deprecation of features.

**RFC Process:**

1. **Draft the RFC**: Create a document in `docs/rfcs/` using the RFC template (`docs/rfcs/0000-template.md`):
   - Title
   - Summary (1-2 paragraphs)
   - Motivation (why is this needed?)
   - Detailed design (how does it work?)
   - Alternatives considered
   - Unresolved questions
   - Impact on existing functionality

2. **Open a PR for the RFC**: Target the `rfc` branch or a feature branch. The PR is the discussion forum.

3. **Community Discussion**: Minimum 7 days of open discussion. Maintainers and community members discuss the merits, concerns, and alternatives.

4. **Maintainer Vote**: After the discussion period, Maintainers vote:
   - **+1**: Approve
   - **0**: Neutral (no opinion)
   - **-1**: Veto (must include a reason)

   **Approval requires**: 2/3 majority of Maintainer votes, with no veto, OR BDFL override.

5. **Implementation**: If approved, the RFC is assigned a number (e.g., RFC-0042) and the author implements it. The RFC PR is merged into `docs/rfcs/`.

6. **Completion**: When implementation is done, the RFC status is updated to "Completed" and a summary PR is merged.

**RFC States:**
- `Draft` — Being written, not yet submitted
- `Proposed` — PR opened, under discussion
- `Approved` — Vote passed, ready for implementation
- `Implemented` — Code merged, feature available
- `Deferred` — Not a priority right now; may be revisited
- `Rejected` — Vote did not pass or BDFL vetoed

---

### Tier 4: Governance Changes (BDFL Approval)

**Applies to:** Changes to this governance document, changes to the Code of Conduct, adding or removing Maintainers, sunsetting projects.

**Process:**
1. Any Maintainer proposes the change
2. 14-day community comment period
3. Maintainer vote (2/3 majority required)
4. BDFL approval required (BDFL can also propose)

---

## Release Process

### Versioning

FableForge projects follow [Semantic Versioning 2.0.0](https://semver.org/):

- **Major version (X.0.0)**: Breaking changes, incompatible API changes
- **Minor version (0.X.0)**: New features, backwards-compatible
- **Patch version (0.0.X)**: Bug fixes, backwards-compatible

**Pre-release versions:**
- `X.Y.Z-alpha.N`: Early preview, unstable, API may change
- `X.Y.Z-beta.N**: Feature-complete, known bugs may exist
- `X.Y.Z-rc.N**: Release candidate, no new features, final testing

### Release Checklist

For every release (major, minor, or patch):

1. **Update CHANGELOG.md** — Every release gets a changelog entry. Use the [Keep a Changelog](https://keepachangelog.com/) format:
   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD

   ### Added
   - New feature description (#PR)

   ### Changed
   - Change description (#PR)

   ### Fixed
   - Bug fix description (#PR)

   ### Breaking
   - Breaking change description (#PR)
   ```

2. **Run the full test suite** — All tests must pass:
   ```bash
   pytest tests/ -xvs
   pytest tests/integration/ -xvs
   anvil verify --all
   ```

3. **Update version number** — In `pyproject.toml`, `__init__.py`, and any version-socketed files.

4. **Create a release branch** (for major/minor releases):
   ```bash
   git checkout -b release/X.Y.Z main
   ```

5. **Review and approve** — At least 2 Maintainers review the release PR.

6. **Tag the release**:
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

7. **Build and publish to PyPI**:
   ```bash
   python -m build
   python -m twine upload dist/*
   ```

8. **Create GitHub Release** — Use the changelog as the release notes. A Maintainer creates the release on GitHub.

9. **Announce** — Post in Discord `#announcements`, update the website, tweet if applicable.

10. **Merge back** (for major/minor releases):
    ```bash
    git checkout main
    git merge release/X.Y.Z
    git push origin main
    ```

### Hotfix Process

For critical bug fixes:

1. Branch from the release tag:
   ```bash
   git checkout -b hotfix/X.Y.Z+1 vX.Y.Z
   ```
2. Fix the bug, add tests
3. Follow the full release checklist (abbreviated — no feature review needed)
4. Tag and release as X.Y.(Z+1)

---

## Security Vulnerability Reporting

### Responsible Disclosure

FableForge takes security seriously. If you discover a security vulnerability, please report it responsibly.

**DO NOT** open a public GitHub issue for security vulnerabilities.

### Reporting Process

1. **Report privately** via [GitHub Security Advisories](https://github.com/KingLabsA/anvil/security/advisories/new)
   - Include: description of the vulnerability, steps to reproduce, affected versions, potential impact
   - You can also email: security@fableforge.ai (encrypted with our PGP key, available in the repository)

2. **Acknowledgment** — We will acknowledge your report within 48 hours.

3. **Assessment** — We will assess the vulnerability within 7 days and provide an initial severity rating:
   - **Critical**: Remote code execution, data exfiltration, authentication bypass
   - **High**: Privilege escalation, significant data exposure
   - **Medium**: Limited impact bugs that could be chained with other issues
   - **Low**: Minor information leaks, edge-case issues

4. **Fix Development** — We will develop a fix and coordinate disclosure with you.

5. **Release** — We will release a patched version within:
   - Critical: 48 hours
   - High: 7 days
   - Medium: 14 days
   - Low: 30 days (or next scheduled release)

6. **Public Disclosure** — After the fix is released, we will publish a security advisory on GitHub and credit the reporter (unless they request anonymity).

### Security Response Team

The security response team consists of:
- All Maintainers (primary responders)
- BDFL (escalation point)

For critical issues, the BDFL and at least 2 Maintainers will coordinate the response.

---

## Code of Conduct

### Our Pledge

We as members, contributors, and leaders pledge to make participation in our community a harassment-free experience for everyone, regardless of age, body size, visible or invisible disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, caste, color, religion, or sexual identity and orientation.

We pledge to act and interact in ways that contribute to an open, welcoming, diverse, inclusive, and healthy community.

### Our Standards

Examples of behavior that contribute to a positive environment for our community:

- Demonstrating empathy and kindness toward other people
- Being respectful of differing opinions, viewpoints, and experiences
- Giving and gracefully accepting constructive feedback
- Accepting responsibility and apologizing to those affected by our mistakes, and learning from the experience
- Focusing on what is best not just for us as individuals, but for the overall community

Examples of unacceptable behavior:

- The use of sexualized language or imagery and sexual attention of any kind
- Trolling, insulting or derogatory comments, and personal or political attacks
- Public or private harassment
- Publishing others' private information, such as a physical or email address, without their explicit permission
- Other conduct which could reasonably be considered inappropriate in a professional setting

### Enforcement Responsibilities

Community leaders are responsible for clarifying and enforcing our standards of acceptable behavior and will take appropriate and fair corrective action in response to any behavior that they deem inappropriate, threatening, offensive, or harmful.

Community leaders have the right and responsibility to remove, edit, or reject comments, commits, code, wiki edits, issues, and other contributions that are not aligned with this Code of Conduct, and will communicate reasons for moderation decisions when appropriate.

### Scope

This Code of Conduct applies within all community spaces, including but not limited to:

- GitHub repositories under the FableForge organization
- Discord server
- GitHub Discussions
- Social media accounts representing FableForge
- Any official events (online or in-person)
- Any community member's public representation of the project

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported to the community leaders responsible for enforcement via:

- GitHub: Direct message to any Maintainer
- Discord: DM any Maintainer (identifiable by the gold "Maintainer" role)
- Email: conduct@fableforge.ai

All complaints will be reviewed and investigated promptly and fairly.

All community leaders are obligated to respect the privacy and security of the reporter of any incident.

### Enforcement Guidelines

Community leaders will follow these Community Impact Guidelines in determining the consequences for any action they deem in violation of this Code of Conduct:

**1. Correction**

*Community Impact*: Use of inappropriate language or other behavior deemed unprofessional or unwelcome in the community.

*Consequence*: A private, written warning from community leaders, providing clarity around the nature of the violation and an explanation of why the behavior was inappropriate. A public apology may be requested.

**2. Warning**

*Community Impact*: A violation through a single incident or series of actions.

*Consequence*: A warning with consequences for continued behavior. No interaction with the people involved, including unsolicited interaction with those enforcing the Code of Conduct, for a specified period of time. This includes avoiding interactions in community spaces as well as external channels like social media. Violating these terms may lead to a temporary or permanent ban.

**3. Temporary Ban**

*Community Impact*: A serious violation of community standards, including sustained inappropriate behavior.

*Consequence*: A temporary ban from any sort of interaction or public communication with the community for a specified period of time. No public or private interaction with the people involved, including unsolicited interaction with those enforcing the Code of Conduct, is allowed during this period. Violating these terms may lead to a permanent ban.

**4. Permanent Ban**

*Community Impact*: Demonstrating a pattern of violation of community standards, including sustained inappropriate behavior, harassment of an individual, or aggression toward or disparagement of classes of individuals.

*Consequence*: A permanent ban from any sort of public interaction within the project community.

### Attribution

This Code of Conduct is adapted from the [Contributor Covenant](https://www.contributor-covenant.org/), version 2.1, available at https://www.contributor-covenant.org/version/2/1/code_of_conduct/.

Community Impact Guidelines were inspired by [Mozilla's code of conduct enforcement ladder](https://github.com/mozilla/diversity).

---

## How to Become a Maintainer

### Path from Community Member to Maintainer

FableForge is designed to have a clear and transparent path from user to contributor to maintainer. There is no mystery — the criteria are published and anyone who meets them can be nominated.

#### Step 1: Community Member → Contributor

**Requirements:**
- 1 merged pull request to any FableForge project

**What you get:**
- Contributor badge on Discord
- Listed in the project's CONTRIBUTORS file
- Eligible for Contributor-specific events

**How to get there:**
- Check issues labeled `good first issue` or `help wanted`
- Read CONTRIBUTING.md for the project you want to contribute to
- Submit a PR and respond to review feedback

#### Step 2: Contributor → Maintainer

**Requirements (all must be met):**
- At least **20 merged PRs** across FableForge projects (or equivalent sustained contribution such as major feature development, long-term issue triage, or extensive documentation work)
- At least **3 months** of sustained activity in the community (Discord, GitHub, or both)
- Demonstrated ability to **review others' PRs** thoughtfully and constructively
- Written at least **1 RFC** (for significant changes) or equivalent design documentation
- Endorsed by **2 current Maintainers** who can vouch for your judgment and technical ability
- No active Code of Conduct violations

**Nomination process:**
1. A current Maintainer nominates you by opening a GitHub issue titled `[MAINTAINER NOMINATION] @username`
2. The nomination issue lists:
   - Your contributions (PR count, areas of impact, RFCs authored)
   - Why you'd be a good Maintainer
   - Which 2 Maintainers endorse you
3. Maintainers have **7 days** to discuss and vote
4. A **2/3 majority** of Maintainers must approve
5. No BDFL veto (the BDFL has 7 days to veto after approval)
6. If approved, you're added to the CODEOWNERS file and given Maintainer role on Discord

**Maintainer responsibilities after promotion:**
- Review at least 2 PRs per week
- Triage at least 5 issues per week
- Participate in RFC discussions
- Enforce the Code of Conduct
- Release new versions when needed

#### Step 3: Maintainer → Emeritus

If a Maintainer needs to step back:

1. Post an announcement in the Maintainer channel (Discord and/or GitHub)
2. Update the CODEOWNERS file
3. Retain the Emeritus Maintainer title on Discord
4. Can return to active duty by request (no re-nomination needed)

**Inactivity policy:** If a Maintainer is inactive (no PRs, reviews, or issue comments) for 60+ days without notice, they will be moved to Emeritus status. They can request reinstatement at any time.

---

### Maintainer Removal

Maintainers can be removed for:

1. **Voluntary resignation** — The Maintainer steps down (becomes Emeritus)
2. **Inactivity** — 60+ days without activity and no response to check-in
3. **Code of Conduct violation** — After investigation and BDFL approval
4. **Loss of trust** — After a 2/3 Maintainer vote and BDFL approval

Removal is never taken lightly. The goal is always to support and retain Maintainers.

---

*This governance document is maintained by the FableForge BDFL and Maintainer team. For questions or proposed changes, open an issue on the [fableforge/fableforge](https://github.com/KingLabsA/anvil) repository or start a Discussion. Last updated: 2025-01-15.*
