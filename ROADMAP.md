# Standalone Orchestrator — Roadmap

## Current State (v0.5.1 — Feb 2026)
Core loop working: EXPLORE → PLAN → BUILD → POST-BUILD VERIFY → RCA → REPLAN
- 11/11 memory tests passing
- **v0.5.1: Context budget management** — all prompt sections budget-capped to prevent context window bloat on multi-file tasks
- **v0.5.0: Post-build verification architecture** — commands generated from actual code on disk, not plan-time predictions
- **v0.5.0: Enriched RCA** — feeds actual stderr, git diff, file contents into 5 Whys analysis
- **v0.5.0: Eliminated sanitizer pipeline** — removed 179 lines of heuristic duct tape
- Structured output for plan, explore, and RCA agents (JSON schema mode)
- Conversation memory across iterations with structured DoD tracking
- LLM-based 5 Whys RCA with action injection into replanning
- Stuck-loop detection (fingerprinting + 3x threshold)
- Safety rails on destructive commands + .gitignore protection
- Auto-backup before each build iteration
- Auto-dependency installation before verification
- Primary model: Llama 3.3 70B (plan + build), Qwen 2.5 Coder 7B (explore + test)

### Proven Results
| Task | DoD | Iterations | Time | Version |
|------|-----|-----------|------|---------|
| Calculator | 7/7 | 1 | ~5.5m | v0.4 |
| Eigenvalue | 5/5 | 1 | ~5m | v0.4.1 |
| Flask REST API | 6/6 | 2 | ~8m | v0.4.1 |
| Flask REST API | 5/5 | 2 | ~8m | v0.4.2 |

---

## Stabilization (Active)

- [ ] Verify stuck-loop detection triggers correctly (should bail at 3 repeats)
- [ ] Verify conversation memory injects into iteration 2+ build prompts
- [ ] Re-run Flask API test with v0.4.3 — should pass in 1 iteration now (auto-deps)
- [ ] Test with a complex task (multi-module, inter-file dependencies)
- [ ] Test Qwen3 native tool calling (pull qwen3:8b, swap into config)

---

## Tier 1: High Impact, Local Only (No Paid API)

- [x] ~~Structured exploration reports~~ ✅ v0.4
- [x] ~~5 Whys RCA via LLM~~ ✅ v0.4
- [x] ~~Structured test reports~~ ✅ v0.4
- [x] ~~Git init in initializer phase~~ ✅ v0.4
- [x] ~~Qwen3 native tool calling support~~ ✅ v0.4.2 (infrastructure ready, configs defined)
- [x] ~~.gitignore protection~~ ✅ v0.4.2
- [x] ~~Auto-dependency installation before verification~~ ✅ v0.4.3
- [x] ~~RCA action injection into replan prompts~~ ✅ v0.4.1
- [x] ~~Post-build verification architecture~~ ✅ v0.5.0
  Commands generated from actual workspace, not plan-time predictions.
  Eliminated sanitizer pipeline (179 lines of heuristic duct tape removed).
- [x] ~~RCA evidence enrichment~~ ✅ v0.5.0
  Feeds actual stderr, git diff, file contents into 5 Whys analysis.
  RCA can now reason about code, not just about vague error summaries.

- [ ] **Qwen3 model testing**
  Pull qwen3:8b or qwen3:30b-a3b and validate native tool calling end-to-end.
  Configs are ready in standalone_config.py — just uncomment and swap.

- [ ] **Node.js / npm project support**
  Detect package.json in auto-deps, run `npm install` before verification.
  Extend initializer to optionally create node projects.

---

## Tier 2: Smarter Orchestration

- [ ] **Context compaction (full)**
  v0.5.1 added budget caps per prompt section. Next step: dynamic budgets based on
  actual model context_window, and summarization of old iterations (not just truncation).
  Impact: Enables 10+ iteration tasks without degradation.

- [ ] **Subagent delegation**
  Spawn isolated subtasks with separate context windows.
  Impact: Main build context stays clean for implementation.

- [ ] **Tracing / structured observability**
  JSON span logging per AGENTS_2 schema (trace_id, span_id, duration, tokens).
  Impact: Debug failing runs faster, performance profiling.

- [ ] **Parallel agent execution**
  Run explore on secondary node while plan runs on primary.
  Impact: Faster iteration cycles (currently sequential).

- [ ] **Task dependency graph (DAG with cycle detection)**
  Express "task B depends on task A finishing" for multi-module builds.
  Enables parallel building of independent modules.
  Reference: Claude Code uses numbered JSON task files with dependency fields.

