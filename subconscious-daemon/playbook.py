"""
Playbook Manager — ACE-style evolving context for the orchestrator.

Based on the ACE (Agentic Context Engineering) framework (Stanford/SambaNova, Oct 2025).
Maintains a living playbook of structured bullet-point heuristics that get injected
into orchestrator agent prompts to improve coding performance.

Key principles:
- Delta updates only (never rewrite the whole playbook)
- Each bullet has helpful/harmful counters tracked by real test outcomes
- Deduplication by content similarity
- Periodic pruning of stale or consistently harmful bullets
"""

import json
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ── Bullet (single knowledge unit) ───────────────────────────────────

@dataclass
class Bullet:
    """A single knowledge bullet in the playbook."""
    id: str                           # e.g. "IR-001" (section prefix + number)
    content: str                      # The actual heuristic/strategy/pattern
    section: str                      # Category: import_resolution, test_generation, etc.
    helpful_count: int = 0            # Times this bullet was in context during success
    harmful_count: int = 0            # Times this bullet was in context during failure
    source_session: str = ""          # Session ID where this was discovered
    added: str = ""                   # ISO timestamp when added
    last_referenced: str = ""         # ISO timestamp when last used in a session
    last_validated: str = ""          # ISO timestamp when last confirmed still useful

    @property
    def quality_ratio(self) -> float:
        """Helpful / (helpful + harmful). Higher = better."""
        total = self.helpful_count + self.harmful_count
        if total == 0:
            return 0.5  # Neutral for new bullets
        return self.helpful_count / total

    @property
    def total_references(self) -> int:
        return self.helpful_count + self.harmful_count

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Bullet":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Playbook (collection of bullets) ─────────────────────────────────

# Default sections — can be extended dynamically
DEFAULT_SECTIONS = [
    "import_resolution",
    "test_generation",
    "build_ordering",
    "flask_patterns",
    "dataclass_patterns",
    "sqlite_patterns",
    "error_recovery",
    "stdlib_usage",
    "architecture",
    "general",
]


