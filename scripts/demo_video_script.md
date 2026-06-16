# Anvil Demo Video Script

**Title:** Anvil — Where Code Gets Forged, Hammered, and Tested Until It Holds  
**Duration:** 5:00  
**Format:** 1920x1080, 30fps, terminal + screen recording  
**Music:** Industrial ambient, low and building — think forge bellows and hydraulic press  
**Voice:** Confident, slightly gravelly. Think senior engineer who's seen every production fire.

---

## Act 1: The Problem (0:00–0:30)

### Scene 1.1 — Cold Open (0:00–0:08)

**VISUAL:** Black screen. A single cursor blinks. The sound of a keyboard typing — but it's the sound of someone typing fast, then stopping, then backspacing.

**ON-SCREEN TEXT (typewriter effect):**

```
> ai write "implement user authentication"
```

**VOICEOVER:**
You've been there. You ask an AI to write code.

**CUT TO:**

### Scene 1.2 — The Broken Loop (0:08–0:22)

**VISUAL:** Terminal recording — actual footage sped up. An AI agent writes code. Tests are run. They fail. The agent hallucinates a fix. Tests fail again. The agent gives up or produces obviously wrong output.

**TERMINAL OUTPUT (speed 2x):**

```
running tests...
FAILED test_auth.py::test_login — AssertionError: expected 200, got 401
FAILED test_auth.py::test_session — RuntimeError: no active session

> Agent: I've added the session middleware...
> Agent: The tests should now pass.

running tests...
FAILED test_auth.py::test_login — AssertionError: expected 200, got 401
FAILED test_auth.py::test_session — RuntimeError: no active session

> Agent: Task complete.
```

**VOICEOVER:**
It writes code. It doesn't work. You debug it yourself. Every. Single. Time.

**CUT TO:**

### Scene 1.3 — The Blacksmith Metaphor (0:22–0:30)

**VISUAL:** Dramatic transition — the failed terminal output shatters like glass. We see a forge anvil, molten metal being hammered. The hammer strikes are synced to a heartbeat sound.

**ON-SCREEN TEXT:**

```
What if the agent
hammered until it held?
```

**VOICEOVER:**
What if the code was forged — hammered and tested, over and over, until it held?

**SMASH CUT TO:**

---

## Act 2: Introducing Anvil (0:30–1:30)

### Scene 2.1 — Logo and Tagline (0:30–0:38)

**VISUAL:** The Anvil logo forms from glowing amber particles that coalesce on a dark background. A hammer icon strikes, and sparks fly. The tagline appears beneath.

**ON-SCREEN TEXT:**

```
ANVIL
Where Code Gets Forged, Hammered, and Tested Until It Holds
```

**VOICEOVER:**
Meet Anvil — the self-verified coding agent.

### Scene 2.2 — The Loop Explained (0:38–1:05)

**VISUAL:** Clean animated diagram (dark background, amber accent lines). Four nodes connected in a cycle, each lighting up in sequence as it's described. The cycle repeats.

**ANIMATION SEQUENCE:**

1. **PLAN** — A brain icon lights up. Lines radiate outward showing task decomposition.
2. **EXECUTE** — A code icon lights up. Code appears in fragments around it.
3. **VERIFY** — A flask icon lights up. Green/red test results flash.
4. **RECOVER** — A wrench icon lights up. The red results turn green through targeted fixes.
5. Arrow connects RECOVER back to VERIFY — the loop is closed.

**VOICEOVER:**
Most coding agents follow a straight line: plan, then execute, then... hand it to you. Anvil closes the loop. It plans. It executes. Then it verifies — running real tests. And if those tests fail? It doesn't give up. It recovers — diagnosing the root cause, applying a targeted fix, and verifying again. The loop only stops when every test passes.

### Scene 2.3 — Why Verification Matters (1:05–1:15)