- [ ] **Filesystem-based message passing**
  JSON inbox files for inter-agent communication (no HTTP, no database).
  Structure: `.agents/inboxes/<agent>/` with fcntl file locks.
  Fits the no-external-services philosophy.
  Reference: Claude Code uses `~/.claude/teams/<team>/inboxes/` with the same pattern.

- [ ] **Atomic state writes**
  Use `fcntl` locks or atomic rename (`write-to-temp → rename`) for state.json,
  memory.json, and session files. Required before parallel execution — current
  direct writes would race.

- [ ] **GLM-4.7 Flash as build model**
  AGENTS_2 spec calls for this. Need to test if it handles tool calling.
  Impact: Potentially faster builds if it's more code-focused than Qwen.

---

## Tier 3: Multi-Agent Coordination

These features enable true multi-agent parallelism — multiple build agents
working on different parts of the same project simultaneously.

Architecture reference: Claude Code's team mode uses tmux splits with each
agent as a separate CLI process. Coordination is entirely filesystem-based —
no database, no daemon, no network layer. Messages are JSON files guarded
by fcntl locks. Tasks are numbered JSON files with dependency tracking.

- [ ] **tmux-based multi-agent spawning**
  Each agent runs as a separate process in a tmux split.
  Orchestrator manages lifecycle (spawn, monitor, kill).
  Each agent gets its own context window and tool executor.
  Visual: side-by-side tmux panes showing agents working in parallel.

- [ ] **Structured inter-agent protocol**
  Formal message types: task_assignment, progress_update, completion,
  shutdown_request, plan_approval, error_report.
  JSON schema for each message type.
  Enables graceful coordination when one agent needs to pause or
  get approval before proceeding.

- [ ] **Shared workspace with file locking**
  Multiple build agents writing to the same project directory.
  File-level locks prevent concurrent writes to the same file.
  Merge strategy when agents modify related files.

- [ ] **Agent specialization per module**
  For multi-module projects, assign different agents to different modules.
  Each agent gets a subset of the plan focused on their module.
  Coordinator merges and runs integration tests.

---

## Tier 4: Requires Paid API or New Infra

- [ ] **Claude Opus as orchestrator/planner**
  Use Anthropic API for planning and coordination (highest quality).
  Keep build/explore/test on local Ollama models.
  Impact: Dramatically better plans and RCA. Cost: ~$0.10-0.50/task.

- [ ] **MCP integration**
  Replace direct tool execution with Model Context Protocol servers.
  Impact: Standardized tooling, easier to add new capabilities.

- [ ] **Browser automation (@test via Playwright)**
  End-to-end testing for web projects.
  Impact: Enables UI project verification.

- [ ] **LLM-as-Judge evaluation**
  Score completed work on correctness, pattern adherence, error handling.
  Impact: Quality gate beyond pass/fail DoD.

---

## Completed

### v0.6.2 — Regression Protection + Error-Aware Re-Sampling + Trace Collector
- [x] **Fix 1: Snapshot Protection** (Augment/Verdent pattern)
  - `_snapshot_passing_files()` — snapshots all syntactically valid .py files before retry builds
  - `_rollback_regressions()` — after retry build, checks if any passing files regressed
  - Auto-restores files that had syntax broken or lost passing tests
  - Prevents the "retry nukes working code" problem seen in v0.5.x and v0.6.0
- [x] **Fix 2: Error-Aware Re-Sampling** (bug localization research)
  - Wave 1 failures now capture actual error output (pytest/unittest traceback)
  - Error output injected into Wave 2 prompts: "Previous attempts failed with X, avoid this"
  - Based on research: "diverse sampling alone is ineffective when descriptions are vague"
- [x] **Fix 3: Second Wave Sampling** (Agentless pattern)
  - When all 4 Wave 1 candidates fail, launches Wave 2 with 4 more candidates
  - Wave 2 uses different temperatures (0.4, 0.7, 0.9, 1.1) for diversity
  - Wave 2 gets error context from Wave 1 — models see what went wrong
  - Up to 8 total candidates per test file (vs 4 in v0.6.1)
  - Agentless generates up to 40 samples; 8 is practical for local GPU inference
- [x] **Trace Collector** (ML + LLM Co-Training Loop)
  - `standalone_trace_collector.py` — captures failure trajectories automatically
  - Records: prompt, generated code, error output, model, temperature, error category
  - Auto-classifies errors: import_error, name_error, argparse_error, datetime_error, etc.
  - `export_for_claude()` — markdown format for pasting to Claude/GPT-4 for reasoning traces
  - `export_for_training()` — JSONL format for LoRA fine-tuning pipeline
  - `export_training_pairs()` — ready-to-use LoRA training data (after Claude distillation)
  - Pipeline: run orchestrator → traces collected → paste to Claude → get reasoning → LoRA fine-tune

