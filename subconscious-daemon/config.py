"""
Subconscious Daemon Configuration.

Connects to the 9B model on PVE node for analysis,
watches shared session storage, maintains playbook.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DaemonConfig:
    """Configuration for the subconscious daemon."""

    # --- Ollama connection (9B on PVE node) ---
    ollama_url: str = "http://localhost:11434"
    model_id: str = "qwen2.5-coder:7b"
    temperature: float = 0.1
    max_tokens: int = 4096
    request_timeout: int = 120  # seconds

    # --- Shared storage paths ---
    # Sessions dir: orchestrator writes completed session data here
    sessions_dir: str = "/shared/sessions"
    # Playbook: the evolving context document
    playbook_path: str = "/shared/playbook.json"
    # Training pairs output
    training_dir: str = "/shared/training"
    # Benchmark suite
    benchmarks_dir: str = "/shared/benchmarks"
    # Model archive
    models_dir: str = "/shared/models"
    # Daemon state (processed sessions, queue state)
    state_dir: str = "/shared/daemon"

    # --- Timing ---
    scan_interval: int = 30        # seconds between queue checks
    playbook_sync_interval: int = 300  # seconds between playbook syncs to main node
    min_lora_interval: int = 172800    # 48 hours between LoRA training runs
    nightly_eval_hour: int = 3         # 3 AM for nightly self-evaluation

    # --- Playbook settings (ACE-style) ---
    playbook_token_budget: int = 8000  # max tokens for playbook content
    dedup_similarity_threshold: float = 0.85  # cosine sim threshold for dedup
    min_helpful_ratio: float = 0.3  # bullets below this ratio get pruned
    max_bullets_per_section: int = 50
    stale_days: int = 14  # bullets not referenced in N days = stale

    # --- Training pair settings ---
    min_pairs_for_lora: int = 50
    quality_threshold: int = 3  # LLM-as-judge minimum score (1-5)

    # --- Safety ---
    kill_switch_path: str = "/shared/STOP_SUBCONSCIOUS"
    lora_improvement_threshold: float = 0.02  # 2% minimum to deploy

    @classmethod
    def from_env(cls) -> "DaemonConfig":
        """Load config with environment variable overrides."""
        config = cls()
        config.ollama_url = os.environ.get("SUBCONSCIOUS_OLLAMA_URL", config.ollama_url)
        config.model_id = os.environ.get("SUBCONSCIOUS_MODEL", config.model_id)
        config.sessions_dir = os.environ.get("SUBCONSCIOUS_SESSIONS_DIR", config.sessions_dir)
        config.playbook_path = os.environ.get("SUBCONSCIOUS_PLAYBOOK", config.playbook_path)
        config.state_dir = os.environ.get("SUBCONSCIOUS_STATE_DIR", config.state_dir)
        return config

    def ensure_dirs(self):
        """Create all required directories."""
        for d in [self.sessions_dir, self.training_dir, self.benchmarks_dir,
                  self.models_dir, self.state_dir,
                  os.path.join(self.training_dir, "queue"),
                  os.path.join(self.training_dir, "ready"),
                  os.path.join(self.training_dir, "used"),
                  os.path.join(self.models_dir, "archive"),
                  os.path.join(self.models_dir, "active"),
                  os.path.join(self.models_dir, "baseline")]:
            Path(d).mkdir(parents=True, exist_ok=True)