**VISUAL:** Split screen. Left: "Without Verification" — a descending staircase showing first-pass accuracy dropping from ~100% to ~42%. Right: "With Verification" — the same staircase, but each step has a recovery arrow that pushes accuracy back up, ending at ~89%.

**ANIMATION:** The left side path drops sharply. The right side path dips, then recovers, dips, then recovers — each time ending higher. The final right-side bar rises above the left.

**VOICEOVER:**
First-pass success rate for coding agents: about 42 percent. With Anvil's verify-recover loop: 89 percent. That's not incremental improvement. That's the difference between code that might work and code that does work.

### Scene 2.4 — The Uniqueness Statement (1:15–1:30)

**VISUAL:** Full-screen text on dark background with a subtle forge glow effect. Each line appears with a hammer-strike animation.

**ON-SCREEN TEXT (one line at a time):**

```
Anvil doesn't just write code.
It verifies it.
And if verification fails,
it fixes it.
The loop only stops
when tests pass.
```

**VOICEOVER:**
Anvil doesn't just write code. It verifies it. And if verification fails, it fixes it. The loop only stops when tests pass.

**TRANSITION:** Fade to black. Sound of a forge hammer striking once.

---

## Act 3: Live Demo (1:30–3:30)

### Scene 3.1 — Setup (1:30–1:42)

**VISUAL:** Clean desktop. Terminal opens. The camera is set up so we see real keystrokes — not a fake animation, actual terminal recording at normal speed with some slight acceleration for the install step.

**TERMINAL COMMANDS (typed live):**

```bash
$ pip install anvil-agent
# [install output scrolls, accelerated]
Installing anvil-agent-0.9.1 ... done

$ python -c "import anvil; print(anvil.__version__)"
0.9.1
```

**VOICEOVER:**
Let's see it in action. Install Anvil with pip. That's it — no special setup, no Docker, no cloud keys needed for local models.

### Scene 3.2 — Demo: Fix a Bug (1:42–2:12)

**VISUAL:** Terminal continues. We run an Anvil command. The output shows the full verify-recover loop in real time.

**TERMINAL OUTPUT:**

```bash
$ anvil run "Fix the off-by-one error in users.py"

⊕ Planning:  Analyzing users.py for boundary conditions...
⊕ Execute:   Replacing range(1, n+1) with range(0, n) at line 47
⊕ Verify:    Running pytest...
  FAIL test_users.py::test_pagination — AssertionError: expected 10, got 9
✗ Recover:   Root cause: boundary condition in page[page*size:(page+1)*size]
⊕ Execute:   Fixing slice: adjusting to items[page*size:(page+1)*size]
⊕ Verify:    Running pytest...
  PASS test_users.py::test_pagination ✓
  PASS test_users.py::test_user_creation ✓
  PASS test_users.py::test_delete_user ✓
✓ All 3 tests pass — verification complete

Duration: 12.4s | Loops: 2 | Tokens: 4,231
```

**VOICEOVER:**
We tell Anvil to fix an off-by-one error. It plans first — understanding the boundary condition. It makes a fix. First verify: three tests, one failure. It reads the error message — not just the test name, the actual assertion. It recovers: pinpoints the exact line, fixes the page slicing logic. Second verify: all tests pass. Done. Twelve seconds, two loops.

### Scene 3.3 — Demo: Add a Feature (2:12–2:45)

**VISUAL:** Same terminal, new command.

**TERMINAL OUTPUT:**

```bash
$ anvil run "Add rate-limiting middleware to the API"

⊕ Planning:  Scanning api.py for endpoints (4 found)
             Mapping middleware patterns from training data...
⊕ Execute:  Creating rate_limiter.py — sliding window algorithm
⊕ Execute:  Adding @rate_limit decorator to 4 endpoints in api.py
⊕ Verify:   Running pytest...
  FAIL test_api.py::test_rate_limit — TimeoutError: request was not blocked
✗ Recover:  Analysis: window size 60000ms too high for test env
             Fix: injecting TEST_RATE_LIMIT_MS=100 via environment flag
⊕ Execute:  Updating rate_limiter.py to read TEST_RATE_LIMIT_MS env var
⊕ Verify:   Running pytest...
  PASS test_api.py::test_rate_limit ✓
  PASS test_api.py::test_bypass_limit ✓
  PASS test_api.py::test_unauthorized ✓
✓ All 3 tests pass — feature added

Duration: 28.7s | Loops: 2 | Tokens: 8,102
```