### v0.7.0 — Multi-Model Routing (PLANNED)
- Use 70B for planning/RCA, 15B for source files, 9B for simple tasks
- Cascade routing: if 15B fails a test, try 70B (different training → different mistakes)
- DisCIPL pattern: big planner delegates to small executors

### v0.8.0 — Intra-File PRM (PLANNED)
- Build test files function-by-function with verification between each method
- Process Reward Model: verify each reasoning step, not just final output

### v1.0.0 — LoRA-Enhanced Models (PLANNED)
- Fine-tune 15B/9B on distilled reasoning traces from Claude/GPT-4
- Hot-swap LoRA adapters: test_writer.lora, argparse_testing.lora, etc.
- Self-improving: new failures → new traces → retrain → deploy

### v0.6.1 — Multi-Patch Sampling for Test Files (Agentless/Best-of-N)
- [x] `_sample_test_file()` — generates N candidates at different temperatures (0.3, 0.6, 0.8, 1.0)
- [x] Each candidate validated by actually running `pytest` / `unittest` — deterministic, no LLM judge
- [x] First candidate with ALL tests passing wins immediately (early exit)
- [x] If none pass, keeps best candidate (most tests passing)
- [x] `_run_test_file()` — runs test file, parses pytest/unittest output for pass/fail/error counts
- [x] Temperature parameter threaded through `_run_agent` → LLMClient
- [x] Only applies to test files — source files still use standard single-build
- [x] Inspired by Agentless (SWE-bench): sampling + validation > iterative fixing
- [x] Solves: datetime.now() equality bug, meaningless assertions, test logic errors
- [x] Cost: ~4x inference for test files only (~60s per test file vs ~15s)

### v0.6.0 — Sequential Micro-Build Architecture ("One Brick at a Time")
- [x] `_decompose_build_sequence()` — parses plan into ordered single-file build steps
- [x] Dependency-aware ordering: models → storage → cli → tests
- [x] `_run_micro_builds()` — loops through files one at a time with verification between each
- [x] `run_build_single_file()` — focused single-file prompt with:
  - File manifest showing what's been built and their exports
  - Dependency context: actual source code of imported modules
  - Source context for test files: shows the module being tested
- [x] `_verify_single_file()` — py_compile + import check after each file
- [x] `_extract_exports()` — extracts class/function names for manifest
- [x] Auto-detects multi-file tasks and uses micro-builds on iteration 1
- [x] Falls back to monolithic build for single-file tasks and retries
- [x] Inspired by MIT DisCIPL, Spotify verification loops, and the principle
  that 70B models nail single-file tasks but fail on multi-file

### v0.5.5 — Direct RCA-to-Build Injection (Spotify/Atla Pattern)
- [x] RCA schema enhanced with `concrete_edits` field — array of exact file/action/details
- [x] RCA system prompt demands precise edit commands, not vague natural language
- [x] Raw `rca_data` stored in failure_history for direct access by build agent
- [x] `_build_rca_edits_section()` formats concrete edits as mandatory first actions
- [x] Build agent fix mode injects RCA edits BEFORE any other work
- [x] Bypasses "telephone game": RCA → Plan → Build where actions get diluted
- [x] Inspired by: Spotify verification loops (precise error messages), Atla actor-critic
  research (concrete critiques boost performance ~30% vs vague instructions)

### v0.5.4 — Inner-Loop Lint Guard (Industry-Standard Pattern)
- [x] Lint guard on write_file: py_compile runs immediately after writing any .py file
- [x] Lint guard on edit_file: same check after edits
- [x] Error returned inline to build agent in same turn (no wasted iteration)
- [x] Shows exact line number, surrounding context with >>> marker, and common fix hints
- [x] File kept on disk so agent can read_file and fix (matches SWE-agent pattern)
- [x] Pattern inspired by Aider (lint-after-every-edit) and SWE-agent (reject bad edits with guardrails)
- [x] Syntax pre-check in verification still runs as safety net for edge cases

### v0.5.3 — Testing Pattern Hints + Syntax Pre-Check
- [x] Added TESTING PATTERNS section to build agent prompt with concrete code examples
- [x] CLI/argparse pattern: patch sys.argv instead of manual Namespace objects
- [x] File I/O pattern: tempfile or setUp/tearDown cleanup
- [x] Import safety pattern: argparse/input/sys.exit must be guarded
- [x] Added PYTHON PATTERNS section: correct @dataclass decorator syntax with wrong example shown
- [x] Syntax pre-check in post-build verification: py_compile all source files before running tests
- [x] Fast-fail on SyntaxError: reports exact file + line + error, skips test execution entirely
- [x] RCA gets precise "SyntaxError in models.py line 6" instead of vague import failures

