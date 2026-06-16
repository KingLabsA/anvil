# FableForge Roadmap

## What's Done

We have **21 open-source projects**, **278 tests**, and **3 model training pipelines** built from **210,000+ real agent traces**.

### Projects (21/21)

| # | Project | Layer | Package | Tests | Status |
|---|---------|-------|---------|-------|--------|
| 1 | **Anvil** | Flagship | `anvil-agent` | 60+ | ✅ Complete |
| 2 | **VerifyLoop** | Frameworks | `verifyloop` | 20+ | ✅ Complete |
| 3 | **ErrorRecovery** | Frameworks | `error_recovery` | 25+ | ✅ Complete |
| 4 | **AgentSwarm** | Frameworks | `agent_swarm` | 15+ | ✅ Complete |
| 5 | **FableForge-14B** | Models | `fableforge-14b` | Scripts only | ✅ Complete |
| 6 | **ShellWhisperer** | Models | `shell_whisperer` | 10+ | ✅ Complete |
| 7 | **ReasonCritic** | Models | `reason_critic` | 10+ | ✅ Complete |
| 8 | **TraceCompiler** | Infrastructure | `trace_compiler` | 5+ | ✅ Complete |
| 9 | **AgentRuntime** | Infrastructure | `agent_runtime` | 8+ | ✅ Complete |
| 10 | **AgentTelemetry** | Infrastructure | `agent_telemetry` | 10+ | ✅ Complete |
| 11 | **BenchAgent** | Tools | `bench_agent` | 15+ | ✅ Complete |
| 12 | **AgentDev** | Tools | VS Code extension | — | ✅ Complete |
| 13 | **TraceViz** | Tools | `trace_viz` | — | ✅ Complete |
| 14 | **AgentSkills.org** | Data Products | `agent_skills` | 5+ | ✅ Complete |
| 15 | **AgentCurriculum** | Data Products | `agent_curriculum` | 5+ | ✅ Complete |
| 16 | **AgentFuzzer** | Data Products | `agent_fuzzer` | 5+ | ✅ Complete |
| 17 | **AgentConstitution** | Meta | `agent_constitution` | 10+ | ✅ Complete |
| 18 | **CostOptimizer** | Meta | `cost_optimizer` | 10+ | ✅ Complete |
| 19 | **AgentProfiler** | Meta | `agent_profiler` | 10+ | ✅ Complete |
| 20 | **TrajectoryDistiller** | Meta | `trajectory_distiller` | 10+ | ✅ Complete |
| 21 | **Fable5-Dataset** | Meta | `fable5_dataset` | 10+ | ✅ Complete |

### Infrastructure

- **CI/CD**: `.github/workflows/` for lint, test, and release
- **Demo**: `scripts/demo_ecosystem.sh` — end-to-end demonstration of all 9 major components
- **Training**: `scripts/train_all.sh` — orchestrated 3-model pipeline
- **Data**: `scripts/download_data.sh` — downloads all 6 Fable-5 datasets
- **Integration tests**: `integration_tests/test_ecosystem.py` — cross-component tests
- **CLI**: `ff` command with `run`, `verify`, `status`, `projects`, `demo`, `train`, `data`, `test`, `launch`

### Key Metrics

| Metric | Value |
|--------|-------|
| Total traces | 210,000+ |
| Unique sessions | ~145 |
| Unique tools | 31 |
| Planning rate | 87.7% |
| Error recovery rate | 39.5% |
| Longest session | 303 tool calls (15h) |
| Transition matrices | 6 tool × 6 tool |
| Error categories | 9 |
| Recovery patterns | 108 |
| Constitutional rules | 60 |
| Benchmark tasks | 107 |
| Training dataset rows | ~234,000 |

---

## What's Needed Before GitHub Push

### Phase 0: Pre-Release Hygiene (Week 1)

- [ ] **License headers**: Add MIT license header to every source file in all 21 projects
  - `# SPDX-License-Identifier: MIT` at top of every `.py` file
  - `// SPDX-License-Identifier: MIT` at top of every `.ts`/`.js` file
  - Use `addlicense` or a simple script to batch-apply