**VOICEOVER:**
Now a feature: add rate limiting. Anvil scans the codebase, finds four endpoints, creates the middleware, adds decorators — and on first verify, one test fails because the rate limit window is too slow for the test environment. It reads the test timeout, adjusts the timing, re-verifies. Feature added, all tests green.

### Scene 3.4 — Demo: Refactoring (2:45–3:10)

**VISUAL:** Same terminal, refactoring command.

**TERMINAL OUTPUT:**

```bash
$ anvil run "Refactor database layer to async/await"

⊕ Planning: Mapping sync DB calls across 12 files...
             Identifying asyncio migration patterns...
⊕ Execute: Converting db.py: fetch_one → afetch, execute → aexecute
⊕ Execute: Updating 8 query functions to async in queries.py
⊕ Verify:  Running pytest...
  FAIL test_db.py::test_connection — RuntimeError: no current event loop
✗ Recover: Root cause: tests provide no event loop for async functions
             Fix: adding asyncio.run() wrapper in conftest.py fixture
⊕ Execute: Creating event_loop pytest fixture in conftest.py
⊕ Verify:  Running pytest...
  PASS test_db.py::test_connection ✓
  PASS test_db.py::test_query_async ✓
  PASS test_db.py::test_transaction_rollback ✓
✓ All 3 tests pass — refactor complete

Duration: 45.2s | Loops: 2 | Tokens: 12,847
```

**VOICEOVER:**
Refactoring is where most agents fall apart — too many moving parts. Anvil maps all 12 files, migrates the sync calls to async, and on first verify, catches the missing event loop. It adds the pytest fixture, re-verifies, and the refactor is clean. Twelve files, forty-five seconds, zero manual debugging.

### Scene 3.5 — Daemon Mode and Model Switching (3:10–3:30)

**VISUAL:** Split terminal view. Left: Anvil running in daemon mode. Right: showing model switching.

**TERMINAL OUTPUT (left panel):**

```bash
$ anvil daemon --watch src/

🔍 Watching src/ for changes...
✓ Detected change: src/models/user.py
⊕ Planning... ⊕ Executing... ⊕ Verifying...
✓ All tests pass — auto-fixed

🔍 Watching src/ for changes...
```

**TERMINAL OUTPUT (right panel):**

```bash
$ anvil run "Fix the type errors" --model local

Using model: local (FableForge-14B-Q4)
⊕ Running verify loop...

$ anvil run "Fix the type errors" --model gpt4

Using model: gpt-4-turbo
⊕ Running verify loop...

$ anvil run "Fix the type errors" --model claude

Using model: claude-3-opus
⊕ Running verify loop...
```

**VOICEOVER:**
Anvil also runs as a daemon — watching your source directory and auto-fixing as you code. And with six model backends, you can switch between local models for speed, GPT-4 for complexity, or Claude for reasoning. Same verification loop, different brain.

---

## Act 4: The Ecosystem (3:30–4:30)

### Scene 4.1 — Ecosystem Overview (3:30–3:50)

**VISUAL:** Animated diagram showing all 21 projects as nodes in a network. Nodes pulse with amber light as they're described. Lines connect related projects. The diagram has four quadrants: Core (top-left), Models (top-right), Data (bottom-left), Infra (bottom-right).

**VOICEOVER:**
Anvil isn't just one tool. It's an ecosystem of 21 projects built to work together.

### Scene 4.2 — The Core Four (3:50–4:02)