### v0.5.2 — Retry Fix Mode (Multi-File Task Fix)
- [x] Build agent "fix mode" on retry iterations: reads existing files first, uses targeted edits instead of full rewrites
- [x] Plan agent shows PASSING criteria (not just failures) and instructs to preserve them
- [x] Plan agent told not to inflate DoD criteria count on retries
- [x] Build agent instructions differentiate iteration 1 (write_file) vs retries (read_file → edit_file)
- [x] Removed contradictory "prefer write_file over edit_file" instruction

### v0.5.1 — Context Budget Management
- [x] `context_window` field on ModelConfig (128K Llama 3.3, 32K Qwen 2.5, 256K Qwen3-Coder-Next)
- [x] Budget utility functions: `estimate_tokens()`, `truncate_to_budget()`, `truncate_diff()`
- [x] `_gather_rca_evidence()` — per-section budgets (file_listing, diff_stat, diff_content, test_files, source_files) with 8K total hard cap
- [x] `run_rca()` — budget-capped prompt assembly (failure_context 3K, evidence 8K, plan 2K, history 1.5K, total 16K)
- [x] `run_plan()` — budget caps on failure_context (4K) and exploration_context (3K)
- [x] `run_build()` — budget caps on memory_context (6K), plan_context (8K), dod_context (2K)
- [x] `ConversationMemory.get_context()` — total_budget parameter with per-iteration allocation and smart head+tail truncation
- [x] Token estimation logging in RCA for observability
- [x] All existing tests pass (11/11 memory tests, all compile checks)

### v0.5.0 — Post-Build Verification Redesign
- [x] Post-build verification: commands generated from actual workspace, not plan-time predictions
- [x] Eliminated verification sanitizer pipeline (removed _sanitize_verification_command, _convert_long_python_c_to_script, _simplify_verification_for_description, _infer_verification_command — 179 lines)
- [x] RCA evidence enrichment: feeds actual stderr, git diff, file contents, workspace listing into 5 Whys
- [x] Plan schema updated: DoD criteria now have description + verification_type + target_file (no verification_command)
- [x] DoDCriterion.target_file field for file-specific verification hints
- [x] Stale test file exclusion built into post-build scanner (was v0.4.4 patch, now integrated)
- [x] Printf/python3 -c sanitization no longer needed (commands not generated at plan time)

### v0.4.3
- [x] Auto-dependency installation before verification (requirements.txt, setup.py, pyproject.toml)

### v0.4.2
- [x] .gitignore protection (agents can't remove venv/ from .gitignore)
- [x] Native tool calling infrastructure (ModelConfig flags, tool_name in results, Qwen3 configs)
- [x] `<think>` block stripping from native tool call responses

### v0.4.1
- [x] Long python3 -c conversion to printf pipeline *(superseded by v0.5.0 post-build verification)*
- [x] Universal fallback in verification command simplifier *(superseded by v0.5.0)*
- [x] RCA action injection into plan prompt (MANDATORY FIX section)
- [x] Explicit 150-char length constraint on verification commands *(superseded by v0.5.0)*

### v0.4.0
- [x] Structured exploration reports (EXPLORE_OUTPUT_SCHEMA)
- [x] LLM-based 5 Whys RCA (RCA_OUTPUT_SCHEMA, run_rca method)
- [x] Structured test reports (TEST_REPORT_SCHEMA + failure reason extraction)
- [x] Git init in initializer phase (deterministic setup before LLM)

### v0.3.0
- [x] Standalone system (no opencode dependency)
- [x] Direct Ollama API integration
- [x] Fallback tool-call parser for Qwen text-embedded JSON
- [x] Safety rails (blocks rm -rf, protected paths)
- [x] Direct DoD verification (bypasses unreliable 7B test agent)
- [x] Auto-backup system (snapshots before each build)
- [x] Venv detection in verification
- [x] Command inference for missing verification commands
- [x] Structured output for plan agent (PLAN_OUTPUT_SCHEMA)
- [x] Conversation memory (ConversationMemory class + persistence)
- [x] Memory injection into build agent prompts
- [x] Stuck-loop detection (fingerprinting + 3x threshold)
- [x] Build agent environment hints (venv, git init, python3 -m pytest)
- [x] Reduced build agent limits (25 rounds, 600s timeout)
- [x] GitHub-ready clean repo (env vars, no hardcoded IPs)