- [ ] **README badges**: Add CI, coverage, PyPI, license, and Discord badges to every project README
  - `[![CI](https://github.com/KingLabsA/{project}/actions/workflows/ci.yml/badge.svg)]`
  - `[![PyPI](https://img.shields.io/pypi/v/{package})]`
  - `[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)]`
- [ ] **CONTRIBUTING.md**: Create a consistent contributing guide referenced from all repos
  - Code style, PR checklist, commit message format, test requirements
- [ ] **SECURITY.md**: Add a security policy (responsible disclosure, contact email)
- [ ] **CODEOWNERS**: Set up code ownership for each project
- [ ] **Consistent `.gitignore`**: Ensure no build artifacts, `__pycache__`, `.env`, or model weights get committed
- [ ] **Consistent `pyproject.toml`**: Normalize build system, Python version (≥3.10), key metadata across all projects

### Phase 1: PyPI Publishing (Week 2)

- [ ] **Reserve package names** on PyPI for all 14 Python packages
- [ ] **Build and publish to TestPyPI** first, verify installation works
- [ ] **Tag v0.1.0** on all repos simultaneously
- [ ] **Publish to PyPI** with automated GitHub Actions
- [ ] **Verify `pip install`** works for every package on a clean Python 3.10+ environment
- [ ] **Create conda-forge recipes** (optional, for wider reach)

### Phase 2: Documentation (Weeks 2-3)

- [ ] **docs.fableforge.ai**: Set up a shared documentation site (MkDocs or Docusaurus)
  - Getting Started guide
  - Architecture overview with the stack diagram from the Manifesto
  - Per-project API reference (auto-generated from docstrings)
  - Tutorial: "From zero to self-verified agent in 5 minutes"
  - Tutorial: "Training your own model with Fable-5 data"
- [ ] **Jupyter notebooks**: Create walkthrough notebooks for each major workflow
  - `01_anvil_demo.ipynb`
  - `02_verifyloop_pipeline.ipynb`
  - `03_error_recovery.ipynb`
  - `04_agent_swarm.ipynb`
  - `05_training_pipeline.ipynb`
- [ ] **Video walkthrough**: 10-minute overview video linked from README
- [ ] **API reference**: Auto-generated with Sphinx or mkdocstrings

---

## Model Training Roadmap

### FableForge-14B — 4-Stage Training

| Stage | Method | Data | Hardware | Time | Est. Cost |
|-------|--------|------|----------|------|-----------|
| 1 | SFT (supervised fine-tuning) | 100K rows (coding excellence) | 2× A100-80GB | ~18h | ~$60 |
| 2 | SFT (tool-use chains) | 50K rows (multi-tool traces) | 2× A100-80GB | ~8h | ~$26 |
| 3 | DPO (preference optimization) | 20K pairs (chosen/rejected) | 2× A100-80GB | ~12h | ~$40 |
| 4 | Merging + export | — | 1× A100-80GB | ~7h | ~$12 |

**Total**: ~45h on 2× A100-80GB, ~$138

**Base model**: Qwen2.5-Coder-14B

### ShellWhisperer-1.5B — Edge Agent

| Stage | Method | Data | Hardware | Time | Est. Cost |
|-------|--------|------|----------|------|-----------|
| 1 | SFT | 50K rows (shell commands) | 1× A100-80GB | ~3h | ~$5 |
| 2 | ONNX export + INT8 quantize | — | 1× A100-80GB | ~1h | ~$2 |

**Total**: ~4h on 1× A100-80GB, ~$7

**Base model**: Qwen2.5-Coder-1.5B

### ReasonCritic-7B — Verification Model

| Stage | Method | Data | Hardware | Time | Est. Cost |
|-------|--------|------|----------|------|-----------|
| 1 | Contrastive learning | 20K pairs (pass/fail verification) | 1× A100-80GB | ~4h | ~$7 |
| 2 | LoRA fine-tuning | 50K rows (code review) | 1× A100-80GB | ~3h | ~$5 |
| 3 | DPO | 10K pairs (chosen/rejected verification) | 1× A100-80GB | ~3h | ~$5 |

**Total**: ~10h on 1× A100-80GB, ~$17

**Base model**: Qwen2.5-Coder-7B

### Training Summary

