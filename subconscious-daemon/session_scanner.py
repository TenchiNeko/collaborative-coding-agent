"""
Session Scanner — Watches for completed orchestrator sessions.

Reads the session data the orchestrator produces:
- .agents/state.json (TaskState with goal, iterations, failures, DoD)
- .agents/traces/training_traces.jsonl OR failure_traces.jsonl
- Source files (*.py) in the working directory
- Test results from the build/test cycle
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionTrace:
    """Parsed data from a completed orchestrator session."""
    session_id: str
    session_dir: str
    goal: str
    iterations_used: int
    max_iterations: int = 3
    completed: bool = False
    success: bool = False  # True if DoD criteria all passed

    # DoD results
    dod_total: int = 0
    dod_passed: int = 0
    dod_criteria: List[Dict] = field(default_factory=list)

    # Failure history
    failure_history: List[Dict] = field(default_factory=list)

    # Trace data
    build_failures: List[Dict] = field(default_factory=list)
    test_failures: List[Dict] = field(default_factory=list)
    rca_failures: List[Dict] = field(default_factory=list)
    sampling_results: List[Dict] = field(default_factory=list)

    # Source files produced
    source_files: Dict[str, str] = field(default_factory=dict)  # filename → content
    test_files: Dict[str, str] = field(default_factory=dict)    # filename → content

    # Timing
    started_at: str = ""
    completed_at: str = ""

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            try:
                start = datetime.fromisoformat(self.started_at)
                end = datetime.fromisoformat(self.completed_at)
                return (end - start).total_seconds()
            except ValueError:
                pass
        return 0

    @property
    def test_pass_rate(self) -> float:
        if self.dod_total == 0:
            return 0.0
        return self.dod_passed / self.dod_total


class SessionScanner:
    """
    Scans the shared sessions directory for completed orchestrator sessions.
    Parses session data into SessionTrace objects for analysis.
    """

    def __init__(self, sessions_dir: str, state_dir: str):
        self.sessions_dir = Path(sessions_dir)
        self.state_dir = Path(state_dir)
        self.processed_file = Path(state_dir) / "processed_sessions.json"
        self._processed: set = set()
        self._load_processed()

    def _load_processed(self):
        """Load set of already-processed session IDs."""
        if self.processed_file.exists():
            try:
                data = json.loads(self.processed_file.read_text())
                self._processed = set(data.get("processed", []))
            except (json.JSONDecodeError, KeyError):
                self._processed = set()
        logger.debug(f"Loaded {len(self._processed)} processed session IDs")

    def _save_processed(self):
        """Save processed session IDs."""
        self.processed_file.parent.mkdir(parents=True, exist_ok=True)
        self.processed_file.write_text(json.dumps({
            "processed": list(self._processed),
            "last_updated": datetime.now().isoformat(),
        }))

    def mark_processed(self, session_id: str):
        """Mark a session as processed."""
        self._processed.add(session_id)
        self._save_processed()

    def find_new_sessions(self) -> List[Path]:
        """
        Find session directories that haven't been processed yet.
        A session is 'complete' if it has .agents/state.json with a completed_at field.
        """
        if not self.sessions_dir.exists():
            return []

        new_sessions = []
        for session_dir in sorted(self.sessions_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            session_id = session_dir.name
            if session_id in self._processed:
                continue

            # Check if session is complete
            state_file = session_dir / ".agents" / "state.json"
            if not state_file.exists():
                continue

            try:
                state = json.loads(state_file.read_text())
                if state.get("completed_at"):
                    new_sessions.append(session_dir)
            except (json.JSONDecodeError, KeyError):
                continue

        return new_sessions

    def find_all_sessions(self) -> List[Path]:
        """Find ALL session directories (for re-analysis)."""
        if not self.sessions_dir.exists():
            return []

        sessions = []
        for session_dir in sorted(self.sessions_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            state_file = session_dir / ".agents" / "state.json"
            if state_file.exists():
                sessions.append(session_dir)

        return sessions

    def _find_traces_file(self, session_dir: Path) -> Optional[Path]:
        """
        Find the traces file — handles both naming conventions:
        - training_traces.jsonl (orchestrator v0.9.x+)
        - failure_traces.jsonl (original subconscious expected name)
        """
        traces_dir = session_dir / ".agents" / "traces"
        if not traces_dir.exists():
            return None

        # Try both filenames
        for name in ["training_traces.jsonl", "failure_traces.jsonl"]:
            candidate = traces_dir / name
            if candidate.exists():
                return candidate

        return None

    def parse_session(self, session_dir: Path) -> Optional[SessionTrace]:
        """
        Parse a complete session directory into a SessionTrace.
        """
        state_file = session_dir / ".agents" / "state.json"
        if not state_file.exists():
            logger.warning(f"No state.json in {session_dir}")
            return None

        try:
            state = json.loads(state_file.read_text())
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid state.json in {session_dir}: {e}")
            return None

        session_id = session_dir.name

        # Parse DoD
        dod = state.get("dod", {})
        dod_criteria = dod.get("criteria", [])
        dod_passed = sum(1 for c in dod_criteria if c.get("passed", False))

        trace = SessionTrace(
            session_id=session_id,
            session_dir=str(session_dir),
            goal=state.get("goal", ""),
            iterations_used=state.get("iteration", 1),
            completed=bool(state.get("completed_at")),
            success=(dod_passed == len(dod_criteria) and len(dod_criteria) > 0),
            dod_total=len(dod_criteria),
            dod_passed=dod_passed,
            dod_criteria=dod_criteria,
            failure_history=state.get("failure_history", []),
            started_at=state.get("started_at", ""),
            completed_at=state.get("completed_at", ""),
        )

        # Parse failure traces (try both filenames)
        traces_file = self._find_traces_file(session_dir)
        if traces_file:
            try:
                for line in traces_file.read_text().strip().split("\n"):
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    trace_type = entry.get("type", "")
                    if trace_type == "build_failure":
                        trace.build_failures.append(entry)
                    elif trace_type == "test_failure":
                        trace.test_failures.append(entry)
                    elif trace_type == "rca_failure":
                        trace.rca_failures.append(entry)
                    elif trace_type == "sampling_result":
                        trace.sampling_results.append(entry)
            except Exception as e:
                logger.warning(f"Error parsing traces in {session_dir}: {e}")

        # Also try for_claude.md as supplementary trace data
        claude_traces = session_dir / ".agents" / "traces" / "for_claude.md"
        if claude_traces.exists() and not traces_file:
            # If we have no JSONL traces but do have the markdown summary,
            # extract what we can from it
            try:
                content = claude_traces.read_text()
                # Count failure mentions as a rough signal
                import_errors = content.lower().count("import_error")
                if import_errors > 0:
                    trace.test_failures.append({
                        "type": "test_failure",
                        "error_category": "import_error",
                        "error_output": f"Extracted from for_claude.md: {import_errors} import_error mentions",
                        "filename": "unknown",
                    })
            except Exception:
                pass

        # Collect source and test files
        for py_file in session_dir.glob("*.py"):
            name = py_file.name
            try:
                content = py_file.read_text()
                if name.startswith("test_"):
                    trace.test_files[name] = content
                else:
                    trace.source_files[name] = content
            except Exception:
                pass

        logger.debug(
            f"Parsed session {session_id}: "
            f"{'✅' if trace.success else '❌'} "
            f"DoD {trace.dod_passed}/{trace.dod_total}, "
            f"{len(trace.build_failures)} build failures, "
            f"{len(trace.test_failures)} test failures, "
            f"{len(trace.source_files)} source files"
        )

        return trace