**VISUAL:** The four core projects light up in sequence.

**ON-SCREEN:**

```
Anvil          → The self-verified coding agent (orchestrator)
VerifyLoop     → The verification loop engine (test runner + signal parser)
ErrorRecovery  → Targeted error diagnosis and fix generation
AgentSwarm     → Multi-agent orchestration for parallel tasks
```

**VOICEOVER:**
At the core: Anvil orchestrates everything. VerifyLoop runs the tests and parses failures. ErrorRecovery diagnoses root causes. AgentSwarm splits tasks across parallel agents when one brain isn't enough.

### Scene 4.3 — The Three Models (4:02–4:12)

**VISUAL:** Three model cards appear with architecture diagrams.

**ON-SCREEN:**

```
FableForge-14B     → Full code understanding + verification head
ShellWhisperer-1.5B → Shell command generation for terminal interaction
ReasonCritic-7B    → Reasoning verification — catches hallucinations
```

**VOICEOVER:**
Three purpose-built models: FableForge-14B for code generation and verification. ShellWhisperer — 1.5 billion parameters, lightning-fast for terminal commands. And ReasonCritic, a 7-billion parameter model that does one thing extremely well: verifying reasoning and catching mistakes before they ship. And yes — you can train all of them for free on Colab.

### Scene 4.4 — Data and Infra (4:12–4:22)

**VISUAL:** Data pipeline and infrastructure components animate in.

**ON-SCREEN:**

```
Data:
├── FableForge Dataset (210K+ verified traces)
├── TrajectoryDistiller (filter + clean raw traces)
└── TraceCompiler (tokenize + compile for training)

Infra:
├── Anvil Runtime (sandboxed execution + monitoring)
├── Telemetry (trace every loop, every token)
└── BenchAgent (automated benchmark evaluation)
```

**VOICEOVER:**
The entire pipeline is open: 210,000-plus verified agent traces in the dataset. The Distiller filters raw traces into high-quality training data. The Compiler tokenizes and structures it. On the infra side, the Runtime gives you sandboxed execution, Telemetry traces every loop, and BenchAgent runs your benchmarks automatically.

### Scene 4.5 — The Full Picture (4:22–4:30)

**VISUAL:** The entire diagram zooms out to show all 21 projects connected. A data flow animation shows traces going from Anvil, through the Distiller, into training, producing models, which power Anvil again — a virtuous cycle.

**VOICEOVER:**
Every component feeds the others. More traces make better models. Better models make better agents. Better agents make better traces. The forge sharpens itself.

---

## Act 5: Call to Action (4:30–5:00)

### Scene 5.1 — Train Your Own Model (4:30–4:42)

**VISUAL:** Screen recording of a Google Colab notebook. A simple interface shows model selection, dataset upload, and a "Start Training" button. The user clicks it, and a progress bar fills.

**ON-SCREEN TEXT:**

```
Train Your Own Model — Free on Colab

1. Open the Colab notebook
2. Select a base model
3. Upload your traces (or use FableForge Dataset)
4. Click "Start Training"
5. Download your model weights
```

**VOICEOVER:**
Every model in the FableForge ecosystem can be trained on your own data, for free, on Google Colab. Open the notebook, select a base, upload your traces — or use ours — and click start. Your model, your data, your forge.

### Scene 5.2 — Open Source Call (4:42–4:52)

**VISUAL:** GitHub star count animating upward. The FableForge org page is shown with all 21 repos listed. PRs and Issues counts are visible. A "CONTRIBUTING.md" file is highlighted.

**ON-SCREEN TEXT:**

```
★ Star us on GitHub
→ github.com/KingLabsA

Every issue, every PR, every trace makes Anvil stronger.
```

**VOICEOVER:**
Star us on GitHub. Every issue you file, every PR you submit, every trace you contribute — it all goes back into the dataset, making every model better for everyone.

### Scene 5.3 — Join the Community (4:52–4:56)