| Model | GPU Hours | Est. Cost |
|-------|-----------|-----------|
| FableForge-14B | ~90h (2× A100) | ~$138 |
| ShellWhisperer-1.5B | ~4h (1× A100) | ~$7 |
| ReasonCritic-7B | ~10h (1× A100) | ~$17 |
| Data download + convert | — | ~$0 (AWS S3) |
| GGUF/ONNX exports | ~4h | ~$8 |
| **Total** | **~108 GPU-hours** | **~$170** |

**Recommended hardware**: AWS p4d.24xlarge (8× A100-80GB, $32.77/hr) — total ~$170 for complete pipeline in ~2.6 days

**Minimum hardware**: 1× A100-80GB (train models sequentially) — total ~5 days, ~$100

**Alternative**: Use Lambda Labs or Vast.ai for lower cost (~$1-2/hr per A100)

---

## Coordinated Launch Plan

### Week -2: Soft Launch (Internal)

- [ ] Final repo review — every project passes `pytest` and `ruff check`
- [ ] Security audit — no secrets, no `.env` files, no model weights committed
- [ ] License audit — every file has MIT header, every `pyproject.toml` has correct license
- [ ] Dogfood — team uses Anvil for a full day of real work
- [ ] Run `scripts/demo_ecosystem.sh` on a clean machine — must pass without errors

### Week -1: Release Candidates

- [ ] Tag `v0.1.0rc1` on all repos
- [ ] Publish to TestPyPI
- [ ] Create GitHub Releases with auto-generated changelogs
- [ ] Create the website: `docs.fableforge.ai`
- [ ] Write the launch blog post
- [ ] Set up Discord server (see Community section)

### Week 0: Launch Day

- [ ] Tag `v0.1.0` on all 21 repos simultaneously
- [ ] Publish all packages to PyPI
- [ ] Publish the blog post
- [ ] Post to: Reddit (r/LocalLLaMA, r/MachineLearning, r/Python), Hacker News, X/Twitter
- [ ] Submit to: Papers With Code, Hugging Face Models, Awesome Lists
- [ ] Email the waitlist / early adopters

### Week +1: Post-Launch

- [ ] Fix any critical bugs from first 24 hours
- [ ] Respond to all GitHub Issues within 24 hours
- [ ] Publish first batch of community-contributed examples
- [ ] Begin FableForge-14B training (takes ~2.6 days)
- [ ] Publish models to Hugging Face

---

## Community Building

### Discord Server Structure

```
📚 announcements
   # release-notes
   # changelog
💬 general
   # introductions
   # show-and-tell
   # help
🔧 projects
   # anvil
   # verifyloop
   # error-recovery
   # agent-swarm
   # fableforge-14b
   # shell-whisperer
   # reason-critic
   # (one per project)
🧪 research
   # training-discussions
   # dataset-discussions
   # benchmark-results
🤝 contributing
   # good-first-issues
   # code-review
   # documentation
```

### Contributing Guide

1. **Code Style**: Ruff for linting, Black for formatting, mypy for type checking
2. **Tests**: Every PR must include tests. Target 80%+ coverage.
3. **Commits**: Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
4. **PRs**: Small, focused, with clear description. Max 400 lines per PR.
5. **Reviews**: 1 approval required for merges. 2 for model-related changes.

### First 30 Days Community Goals

| Metric | Target |
|--------|--------|
| GitHub stars (total) | 1,000 |
| Discord members | 200 |
| PyPI downloads (first week) | 500 |
| Community PRs | 10 |
| Blog posts / tutorials (external) | 5 |
| Issues resolved | 50 |

### Good First Issues (pre-seeded)

- Add type stubs (`.pyi`) for public APIs
- Create `examples/` directory with real-world workflows
- Translate README to 3 additional languages
- Add pre-commit hooks to all repos
- Create GitHub Actions for Windows/macOS CI
- Write a getting-started tutorial for each major project

---

## Long-Term Vision

### Phase 3: Model Hosting (Months 2-3)

- [ ] Host FableForge-14B on Hugging Face Inference Endpoints
- [ ] Host ShellWhisperer-1.5B as ONNX on Cloudflare Workers (50ms global)
- [ ] Host ReasonCritic-7B on Hugging Face for verification-as-a-service
- [ ] Create `anvil-agent` cloud mode that routes to hosted models
- [ ] Build a free tier (rate-limited) and a paid tier for model hosting

