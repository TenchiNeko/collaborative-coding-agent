"""
Subconscious Daemon — Autonomous self-improving background agent.

Runs 24/7 on the PVE node with a 9B model, continuously:
1. Analyzing completed orchestrator sessions
2. Evolving the playbook (ACE-style delta updates)
3. Extracting training pairs for LoRA fine-tuning
4. Re-analyzing old sessions with updated knowledge
5. Self-evaluating playbook quality

Priority queue ensures most valuable work always happens first.
The daemon NEVER idles — there's always something to learn from.
"""

import asyncio
import json
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict

from config import DaemonConfig
from playbook import Playbook
from session_scanner import SessionScanner, SessionTrace
from ollama_client import OllamaClient

logger = logging.getLogger(__name__)


# ── Failure taxonomy ──────────────────────────────────────────────

FAILURE_CATEGORIES = [
    "IMPORT_ERROR",     # Wrong import paths, missing modules
    "TEST_STALE",       # Tests don't match source signatures
    "SYNTAX_ERROR",     # Model generated invalid Python
    "LOGIC_ERROR",      # Code runs but produces wrong output
    "TIMEOUT",          # Model stuck in loop or excessive iterations
    "STDLIB_MISS",      # Used external package when stdlib works
    "BUILD_ORDER",      # Dependency built before its prerequisite
    "JSON_ESCAPE",      # Model produced broken JSON/tool calls
    "TYPE_ERROR",       # Wrong types, missing args, bad signatures
    "OTHER",            # Uncategorized
]

# Section mapping: failure category → playbook section
CATEGORY_TO_SECTION = {
    "IMPORT_ERROR": "import_resolution",
    "TEST_STALE": "test_generation",
    "SYNTAX_ERROR": "error_recovery",
    "LOGIC_ERROR": "general",
    "TIMEOUT": "error_recovery",
    "STDLIB_MISS": "stdlib_usage",
    "BUILD_ORDER": "build_ordering",
    "JSON_ESCAPE": "error_recovery",
    "TYPE_ERROR": "general",
    "OTHER": "general",
}


# ── Priority queue task types ─────────────────────────────────────

class TaskPriority(Enum):
    """Priority levels — lower number = higher priority."""
    P0_REFLECT = 0       # Analyze new completed session
    P1_CURATE = 1        # Apply delta updates to playbook
    P2_EXTRACT = 2       # Extract training pairs from successes
    P3_REANALYZE = 3     # Re-analyze old sessions
    P4_BENCHMARK = 4     # Generate benchmark tasks
    P5_PROMPT_EVOLVE = 5 # Test prompt variations
    P6_TRAIN = 6         # LoRA training
    P7_SELF_EVAL = 7     # Nightly playbook self-evaluation


class DaemonState(Enum):
    STARTING = "starting"
    RUNNING = "running"
    REFLECTING = "reflecting"     # P0
    CURATING = "curating"         # P1
    EXTRACTING = "extracting"     # P2
    REANALYZING = "reanalyzing"   # P3
    BENCHMARKING = "benchmarking" # P4
    EVOLVING = "evolving"         # P5
    TRAINING = "training"         # P6
    EVALUATING = "evaluating"     # P7
    SLEEPING = "sleeping"         # Brief pause between queue checks
    STOPPED = "stopped"


# ── Main Daemon ───────────────────────────────────────────────────

