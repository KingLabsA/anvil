# FableForge Discord Server Setup Guide

This document provides a complete guide for setting up and maintaining the FableForge Discord server. It covers server structure, roles, bots, moderation, and onboarding.

---

## Table of Contents

1. [Server Structure](#server-structure)
2. [Channel Descriptions](#channel-descriptions)
3. [Role Setup](#role-setup)
4. [Bot Setup](#bot-setup)
5. [Moderation Guidelines](#moderation-guidelines)
6. [Welcome Message Template](#welcome-message-template)
7. [Rules and Code of Conduct](#rules-and-code-of-conduct)
8. [Setting Up the Server](#setting-up-the-server)

---

## Server Structure

### Channel Categories and Channels

```
FableForge Discord Server
│
├── 🏠 Welcome & Rules
│   ├── #welcome
│   ├── #rules
│   ├── #announcements
│   └── #start-here
│
├── 💬 General
│   ├── #general
│   ├── #introduction
│   ├── #showcase
│   ├── #help-wanted
│   └── #events
│
├── 🔨 Anvil
│   ├── #anvil-help
│   ├── #anvil-discussion
│   ├── #anvil-bugs
│   └── #anvil-templates
│
├── 🤖 Models
│   ├── #training-help
│   ├── #model-discussion
│   ├── #fableforge-14b
│   ├── #shell-whisperer
│   └── #reason-critic
│
├── 🔗 Ecosystem
│   ├── #verifyloop
│   ├── #error-recovery
│   ├── #agent-swarm
│   ├── #bench-agent
│   ├── #prompt-forge
│   └── #eval-suite
│
├── 📊 Data
│   ├── #dataset
│   ├── #distiller
│   ├── #trace-compiler
│   └── #pipeline
│
├── 🛠️ Dev
│   ├── #contributing
│   ├── #architecture
│   ├── #security
│   ├── #rfc
│   └── #ci-cd
│
├── 🎓 Learning
│   ├── #tutorials
│   ├── #papers
│   └── #course-material
│
└── 🎯 Off-Topic
    ├── #random
    ├── #memes
    ├── #career
    └── #hardware
```

---

## Channel Descriptions

### 🏠 Welcome & Rules

| Channel | Purpose | Topic |
|---------|---------|-------|
| `#welcome` | Bot-posted welcome messages and onboarding info for new members | Welcome to FableForge! Read #rules and #start-here to get started. |
| `#rules` | Server rules and Code of Conduct — read-only | FableForge Community Code of Conduct and Server Rules |
| `#announcements` | Official announcements from maintainers — read-only, notifications on | New releases, events, breaking changes |
| `#start-here` | Links to docs, GitHub, and getting-started guides | New here? Start with these resources! |

### 💬 General

| Channel | Purpose | Topic |
|---------|---------|-------|
| `#general` | General discussion about FableForge, AI, coding | Anything FableForge-related that doesn't fit elsewhere |
| `#introduction` | Introduce yourself — background, interests, what you're building | Hi, I'm ... |
| `#showcase` | Show off what you've built with FableForge | Projects, blog posts, demos built with FableForge |
| `#help-wanted` | Issues and tasks looking for contributors | Good first issues, community tasks, mentorship |
| `#events` | Community events, meetups, hackathons, office hours | Upcoming FableForge events and community gatherings |

### 🔨 Anvil

| Channel | Purpose | Topic |
|---------|---------|-------|
| `#anvil-help` | Get help with Anvil installation, configuration, and usage | Questions about the Anvil generation engine |
| `#anvil-discussion` | Discuss Anvil features, architecture, and design decisions | Anvil design, roadmap, and ideas |
| `#anvil-bugs` | Report and discuss known Anvil bugs (link to GitHub issues) | Anvil bug reports and workarounds |
| `#anvil-templates` | Share and discuss Anvil project templates | Custom templates, template requests, template patterns |

### 🤖 Models

| Channel | Purpose | Topic |
|---------|---------|-------|
| `#training-help` | Get help with model training, fine-tuning, and evaluation | Training configuration, debugging, hardware questions |
| `#model-discussion` | General discussion about model architecture and capabilities | Model design, comparison, research |
| `#fableforge-14b` | Discussion specific to the FableForge-14B base model | FableForge-14B usage, results, and improvements |
| `#shell-whisperer` | Discussion specific to ShellWhisperer model | Shell generation benchmarks, ShellWhisperer results |
| `#reason-critic` | Discussion specific to ReasonCritic model | Critique and refinement, ReasonCritic applications |

### 🔗 Ecosystem

| Channel | Purpose | Topic |
|---------|---------|-------|
| `#verifyloop` | VerifyLoop — automated code verification and repair | Verification strategies, VerifyLoop configuration |
| `#error-recovery` | ErrorRecovery — self-healing generation pipelines | Error recovery patterns, integration with Anvil |
| `#agent-swarm` | AgentSwarm — multi-agent orchestration | Agent coordination, swarm topologies, delegation patterns |
| `#bench-agent` | BenchAgent — benchmarking framework | Benchmark design, benchmark results, new benchmark proposals |
| `#prompt-forge` | PromptForge — prompt engineering toolkit | Prompt patterns, prompt optimization, prompt templates |
| `#eval-suite` | EvalSuite — model evaluation framework | Evaluation design, metric discussion, eval results |

### 📊 Data

| Channel | Purpose | Topic |
|---------|---------|-------|
| `#dataset` | Dataset creation, curation, and quality | Dataset formats, cleaning, augmentation |
| `#distiller` | CodeDistiller and SkillDistiller discussion | Distillation strategies, trace extraction |
| `#trace-compiler` | TraceCompiler optimization and integration | Trace optimization, pipeline compilation |
| `#pipeline` | DatasetPipeline — end-to-end data workflows | Pipeline configuration, data processing |

### 🛠️ Dev

| Channel | Purpose | Topic |
|---------|---------|-------|
| `#contributing` | Guide for contributors — PR process, dev setup, code style | How to contribute to FableForge |
| `#architecture` | Architecture discussions, RFCs, and design reviews | System design and technical decisions |
| `#security` | Security discussion (NOT vulnerability disclosure — use GitHub Security Advisories) | Security best practices, threat modeling |
| `#rfc` | Request for Comments on proposed changes | RFC discussion and review |
| `#ci-cd` | CI/CD pipeline, release automation, deployment | Builds, tests, release process |

### 🎓 Learning

| Channel | Purpose | Topic |
|---------|---------|-------|
| `#tutorials` | Tutorials, walkthroughs, and educational content | Step-by-step guides and learning resources |
| `#papers` | Paper discussion — relevant research papers | ArXiv papers, conference proceedings, research |
| `#course-material` | Course and workshop materials | Slides, exercises, and curriculum |

### 🎯 Off-Topic

| Channel | Purpose | Topic |
|---------|---------|-------|
| `#random` | Anything not related to FableForge | Chat freely about non-FableForge topics |
| `#memes` | AI and coding memes | Keep it fun and respectful |
| `#career` | Job postings, career advice, resume review | FableForge-related and AI/ML career discussion |
| `#hardware` | GPU deals, cloud compute, local hardware setup | Hardware recommendations, setup help |

---

## Role Setup

### Role Hierarchy (top to bottom)

| Role | Color | Permissions | How Earned |
|------|-------|-------------|------------|
| **Admin** | Red (`#e74c3c`) | Administrator | BDFL and founding maintainers only |
| **Maintainer** | Gold (`#f1c40f`) | Manage channels, kick/ban, manage messages, manage roles | Nominated by existing maintainers |
| **Contributor** | Blue (`#3498db`) | Send messages, add reactions, upload files, use Slash commands | 1+ merged PR or verified community contribution |
| **Community** | Green (`#2ecc71`) | Send messages, add reactions, read message history | Default role on join |
| **Trainer** | Purple (`#9b59b6`) | Access to #training-help and model channels | Opt-in with `/role trainer` |
| **Learner** | Teal (`#1abc9c`) | Access to #tutorials and #course-material | Opt-in with `/role learner` |
| **Muted** | Dark gray (`#7f8c8d`) | Read-only access | Applied by moderators for rule violations |

### Role Assignment

- **Community**: Auto-assigned by Bot on join
- **Contributor**: Auto-assigned by GitHub.Bot on merged PR (link GitHub account)
- **Trainer/Learner**: Self-assigned via `/role` command (Carl-bot or similar)
- **Maintainer**: Manual assignment after nomination process
- **Muted**: Applied manually by moderators, with auto-removal timer

---

## Bot Setup

### Required Bots

#### 1. GitHub Bot (GitHub Integration)

**Purpose**: Link Discord to GitHub — issue notifications, PR tracking, contributor recognition.

**Setup Steps**:
1. Go to Server Settings → Integrations → Webhooks
2. Create a webhook for each relevant GitHub event type:
   - `#anvil-bugs`: New issues on `fableforge/anvil` repo
   - `#announcements`: New releases across all repos
   - `#ci-cd`: CI/CD workflow runs
3. Configure the GitHub App in the FableForge org settings:
   - Set up the Discord GitHub App from https://discord.com/developers/applications
   - Grant repo permissions: issues, pull_requests, releases, discussions
   - Set webhook URL to the Discord channel webhook
4. Auto-role: Configure the bot to assign the **Contributor** role when a user links their GitHub account and has a merged PR

#### 2. PyPI Release Bot (Custom or Release Radar)

**Purpose**: Announce new package releases to #announcements.

**Setup Steps**:
1. Add the Release Radar bot or configure a custom webhook:
   ```
   Webhook URL: https://discord.com/api/webhooks/<id>/<token>
   Package: anvil-ai
   Package: verifyloop
   Package: errorrecovery
   Package: fableforge-sdk
   ```
2. Configure format: `📦 **{package}** v{version} released! {changelog_url}`
3. Set channel: `#announcements`
4. Set mention: `@everyone` for major releases, `@Contributor` for patches

#### 3. Moderation Bot (Carl-bot or MEE6)

**Purpose**: Auto-mod, reaction roles, temp-mute, logging.

**Setup Steps**:
1. Add Carl-bot to the server: https://carl.gg
2. Configure auto-mod rules:
   - Spam detection: 5+ messages in 5 seconds → auto-mute for 5 minutes
   - Link-only messages in #anvil-help, #training-help: auto-delete (require context)
   - Profanity filter: enabled with custom word list
   - Mention spam: 5+ mentions in one message → auto-delete
3. Set up reaction roles:
   - 🏋️ Trainer role in #start-here
   - 📚 Learner role in #start-here
   - 🔔 Announcement pings in #announcements
4. Configure logging:
   - Message edits and deletes → #mod-log (private channel)
   - Joins and leaves → #mod-log
   - Kicks and bans → #mod-log

#### 4. Auto-Mod (Built-in Discord AutoMod)

**Purpose**: First line of defense against spam, slurs, and malicious links.

**Setup Steps**:
1. Server Settings → AutoMod
2. Create rules:
   - **Custom Word Filter**: Slurs, hate speech, harassment (maintain custom list)
   - **Spam**: Block messages from users without the Community role that contain 5+ emojis
   - **Link Protection**: Block suspicious domains in #general, #anvil-help, #training-help

---

## Moderation Guidelines

### Moderation Philosophy

FableForge follows a **progressive discipline** model. The goal is to educate, not punish. We assume good intent until proven otherwise.

### Moderation Actions

| Action | When to Use | Duration | Who Can Apply |
|--------|------------|----------|---------------|
| Friendly reminder | First minor infraction, genuine misunderstanding | N/A | Maintainer, Contributor |
| Warning | Repeated minor infractions, off-topic in help channels | N/A | Maintainer |
| Mute | Spamming, persistent off-topic, mild hostility | 1-24 hours (escalating) | Maintainer |
| Kick | Severe disruption, multiple warnings unheeded, doxxing attempts | Permanent removal from server | Admin, Maintainer |
| Ban | Hate speech, harassment, threats, spam bots, ban evasion | Permanent IP ban | Admin |

### Channel-Specific Moderation

- **#anvil-help, #training-help, #verifyloop**: Strict on-topic enforcement. Redirect off-topic to #general. Delete meme/low-effort posts.
- **#bugs, #integration**: Require issue template format. Redirect discussion-only posts to the corresponding discussion channel.
- **#announcements**: Maintainer-only posting. Reactions allowed, no replies.
- **#showcase**: No criticism without constructive feedback. Applaud first, critique second.
- **#general, #random**: Light moderation. Step in only for Code of Conduct violations.

### Moderation Workflow

1. **Identify**: Review reported messages in #mod-queue (private mod channel)
2. **Assess**: Determine severity and intent
3. **Act**: Apply the lightest effective action per the table above
4. **Document**: Log action in #mod-log with:
   ```
   [ACTION] @user — Reason — Duration — Moderator: @mod
   ```
5. **Follow-up**: If muted, check in after mute expires. If warned, watch for recurrence.

### Handling Sensitive Issues

- **Security vulnerabilities**: Immediately redirect to GitHub Security Advisories. Delete any public discussion of unpatched vulnerabilities. DM the reporter with a link to the responsible disclosure process.
- **Personal information**: Delete immediately. DM the poster explaining our privacy expectations.
- **Harassment**: Act immediately. No tolerance. Document everything in #mod-log.

---

## Welcome Message Template

When a new member joins, the bot should send the following message in `#welcome`:

```
👋 Welcome to FableForge, {user.name}!

We're building the open-source AI generation engine that actually works.
Here's how to get started:

1️⃣  Read the rules in #rules
2️⃣  Pick your roles in #start-here (🏋️ Trainer, 📚 Learner, or both!)
3️⃣  Introduce yourself in #introduction
4️⃣  Check out the docs: https://fableforge.readthedocs.io

Quick links:
📜 Docs:    https://fableforge.readthedocs.io
💻 GitHub:  https://github.com/KingLabsA
🐛 Issues:  https://github.com/KingLabsA/anvil/issues
💬 Discuss: https://github.com/KingLabsA/anvil/discussions

Need help? Drop a question in #anvil-help or #training-help.
Want to contribute? Check #contributing.

Happy forging! 🔨
```

---

## Rules and Code of Conduct

### Server Rules

These rules are posted in `#rules` (read-only, managed by admins):

---

**FableForge Community Code of Conduct**

We are committed to providing a welcoming and inclusive experience for everyone. By participating in this community, you agree to abide by the following rules:

**1. Be Respectful**
Treat everyone with respect. Disagreements are fine; personal attacks are not. Critique ideas, not people.

**2. Be Constructive**
When giving feedback, focus on how to improve. "This doesn't work" → "This approach has issues because X, have you considered Y?"

**3. Stay On-Topic**
Use the appropriate channels. Help channels are for help; general is for general discussion.
- #anvil-help, #training-help → Questions and troubleshooting only
- #general → Broad FableForge discussion
- #random → Anything else

**4. No Spam or Self-Promotion**
No unsolicited advertising, affiliate links, or promotion of unrelated products or services. Sharing your FableForge project in #showcase is always welcome.

**5. No Hate Speech or Harassment**
Zero tolerance for slurs, hate speech, targeted harassment, doxxing, or threats. This includes sexualized comments, discriminatory jokes, and microaggressions.

**6. Respect Privacy**
Do not share anyone's personal information without consent. This includes real names, addresses, employer info, or private communications.

**7. Security Vulnerabilities**
Do NOT post security vulnerabilities publicly. Report them through [GitHub Security Advisories](https://github.com/KingLabsA/anvil/security/advisories/new). Public disclosure before a fix is available harms users.

**8. English Only in Help Channels**
Keep help channels in English so the maximum number of people can benefit. Use #random for other languages.

**9. No Plagiarism**
Don't present others' work as your own. Always credit the original author.

**10. Follow GitHub's Community Guidelines**
This community also follows the [GitHub Community Guidelines](https://docs.github.com/en/site-policy/github-terms/github-community-guidelines).

---

**Enforcement**

Violations are handled per our moderation guidelines (progressive discipline):
1. Friendly reminder
2. Warning
3. Mute (1-24 hours)
4. Kick
5. Ban (for severe violations)

To report a violation, DM any Maintainer or use the `/report` command.

This Code of Conduct adapts the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

---

## Setting Up the Server

### Step-by-Step Setup

#### Step 1: Create the Server

1. Open Discord and click "+" → "Create My Own"
2. Name: **FableForge**
3. Upload the FableForge logo as the server icon
4. Set the server region to your primary audience region

#### Step 2: Create Categories and Channels

Create each category and its channels following the structure in the "Server Structure" section above.

For each channel, set the topic to the description from the "Channel Descriptions" section.

Settings for specific channels:
- `#rules`, `#announcements`, `#welcome`, `#start-here`: Set to **read-only** (only Maintainers/Admins can send messages)
- `#showcase`: Enable **slowmode** (1 message per 10 seconds) to encourage thoughtful posts
- `#anvil-help`, `#training-help`: Enable **slowmode** (1 message per 5 seconds) to prevent spam
- All channels: Enable **AutoMod** with the rules defined in the Bot Setup section

#### Step 3: Create Roles

Create roles in the order listed in "Role Setup" (Discord applies roles top-to-bottom, so Admin must be created first).

For each role:
1. Set the color as specified
2. Set permissions per the table
3. Set visibility: All roles visible, Muted role not mentionable

**Role order matters!** In Discord, roles are hierarchical. The top role has the most power. Ensure the order in Discord matches:

`Admin > Maintainer > Contributor > Trainer = Learner > Community > @everyone > Muted`

#### Step 4: Add Bots

1. **GitHub Bot**: Add via OAuth2 URL with `bot` and `applications.commands` scopes. Required permissions: Send Messages, Embed Links, Manage Roles, Read Message History.
2. **Carl-bot**: Add from https://carl.gg. Required permissions: Administrator (for auto-mod, reaction roles, and logging).
3. **PyPI Release Bot**: Add via webhook, not a full bot. Set up in Server Settings → Integrations → Webhooks.
4. **AutoMod**: Configure in Server Settings → AutoMod (built into Discord).

#### Step 5: Configure the Welcome Bot

In Carl-bot (or your chosen moderation bot), set up auto-welcome:

1. Go to Carl-bot dashboard → Welcome → Enable
2. Set channel: `#welcome`
3. Set message template (use the "Welcome Message Template" from above)
4. Enable DM welcome (optional): Send a shorter version via DM
5. Enable auto-role: Assign **Community** role on join

#### Step 6: Set Up Reaction Roles

In `#start-here`, create a message with reaction-role pairs:

```
 Pick your roles!
 🏋️ Trainer — Access to training and model channels
 📚 Learner — Access to tutorials and course materials
 🔔 Releases — Get pinged for new releases
```

Configure Carl-bot reaction roles:
- 🏋️ → Trainer role
- 📚 → Learner role
- 🔔 → Releases role (announcement pings)

#### Step 7: Post the Rules

Post the full "Rules and Code of Conduct" section as a message in `#rules`. Pin the message.

#### Step 8: Test Everything

- [ ] Join with a test account and verify auto-welcome message appears
- [ ] Verify reaction roles work in #start-here
- [ ] Test GitHub integration by opening a test issue
- [ ] Verify AutoMod catches spam and slurs
- [ ] Confirm all channels have correct permissions
- [ ] Test the mute command with a test account

#### Step 9: Announce

Post an announcement in `#announcements`:

```
🏁 FableForge Discord is LIVE!

Welcome to the official FableForge community server! Here's what you need to know:

📌 Read #rules before participating
👋 Introduce yourself in #introduction
❓ Get help in #anvil-help or #training-help
🛠️ Contribute in #contributing
📢 Stay updated in #announcements

We're excited to build the future of AI generation together. Let's forge! 🔨
```

---

## Maintenance

### Ongoing Tasks

- **Weekly**: Review #mod-log for patterns. Update AutoMod word filter.
- **Monthly**: Review channel activity. Archive dead channels. Update pinned messages.
- **On release**: Post changelog in #announcements. Update topic in relevant channels.
- **Quarterly**: Review role assignments. Clean up inactive roles. Audit bot permissions.

### Adding New Channels

When a new FableForge project is added:

1. Create a channel under the appropriate category
2. Set the topic with a description
3. Post a welcome message explaining the project
4. Update this document with the new channel
5. Announce in #announcements

### Archiving Channels

If a channel has been inactive for 90+ days:

1. Post a 7-day warning in the channel
2. After 7 days, set the channel to read-only
3. Archive after 30 more days of inactivity
4. Update this document

---

*This guide is maintained by the FableForge maintainers. Last updated: 2025-01-15. For questions, reach out in #contributing or open an issue on the [fableforge/fableforge](https://github.com/KingLabsA/anvil) repository.*
