"""
Conversation Memory — Persistent context across iterations.

Stores a rolling summary of what happened in each iteration so agents
don't repeat the same mistakes. The build agent gets the last N iterations
of context injected into its prompt.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class IterationRecord:
    """Record of what happened in a single iteration."""
    iteration: int
    phase_reached: str  # explore, plan, build, test, complete
    success: bool
    actions_taken: List[str] = field(default_factory=list)  # key things the build agent did
    files_modified: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dod_results: dict = field(default_factory=dict)  # {"criterion-0": {"passed": True, ...}}
    rca: str = ""
    plan_summary: str = ""


class ConversationMemory:
    """
    Rolling memory of iteration outcomes.

    Stores what happened in each iteration and provides formatted context
    for agent prompts. Persists to disk so it survives restarts.
    """

    def __init__(self, memory_file: Optional[Path] = None):
        self.records: List[IterationRecord] = []
        self.memory_file = memory_file

        if memory_file and memory_file.exists():
            self._load()

    def add_iteration(
        self,
        iteration: int,
        phase_reached: str,
        success: bool,
        actions_taken: Optional[List[str]] = None,
        files_modified: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
        dod_results: Optional[dict] = None,
        rca: str = "",
        plan_summary: str = "",
    ):
        """Record the outcome of an iteration."""
        record = IterationRecord(
            iteration=iteration,
            phase_reached=phase_reached,
            success=success,
            actions_taken=actions_taken or [],
            files_modified=files_modified or [],
            errors=errors or [],
            dod_results=dod_results or {},
            rca=rca,
            plan_summary=plan_summary,
        )
        self.records.append(record)
        logger.debug(f"Memory: recorded iteration {iteration} (success={success})")

        if self.memory_file:
            self._save()

    def get_context(self, last_n: int = 3, total_budget: int = 6000) -> str:
        """
        Get formatted context string for injection into agent prompts.

        Returns the last N iterations as a human-readable summary
        that helps the agent understand what already happened.

        v0.5.1: Budget-aware. Each iteration gets an equal share of the total
        budget. If an iteration's content exceeds its share, it's truncated
        with head+tail preservation (errors are usually at the end).

        Args:
            last_n: Number of recent iterations to include
            total_budget: Maximum total characters for the context string
        """
        if not self.records:
            return ""

        recent = self.records[-last_n:]
        per_iteration_budget = total_budget // max(len(recent), 1)

        lines = ["## Previous Iteration History", ""]

        for rec in recent:
            iter_lines = []
            status = "✅ PASSED" if rec.success else "❌ FAILED"
            iter_lines.append(f"### Iteration {rec.iteration} — {status} (reached: {rec.phase_reached})")

            if rec.plan_summary:
                iter_lines.append(f"Plan: {rec.plan_summary[:200]}")

            if rec.actions_taken:
                iter_lines.append("Actions taken:")
                for action in rec.actions_taken[:5]:
                    iter_lines.append(f"  - {action}")

            if rec.files_modified:
                iter_lines.append(f"Files modified: {', '.join(rec.files_modified[:10])}")

            if rec.errors:
                iter_lines.append("Errors encountered:")
                for err in rec.errors[:3]:
                    iter_lines.append(f"  - {err[:200]}")

            if rec.dod_results:
                # Handle both structured and legacy formats
                if isinstance(rec.dod_results, dict):
                    if "criteria_results" in rec.dod_results:
                        # New structured format — summarize, don't dump everything
                        results = rec.dod_results["criteria_results"]
                        passed = sum(1 for r in results if r.get("passed"))
                        total = len(results)
                        iter_lines.append(f"DoD: {passed}/{total} criteria passed")
                        # Only show failed criteria (passed ones aren't useful for fix context)
                        for r in results:
                            if not r.get("passed"):
                                reason = r.get("failure_reason", "unknown")
                                desc = r.get("description", r.get("criterion_id", "?"))
                                # Cap description to avoid verbose criteria eating budget
                                iter_lines.append(f"  FAILED {r['criterion_id']}: {desc[:80]} — {reason[:80]}")
                    else:
                        # Legacy format
                        passed = sum(1 for v in rec.dod_results.values() if isinstance(v, dict) and v.get("passed"))
                        total = len(rec.dod_results)
                        iter_lines.append(f"DoD: {passed}/{total} criteria passed")
                        for cid, result in rec.dod_results.items():
                            if isinstance(result, dict) and not result.get("passed"):
                                evidence = result.get("evidence", "no details")[:100]
                                iter_lines.append(f"  FAILED {cid}: {evidence}")

            if rec.rca:
                iter_lines.append(f"RCA: {rec.rca[:300]}")

            iter_lines.append("")

            # Join this iteration and check budget
            iter_text = "\n".join(iter_lines)
            if len(iter_text) > per_iteration_budget:
                # Truncate but keep header + tail (RCA is usually at the end)
                header = iter_lines[0] + "\n"
                remaining = per_iteration_budget - len(header) - 60
                body = "\n".join(iter_lines[1:])
                head_size = int(remaining * 0.5)
                tail_size = remaining - head_size
                iter_text = (
                    header
                    + body[:head_size]
                    + "\n  ... (iteration details truncated) ...\n"
                    + body[-tail_size:]
                )

            lines.append(iter_text)

        lines.append("## IMPORTANT: Do NOT repeat previous mistakes.")
        lines.append("Review the failures above and take a different approach.")
        lines.append("")

        return "\n".join(lines)

    def get_last_iteration(self) -> Optional[IterationRecord]:
        """Get the most recent iteration record."""
        return self.records[-1] if self.records else None

    def _save(self):
        """Persist memory to disk."""
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            data = [asdict(r) for r in self.records]
            self.memory_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save memory: {e}")

    def _load(self):
        """Load memory from disk."""
        try:
            data = json.loads(self.memory_file.read_text())
            self.records = [IterationRecord(**r) for r in data]
            logger.debug(f"Memory: loaded {len(self.records)} iteration records")
        except Exception as e:
            logger.warning(f"Failed to load memory: {e}")
            self.records = []