**VISUAL:** Discord server preview. Active channels, people asking questions, sharing traces. The "agent-design" channel is highlighted.

**ON-SCREEN TEXT:**

```
Join 2,000+ builders on Discord
→ discord.gg/fableforge
```

**VOICEOVER:**
Join two thousand builders on Discord. Share your traces, get help, and shape the future of self-verified agents.

### Scene 5.4 — Final Frame (4:56–5:00)

**VISUAL:** Pure black screen. The Anvil hammer logo glows in amber. Below it, the tagline.

**ON-SCREEN TEXT:**

```
ANVIL
Where Code Gets Forged, Hammered, and Tested Until It Holds

github.com/KingLabsA
```

**VOICEOVER:**
Anvil. Where code gets forged, hammered, and tested — until it holds.

**MUSIC:** Final hammer strike rings out and fades.

---

## Production Notes

### Terminal Recording Specifications
- **Resolution:** 1920x1080, 30fps minimum
- **Terminal:** iTerm2 with custom Anvil theme (dark background, amber accent)
- **Font:** JetBrains Mono, 16pt
- **Shell:** Zsh with minimal prompt showing only `$ `
- **Recording tool:** `asciinema` or `terminalizer` for crisp playback
- **Post-processing:** No fake typing — use real terminal sessions sped up via `asciinema` speed control
- **Color scheme:** Black background (#0a0a0a), amber text (#f59e0b) for Anvil output, green (#22c55e) for pass, red (#ef4444) for fail

### B-roll Suggestions
- **Act 1:** Real terminal footage of other agents (Cursor, Copilot, etc.) producing broken code
- **Act 2:** Blacksmith footage — hammer on anvil, sparks, quenching — licensed from stock or original
- **Act 3:** Clean screen recordings of actual Anvil sessions — no mockups
- **Act 4:** Animated architecture diagrams created in Figma or similar, exported as video
- **Act 5:** Colab notebook recording, GitHub org page, Discord preview

### Voiceover Timing
- **Act 1:** 30 seconds — punchy, frustrated tone
- **Act 2:** 60 seconds — confident, explanatory, building energy
- **Act 3:** 120 seconds — excited but measured, letting the terminal speak for itself
- **Act 4:** 60 seconds — fast-paced, showing breadth without dwelling
- **Act 5:** 30 seconds — warm, inviting, community-focused

### Music Directions
- **Act 1:** Low, ambient tension. Slow heartbeat.
- **Act 2:** Building industrial percussion. Think testing forge startup.
- **Act 3:** Driving techno beat — minimal, steady. Terminal output IS the rhythm.
- **Act 4:** Layered — each project added is a new synth layer building up.
- **Act 5:** Resolve. Beat drops to single hammer strike. Silence.

### Captioning
- All voiceover should be captioned in white text with dark background (90% opacity)
- Font: Inter, 24pt, centered bottom of frame
- Sound effects (forge, hammer, sparks) are NOT captioned — they're ambient
- Terminal commands and output are NOT captioned — they're visible on screen
- On-screen text cards are NOT captioned — they ARE the visual

### Thumbnail Options
1. **Hammer + Code:** Anvil hammer with glowing amber code fragments flying off
2. **Loop Diagram:** The Plan→Execute→Verify→Recover cycle with "89% vs 42%" in large text
3. **Terminal + Sparks:** Split — terminal on left, forge sparks on right, "Tests Pass or It Doesn't Ship" across the top

### Distribution
- **YouTube:** Standard 16:9 upload
- **Twitter/X:** 60-second cut of Act 3 demo only
- **LinkedIn:** 90-second cut of Acts 1+2+5
- **Discord:** Full 5-minute embed + 60-second GIF of the verify loop
- **GitHub README:** 60-second embed in the hero section

### Revision History
| Version | Date | Author | Notes |
|---------|------|--------|-------|
| 1.0 | 2025-06-15 | FableForge Team | Initial script |

---

*End of script.*