class Playbook:
    """
    ACE-style evolving playbook.

    Maintains structured bullets organized by section, with delta updates,
    deduplication, and pruning. Serializes to/from JSON.
    """

    def __init__(self, path: str, token_budget: int = 8000):
        self.path = Path(path)
        self.token_budget = token_budget
        self.version = "0.1.0"
        self.sections: Dict[str, List[Bullet]] = {}
        self._next_ids: Dict[str, int] = {}  # Track next ID per section
        self.last_updated = ""
        self.metadata = {
            "total_sessions_analyzed": 0,
            "total_deltas_applied": 0,
            "total_bullets_pruned": 0,
        }

        # Load existing or initialize
        if self.path.exists():
            self.load()
        else:
            self._init_empty()

    def _init_empty(self):
        """Initialize empty playbook with default sections."""
        for section in DEFAULT_SECTIONS:
            self.sections[section] = []
            self._next_ids[section] = 1
        self.last_updated = datetime.now().isoformat()
        self.save()
        logger.info(f"✨ Initialized empty playbook at {self.path}")

    # ── Persistence ───────────────────────────────────────────────

    def save(self):
        """Save playbook to JSON."""
        self.last_updated = datetime.now().isoformat()
        data = {
            "version": self.version,
            "last_updated": self.last_updated,
            "token_budget": self.token_budget,
            "metadata": self.metadata,
            "next_ids": self._next_ids,
            "sections": {
                name: [b.to_dict() for b in bullets]
                for name, bullets in self.sections.items()
            }
        }
        # Atomic write (write to temp, then rename)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.rename(self.path)
        logger.debug(f"💾 Playbook saved: {self.total_bullets} bullets across {len(self.sections)} sections")

    def load(self):
        """Load playbook from JSON."""
        try:
            data = json.loads(self.path.read_text())
            self.version = data.get("version", "0.1.0")
            self.last_updated = data.get("last_updated", "")
            self.token_budget = data.get("token_budget", self.token_budget)
            self.metadata = data.get("metadata", self.metadata)
            self._next_ids = data.get("next_ids", {})
            self.sections = {}
            for name, bullets_data in data.get("sections", {}).items():
                self.sections[name] = [Bullet.from_dict(b) for b in bullets_data]
                if name not in self._next_ids:
                    # Reconstruct next_id from existing bullets
                    existing = [int(b.id.split("-")[1]) for b in self.sections[name] if "-" in b.id]
                    self._next_ids[name] = (max(existing) + 1) if existing else 1
            logger.info(f"📖 Loaded playbook: {self.total_bullets} bullets, last updated {self.last_updated}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load playbook: {e}. Initializing empty.")
            self._init_empty()

    # ── Properties ────────────────────────────────────────────────

    @property
    def total_bullets(self) -> int:
        return sum(len(b) for b in self.sections.values())

    # ── Delta Updates (ACE core) ──────────────────────────────────

    def add_bullet(self, section: str, content: str, source_session: str = "") -> Bullet:
        """
        Add a new bullet to the playbook (delta append).
        Returns the created bullet.
        """
        if section not in self.sections:
            self.sections[section] = []
            self._next_ids[section] = 1

        # Generate section-prefixed ID
        prefix = self._section_prefix(section)
        bullet_id = f"{prefix}-{self._next_ids[section]:03d}"
        self._next_ids[section] += 1

        bullet = Bullet(
            id=bullet_id,
            content=content.strip(),
            section=section,
            source_session=source_session,
            added=datetime.now().isoformat(),
            last_referenced=datetime.now().isoformat(),
        )

        self.sections[section].append(bullet)
        self.metadata["total_deltas_applied"] += 1
        self.save()

        logger.info(f"  ➕ Added bullet {bullet_id}: {content[:80]}...")
        return bullet

    def update_counts(self, bullet_id: str, helpful: bool):
        """
        Increment helpful or harmful counter for a bullet.
        Called after a session where this bullet was in context.
        """
        bullet = self.get_bullet(bullet_id)
        if bullet:
            if helpful:
                bullet.helpful_count += 1
            else:
                bullet.harmful_count += 1
            bullet.last_referenced = datetime.now().isoformat()

    def update_content(self, bullet_id: str, new_content: str):
        """Update a bullet's content in-place (ACE delta edit)."""
        bullet = self.get_bullet(bullet_id)
        if bullet:
            old = bullet.content[:60]
            bullet.content = new_content.strip()
            bullet.last_validated = datetime.now().isoformat()
            logger.info(f"  ✏️  Updated {bullet_id}: '{old}...' → '{new_content[:60]}...'")

    def remove_bullet(self, bullet_id: str):
        """Remove a bullet (pruning)."""
        for section_name, bullets in self.sections.items():
            for i, b in enumerate(bullets):
                if b.id == bullet_id:
                    bullets.pop(i)
                    self.metadata["total_bullets_pruned"] += 1
                    logger.info(f"  🗑️  Pruned bullet {bullet_id}")
                    return True
        return False

    def get_bullet(self, bullet_id: str) -> Optional[Bullet]:
        """Find a bullet by ID."""
        for bullets in self.sections.values():
            for b in bullets:
                if b.id == bullet_id:
                    return b
        return None

    # ── Query / Export ────────────────────────────────────────────

    def get_top_bullets(self, n: int = 30, section_filter: Optional[str] = None) -> List[Bullet]:
        """
        Get the top N bullets by quality ratio, optionally filtered by section.
        Used by the orchestrator to inject into agent prompts.
        """
        candidates = []
        for section_name, bullets in self.sections.items():
            if section_filter and section_name != section_filter:
                continue
            candidates.extend(bullets)

        # Score: quality_ratio * log(1 + total_references) — rewards both quality AND usage
        import math
        scored = [
            (b.quality_ratio * math.log1p(b.total_references + 1), b)
            for b in candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        return [b for _, b in scored[:n]]

    def export_for_agent(self, role: str = "general", max_tokens: int = 4000) -> str:
        """
        Export playbook as a text block for injection into agent system prompts.
        Selects most relevant bullets, stays within token budget.
        """
        # Role → section mapping for relevance
        role_sections = {
            "planner": ["architecture", "build_ordering", "general"],
            "builder": ["import_resolution", "flask_patterns", "dataclass_patterns",
                        "sqlite_patterns", "stdlib_usage", "error_recovery", "general"],
            "test_gen": ["test_generation", "import_resolution", "general"],
            "initializer": ["architecture", "general"],
            "explorer": ["architecture", "general"],
        }

        relevant_sections = role_sections.get(role, list(self.sections.keys()))

        # Collect bullets from relevant sections, sorted by quality
        bullets = []
        for section in relevant_sections:
            if section in self.sections:
                bullets.extend(self.sections[section])

        import math
        bullets.sort(
            key=lambda b: b.quality_ratio * math.log1p(b.total_references + 1),
            reverse=True
        )

        # Build text, respecting rough token budget (~4 chars per token)
        lines = ["## Coding Playbook (learned patterns — follow these)\n"]
        char_budget = max_tokens * 4
        char_count = len(lines[0])

        for bullet in bullets:
            line = f"- [{bullet.id}] {bullet.content}\n"
            if char_count + len(line) > char_budget:
                break
            lines.append(line)
            char_count += len(line)

        return "".join(lines)

    # ── Deduplication & Pruning ───────────────────────────────────

    def deduplicate(self, similarity_threshold: float = 0.85):
        """
        Remove duplicate bullets using simple text similarity.
        (Uses Jaccard similarity on word sets — no external dependencies.)
        """
        removed = 0
        for section_name in list(self.sections.keys()):
            bullets = self.sections[section_name]
            if len(bullets) < 2:
                continue

            # Compare all pairs, mark lower-quality dupes for removal
            to_remove = set()
            for i in range(len(bullets)):
                if i in to_remove:
                    continue
                for j in range(i + 1, len(bullets)):
                    if j in to_remove:
                        continue
                    sim = self._text_similarity(bullets[i].content, bullets[j].content)
                    if sim >= similarity_threshold:
                        # Keep the one with better quality ratio (or more references)
                        if bullets[i].quality_ratio >= bullets[j].quality_ratio:
                            to_remove.add(j)
                            # Merge counts into survivor
                            bullets[i].helpful_count += bullets[j].helpful_count
                            bullets[i].harmful_count += bullets[j].harmful_count
                        else:
                            to_remove.add(i)
                            bullets[j].helpful_count += bullets[i].helpful_count
                            bullets[j].harmful_count += bullets[i].harmful_count

            if to_remove:
                self.sections[section_name] = [
                    b for idx, b in enumerate(bullets) if idx not in to_remove
                ]
                removed += len(to_remove)

        if removed:
            self.metadata["total_bullets_pruned"] += removed
            self.save()
            logger.info(f"🔄 Deduplicated: removed {removed} duplicate bullets")

        return removed

    def prune_stale(self, stale_days: int = 14, min_quality: float = 0.3):
        """
        Remove bullets that are stale or consistently harmful.
        """
        cutoff = (datetime.now() - timedelta(days=stale_days)).isoformat()
        pruned = 0

        for section_name in list(self.sections.keys()):
            original_len = len(self.sections[section_name])
            self.sections[section_name] = [
                b for b in self.sections[section_name]
                if not self._should_prune(b, cutoff, min_quality)
            ]
            pruned += original_len - len(self.sections[section_name])

        if pruned:
            self.metadata["total_bullets_pruned"] += pruned
            self.save()
            logger.info(f"✂️  Pruned {pruned} stale/harmful bullets")

        return pruned

    def _should_prune(self, bullet: Bullet, cutoff: str, min_quality: float) -> bool:
        """Determine if a bullet should be pruned."""
        # Never prune bullets with < 5 total references (not enough data)
        if bullet.total_references < 5:
            return False
        # Prune if consistently harmful
        if bullet.quality_ratio < min_quality:
            logger.debug(f"  Pruning {bullet.id}: quality {bullet.quality_ratio:.2f} < {min_quality}")
            return True
        # Prune if stale (not referenced recently) AND low usage
        if bullet.last_referenced < cutoff and bullet.total_references < 3:
            logger.debug(f"  Pruning {bullet.id}: stale (last ref {bullet.last_referenced})")
            return True
        return False

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _section_prefix(section: str) -> str:
        """Generate a 2-letter prefix from section name."""
        parts = section.split("_")
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return section[:2].upper()

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """Jaccard similarity on word sets (no dependencies needed)."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def stats(self) -> dict:
        """Get playbook statistics."""
        all_bullets = [b for bullets in self.sections.values() for b in bullets]
        return {
            "total_bullets": len(all_bullets),
            "sections": {name: len(bullets) for name, bullets in self.sections.items()},
            "avg_quality": (
                sum(b.quality_ratio for b in all_bullets) / len(all_bullets)
                if all_bullets else 0
            ),
            "most_helpful": sorted(all_bullets, key=lambda b: b.helpful_count, reverse=True)[:5]
                           if all_bullets else [],
            "metadata": self.metadata,
        }