class SubconsciousDaemon:
    """
    The subconscious — always running, always learning.

    Implements the ACE (Agentic Context Engineering) loop:
    Generator → Reflector → Curator with delta playbook updates.
    """

    def __init__(self, config: Optional[DaemonConfig] = None):
        self.config = config or DaemonConfig.from_env()
        self.config.ensure_dirs()

        self.state = DaemonState.STARTING
        self.ollama = OllamaClient(
            base_url=self.config.ollama_url,
            model=self.config.model_id,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.request_timeout,
        )
        self.playbook = Playbook(
            path=self.config.playbook_path,
            token_budget=self.config.playbook_token_budget,
        )
        self.scanner = SessionScanner(
            sessions_dir=self.config.sessions_dir,
            state_dir=self.config.state_dir,
        )

        # Daemon stats
        self.stats = {
            "started_at": datetime.now().isoformat(),
            "sessions_analyzed": 0,
            "deltas_applied": 0,
            "training_pairs_extracted": 0,
            "cycles_completed": 0,
            "errors": 0,
        }
        self._stats_file = Path(self.config.state_dir) / "daemon_stats.json"
        self._running = True

    # ── Main Loop ─────────────────────────────────────────────────

    async def run(self):
        """Main event loop — runs forever, priority queue drives work."""
        logger.info("🧠 Subconscious daemon starting...")

        # Check Ollama connectivity
        if not await self.ollama.is_available():
            logger.error(f"❌ Cannot reach Ollama at {self.config.ollama_url}")
            logger.error("   Make sure Ollama is running with the model loaded.")
            return

        logger.info(f"✅ Connected to {self.config.model_id} at {self.config.ollama_url}")
        logger.info(f"📖 Playbook: {self.playbook.total_bullets} bullets")
        logger.info(f"📂 Watching: {self.config.sessions_dir}")

        self.state = DaemonState.RUNNING

        while self._running:
            try:
                # Check kill switch
                if Path(self.config.kill_switch_path).exists():
                    logger.info("🛑 Kill switch detected. Shutting down.")
                    break

                # Execute highest priority available task
                executed = await self._execute_next_task()

                if not executed:
                    # Nothing to do — brief pause then check again
                    self.state = DaemonState.SLEEPING
                    await asyncio.sleep(self.config.scan_interval)

                self.stats["cycles_completed"] += 1
                self._save_stats()

            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
                self.stats["errors"] += 1
                await asyncio.sleep(60)  # Back off on error

        self.state = DaemonState.STOPPED
        logger.info("🧠 Subconscious daemon stopped.")

    async def _execute_next_task(self) -> bool:
        """
        Check priority queue and execute the highest-priority available task.
        Returns True if a task was executed, False if nothing to do.
        """
        # P0: New sessions to analyze?
        new_sessions = self.scanner.find_new_sessions()
        if new_sessions:
            session_dir = new_sessions[0]  # Take the oldest unprocessed
            self.state = DaemonState.REFLECTING
            logger.info(f"\n{'='*60}")
            logger.info(f"P0: REFLECT on session {session_dir.name}")
            logger.info(f"{'='*60}")
            await self._reflect_on_session(session_dir)
            return True

        # P1: Pending delta updates? (driven by P0 output)
        # P1 is integrated into P0 — curate happens immediately after reflect

        # P2: Extract training pairs from successful sessions
        # (Only if we haven't extracted from all sessions yet)
        if await self._has_unextracted_sessions():
            self.state = DaemonState.EXTRACTING
            logger.info(f"\nP2: EXTRACT training pairs")
            await self._extract_training_pairs()
            return True

        # P3: Re-analyze old sessions with updated playbook
        if await self._has_sessions_to_reanalyze():
            self.state = DaemonState.REANALYZING
            logger.info(f"\nP3: RE-ANALYZE old sessions")
            await self._reanalyze_sessions()
            return True

        # P7: Nightly self-evaluation (if it's time)
        if self._is_eval_time():
            self.state = DaemonState.EVALUATING
            logger.info(f"\nP7: SELF-EVALUATE playbook")
            await self._self_evaluate_playbook()
            return True

        return False

    # ── P0: REFLECT — Analyze new session ─────────────────────────

    async def _reflect_on_session(self, session_dir: Path):
        """
        ACE Generator + Reflector + Curator loop for a single session.
        """
        session = self.scanner.parse_session(session_dir)
        if not session:
            self.scanner.mark_processed(session_dir.name)
            return

        logger.info(f"  Goal: {session.goal[:100]}")
        logger.info(f"  Result: {'✅ SUCCESS' if session.success else '❌ FAILED'}")
        logger.info(f"  DoD: {session.dod_passed}/{session.dod_total}")
        logger.info(f"  Iterations: {session.iterations_used}")
        logger.info(f"  Build failures: {len(session.build_failures)}")
        logger.info(f"  Test failures: {len(session.test_failures)}")

        # ── GENERATOR: Produce analysis of what happened ──
        analysis = await self._generate_analysis(session)
        if not analysis:
            logger.warning("  Generator produced no analysis, skipping.")
            self.scanner.mark_processed(session_dir.name)
            return

        # ── REFLECTOR: Extract lessons and proposed bullets ──
        proposed_bullets = await self._reflect_on_analysis(session, analysis)

        # ── CURATOR: Apply delta updates to playbook ──
        self.state = DaemonState.CURATING
        bullets_added = 0
        for proposed in proposed_bullets:
            section = proposed.get("section", "general")
            content = proposed.get("content", "").strip()
            if not content:
                continue

            # Check for duplicates before adding
            is_dupe = False
            for existing in self.playbook.sections.get(section, []):
                if self.playbook._text_similarity(content, existing.content) > self.config.dedup_similarity_threshold:
                    # Not a new bullet — but maybe bump the helpful count
                    if session.success:
                        existing.helpful_count += 1
                    existing.last_referenced = datetime.now().isoformat()
                    is_dupe = True
                    logger.debug(f"  Dedup: '{content[:50]}' matches {existing.id}")
                    break

            if not is_dupe:
                bullet = self.playbook.add_bullet(
                    section=section,
                    content=content,
                    source_session=session.session_id,
                )
                if session.success:
                    bullet.helpful_count = 1
                bullets_added += 1

        self.playbook.save()
        self.scanner.mark_processed(session_dir.name)
        self.stats["sessions_analyzed"] += 1
        self.stats["deltas_applied"] += bullets_added

        logger.info(f"  📝 Added {bullets_added} new bullets to playbook")
        logger.info(f"  📖 Playbook now has {self.playbook.total_bullets} bullets")

    async def _generate_analysis(self, session: SessionTrace) -> Optional[dict]:
        """
        GENERATOR phase: Use 9B to analyze the session.
        Returns structured analysis dict.
        """
        # Build context from session data
        failures_text = ""
        for bf in session.build_failures[:5]:
            failures_text += (
                f"\n--- Build Failure: {bf.get('filename', '?')} ---\n"
                f"Category: {bf.get('error_category', '?')}\n"
                f"Error: {bf.get('error_output', '?')[:300]}\n"
                f"Code excerpt: {bf.get('generated_code', '?')[:300]}\n"
            )
        for tf in session.test_failures[:5]:
            failures_text += (
                f"\n--- Test Failure: {tf.get('test_file', '?')} ---\n"
                f"Error: {tf.get('error_output', '?')[:300]}\n"
                f"Failures: {tf.get('failure_count', '?')}/{tf.get('total_tests', '?')}\n"
            )

        dod_text = ""
        for c in session.dod_criteria:
            status = "✅" if c.get("passed") else "❌"
            dod_text += f"  {status} {c.get('description', '?')}\n"

        prompt = f"""Analyze this coding session and identify patterns.

TASK: {session.goal}
RESULT: {"SUCCESS - all tests pass" if session.success else "FAILED"}
ITERATIONS USED: {session.iterations_used}
DoD CRITERIA:
{dod_text}

FAILURES ENCOUNTERED:
{failures_text if failures_text else "None (clean run)"}

SOURCE FILES: {', '.join(session.source_files.keys())}
TEST FILES: {', '.join(session.test_files.keys())}

Analyze this session. For each observation, classify it as one of:
{', '.join(FAILURE_CATEGORIES)}

Respond as JSON with this structure:
{{
  "overall_assessment": "one sentence summary",
  "observations": [
    {{
      "category": "IMPORT_ERROR",
      "pattern": "specific reusable pattern description",
      "recommendation": "what should be done differently next time",
      "confidence": 0.8
    }}
  ]
}}"""

        system = (
            "You are a code failure analyst. You review session traces from an autonomous "
            "coding agent and extract reusable patterns. Be specific and actionable. "
            "Focus on patterns that would help prevent the same failure in future sessions. "
            "Respond ONLY with valid JSON."
        )

        return await self.ollama.generate_json(prompt, system=system)

    async def _reflect_on_analysis(self, session: SessionTrace,
                                   analysis: dict) -> List[dict]:
        """
        REFLECTOR phase: Convert analysis observations into proposed playbook bullets.
        """
        observations = analysis.get("observations", [])
        if not observations:
            logger.debug("  No observations from generator.")
            return []

        # Get current playbook state for the reflector to compare against
        current_bullets_text = ""
        for section_name, bullets in self.playbook.sections.items():
            if bullets:
                current_bullets_text += f"\n[{section_name}]\n"
                for b in bullets[:10]:  # Top 10 per section
                    current_bullets_text += f"  - [{b.id}] {b.content}\n"

        prompt = f"""You are reviewing analysis of a coding session to create playbook entries.

CURRENT PLAYBOOK (existing knowledge):
{current_bullets_text if current_bullets_text else "(empty — no existing bullets)"}

NEW OBSERVATIONS from session:
{json.dumps(observations, indent=2)}

SESSION WAS: {"SUCCESSFUL" if session.success else "FAILED"}

For each observation, determine:
1. Is this genuinely NEW knowledge not already in the playbook?
2. What SPECIFIC, ACTIONABLE bullet should be added?
3. Which section does it belong to?

Section options: {', '.join(self.playbook.sections.keys())}

Respond as JSON:
{{
  "proposed_bullets": [
    {{
      "section": "import_resolution",
      "content": "When building Flask apps, always import Flask before defining routes. The import order matters for circular dependency resolution.",
      "is_new": true,
      "reasoning": "This pattern appeared in the failure but isn't covered by existing bullets"
    }}
  ]
}}

IMPORTANT:
- Only propose bullets that are genuinely NEW (not duplicates of existing ones)
- Each bullet should be a single, specific, actionable instruction
- Write from the perspective of advising a coding agent
- Be concrete, not vague (bad: "handle imports carefully", good: "use absolute imports with the exact filename stem as module name")"""

        system = (
            "You are a knowledge curator for an AI coding agent. "
            "Your job is to identify NEW, ACTIONABLE knowledge from session analysis "
            "that should be added to the agent's playbook. Be highly selective — "
            "only propose bullets that capture genuinely useful, specific patterns. "
            "Respond ONLY with valid JSON."
        )

        result = await self.ollama.generate_json(prompt, system=system)
        if not result:
            return []

        proposed = result.get("proposed_bullets", [])
        # Filter to only new ones
        return [p for p in proposed if p.get("is_new", True)]

    # ── P2: EXTRACT training pairs ────────────────────────────────

    async def _has_unextracted_sessions(self) -> bool:
        """Check if there are successful sessions we haven't extracted pairs from."""
        extracted_file = Path(self.config.state_dir) / "extracted_sessions.json"
        extracted = set()
        if extracted_file.exists():
            try:
                extracted = set(json.loads(extracted_file.read_text()).get("extracted", []))
            except (json.JSONDecodeError, KeyError):
                pass

        for session_dir in self.scanner.find_all_sessions():
            if session_dir.name not in extracted:
                session = self.scanner.parse_session(session_dir)
                if session and session.success:
                    return True
        return False

    async def _extract_training_pairs(self):
        """Extract (instruction, response) pairs from successful sessions."""
        extracted_file = Path(self.config.state_dir) / "extracted_sessions.json"
        extracted = set()
        if extracted_file.exists():
            try:
                extracted = set(json.loads(extracted_file.read_text()).get("extracted", []))
            except (json.JSONDecodeError, KeyError):
                pass

        pairs_added = 0
        for session_dir in self.scanner.find_all_sessions():
            if session_dir.name in extracted:
                continue

            session = self.scanner.parse_session(session_dir)
            if not session or not session.success:
                extracted.add(session_dir.name)
                continue

            # Extract positive pairs from source files
            for filename, content in session.source_files.items():
                if len(content.strip().split("\n")) < 10:
                    continue  # Skip trivial files

                pair = {
                    "instruction": f"Build the file '{filename}' for: {session.goal}",
                    "response": content,
                    "source_session": session.session_id,
                    "type": "positive",
                    "timestamp": datetime.now().isoformat(),
                }

                # Write to queue
                queue_dir = Path(self.config.training_dir) / "queue"
                queue_file = queue_dir / f"pairs_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
                with open(queue_file, "a") as f:
                    f.write(json.dumps(pair) + "\n")
                pairs_added += 1

            extracted.add(session_dir.name)

        # Save extracted state
        extracted_file.write_text(json.dumps({
            "extracted": list(extracted),
            "last_updated": datetime.now().isoformat(),
        }))
        self.stats["training_pairs_extracted"] += pairs_added
        logger.info(f"  📦 Extracted {pairs_added} training pairs")

    # ── P3: RE-ANALYZE old sessions ───────────────────────────────

    async def _has_sessions_to_reanalyze(self) -> bool:
        """Check if there are old sessions worth re-analyzing."""
        reanalysis_file = Path(self.config.state_dir) / "reanalysis_state.json"
        if not reanalysis_file.exists():
            all_sessions = self.scanner.find_all_sessions()
            return len(all_sessions) > 0

        try:
            data = json.loads(reanalysis_file.read_text())
            last_epoch = data.get("epoch", 0)
            # Re-analyze every 24 hours (multi-epoch adaptation)
            last_run = data.get("last_run", "")
            if last_run:
                lr = datetime.fromisoformat(last_run)
                if datetime.now() - lr < timedelta(hours=24):
                    return False
            return True
        except (json.JSONDecodeError, ValueError):
            return True

    async def _reanalyze_sessions(self):
        """
        Re-analyze old sessions with the updated playbook.
        ACE's 'multi-epoch adaptation' — same data, stronger context each pass.
        """
        reanalysis_file = Path(self.config.state_dir) / "reanalysis_state.json"
        epoch = 0
        if reanalysis_file.exists():
            try:
                epoch = json.loads(reanalysis_file.read_text()).get("epoch", 0)
            except (json.JSONDecodeError, KeyError):
                pass

        epoch += 1
        logger.info(f"  Re-analysis epoch {epoch}")

        sessions = self.scanner.find_all_sessions()
        for session_dir in sessions[:5]:  # Process max 5 per cycle
            session = self.scanner.parse_session(session_dir)
            if not session:
                continue

            # Only re-analyze failed sessions (successes already captured)
            if session.success:
                continue

            analysis = await self._generate_analysis(session)
            if analysis:
                proposed = await self._reflect_on_analysis(session, analysis)
                for p in proposed:
                    section = p.get("section", "general")
                    content = p.get("content", "").strip()
                    if content:
                        # Check dedup
                        is_dupe = False
                        for existing in self.playbook.sections.get(section, []):
                            if self.playbook._text_similarity(content, existing.content) > self.config.dedup_similarity_threshold:
                                is_dupe = True
                                break
                        if not is_dupe:
                            self.playbook.add_bullet(section, content, session.session_id)

        self.playbook.save()

        # Save reanalysis state
        reanalysis_file.write_text(json.dumps({
            "epoch": epoch,
            "last_run": datetime.now().isoformat(),
            "sessions_reviewed": len(sessions),
        }))
        logger.info(f"  Epoch {epoch} complete. Playbook: {self.playbook.total_bullets} bullets")

    # ── P7: SELF-EVALUATE playbook ────────────────────────────────

    def _is_eval_time(self) -> bool:
        """Check if it's time for nightly self-evaluation."""
        eval_file = Path(self.config.state_dir) / "last_eval.json"
        if not eval_file.exists():
            return True
        try:
            data = json.loads(eval_file.read_text())
            last = datetime.fromisoformat(data["last_eval"])
            return datetime.now() - last > timedelta(hours=23)
        except (json.JSONDecodeError, KeyError, ValueError):
            return True

    async def _self_evaluate_playbook(self):
        """
        Nightly self-evaluation: prune stale/harmful bullets, deduplicate.
        """
        logger.info("  Running nightly evaluation...")

        # Prune harmful and stale
        pruned = self.playbook.prune_stale(
            stale_days=self.config.stale_days,
            min_quality=self.config.min_helpful_ratio,
        )

        # Deduplicate
        deduped = self.playbook.deduplicate(self.config.dedup_similarity_threshold)

        # Log stats
        stats = self.playbook.stats()
        logger.info(f"  Pruned: {pruned}, Deduped: {deduped}")
        logger.info(f"  Total bullets: {stats['total_bullets']}")
        logger.info(f"  Avg quality: {stats['avg_quality']:.2f}")

        # Save eval timestamp
        eval_file = Path(self.config.state_dir) / "last_eval.json"
        eval_file.write_text(json.dumps({
            "last_eval": datetime.now().isoformat(),
            "pruned": pruned,
            "deduped": deduped,
            "total_bullets": stats["total_bullets"],
        }))

    # ── Utilities ─────────────────────────────────────────────────

    def _save_stats(self):
        """Persist daemon stats."""
        try:
            self._stats_file.write_text(json.dumps(self.stats, indent=2))
        except Exception:
            pass

    def handle_shutdown(self, signum, frame):
        """Graceful shutdown handler."""
        logger.info(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self._running = False


# ── Entry point ───────────────────────────────────────────────────

def main():
    """Start the subconscious daemon."""
    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("/shared/daemon/subconscious.log"),
        ]
    )

    config = DaemonConfig.from_env()
    daemon = SubconsciousDaemon(config)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, daemon.handle_shutdown)
    signal.signal(signal.SIGINT, daemon.handle_shutdown)

    # Run the event loop
    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