### Phase 4: Skill Marketplace (Months 3-6)

- [ ] Expand AgentSkills.org into a full skill marketplace
- [ ] Allow community-submitted skills with namespace (`@username/skill-name`)
- [ ] Build skill signing and verification (similar to npm signatures)
- [ ] Create skill rating system (downloads, stars, verified badge)
- [ ] Integrate skill publishing into the `ff` CLI:
  ```
  ff skills publish my-skill
  ff skills install @user/skill
  ff skills search "database migrations"
  ```

### Phase 5: Enterprise Offering (Months 6-12)

- [ ] **Self-hosted option**: Docker Compose + K8s Helm charts for on-premise deployment
- [ ] **Enterprise features**:
  - SSO/SAML integration
  - Audit logs
  - Custom constitutional rules
  - Fine-tuning on proprietary traces
  - Priority support
  - SLA guarantees
- [ ] **Pricing**: Usage-based (per-token or per-seat)
- [ ] **Compliance**: SOC 2 Type II, HIPAA-ready configuration

### Phase 6: Research & Growth (Year 2+)

- [ ] Publish a paper on the Fable-5 dataset and behavioral patterns
- [ ] Expand to multi-modal agents (vision, audio)
- [ ] Expand to non-coding domains (research, legal, medical)
- [ ] Build an agent evaluation leaderboard (BenchAgent-as-a-Service)
- [ ] Open-source a 70B model trained on expanded data
- [ ] Run the first FableForge conference

---

## Architecture Vision

```
                          ┌─────────────────────┐
                          │    docs.fableforge.ai │
                          └──────────┬──────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                                 │
          ┌─────────▼──────────┐          ┌──────────▼─────────┐
          │     Anvil Agent    │          │   Model Hosting    │
          │  (Self-Verified)   │          │  (HF + Cloudflare) │
          └─────────┬──────────┘          └──────────┬─────────┘
                    │                                 │
     ┌──────────────┼───────────────┐               │
     │              │               │               │
     ▼              ▼               ▼               ▼
┌─────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────┐
│VerifyLoop│  │ErrorRecovery│  │AgentSwarm   │  │CostOptimizer │
│         │  │(3,725 errs)│  │(6×6 matrix) │  │(50-80% save) │
└────┬────┘  └─────┬─────┘  └──────┬──────┘  └──────┬──────┘
     │             │               │                 │
     └─────────────┼───────────────┼─────────────────┘
                   │               │
          ┌────────▼──────────────▼────────┐
          │     AgentRuntime (daemon)       │
          │  Persistent • Sandbox • Metrics │
          └────────┬──────────────────────┘
                   │
     ┌─────────────┼───────────────┐
     │             │               │
     ▼             ▼               ▼
┌──────────┐ ┌──────────┐  ┌──────────────┐
│FableForge │ │ShellWhisp│  │ReasonCritic  │
│  -14B     │ │  er-1.5B │  │   -7B       │
│(coding)   │ │(edge)    │  │(verification)│
└──────────┘ └──────────┘  └──────────────┘
                   │
          ┌────────▼────────┐
          │   Fable-5 Data   │
          │  234K rows • 6   │
          │  sources • 31    │
          │  tools           │
          └─────────────────┘
```

---

## Timeline Summary

| Phase | Timeline | Key Milestones |
|-------|----------|----------------|
| 0: Pre-release | Week 1 | License headers, badges, CONTRIBUTING.md |
| 1: PyPI | Week 2 | Publish all 14 packages |
| 2: Docs | Weeks 2-3 | docs.fableforge.ai, notebooks, videos |
| Launch | Week 4 | v0.1.0, blog post, social media |
| 3: Models | Weeks 4-6 | Train FableForge-14B, ShellWhisperer, ReasonCritic |
| 4: Skills | Months 3-6 | Skill marketplace, community skills |
| 5: Enterprise | Months 6-12 | Self-hosted, SSO, audit logs |
| 6: Research | Year 2+ | Paper, multi-modal, 70B model |

---

*This is a living document. Update it as milestones are reached.*
