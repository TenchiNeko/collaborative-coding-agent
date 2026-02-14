#!/usr/bin/env python3
"""
Seed the playbook with patterns we already know from debugging sessions.
Run on PVE node: python3 seed_playbook.py

These are high-confidence patterns extracted from our v0.9.9a-v1.0 sessions.
"""

import json
from datetime import datetime
from pathlib import Path

PLAYBOOK_PATH = "/shared/playbook.json"

SEED_BULLETS = [
    # import_resolution
    {
        "section": "import_resolution",
        "content": "Use flat imports with exact filename stems: `from models import Bookmark`, `from database import BookmarkDB`. Never use package-style imports like `from app.models import Bookmark` in flat-file projects.",
        "helpful_count": 5,
    },
    {
        "section": "import_resolution",
        "content": "When the manifest shows `models.py` exports `Bookmark(id, url, title, tags, created_at)`, import exactly that name — not `BookmarkModel` or `BookmarkSchema`.",
        "helpful_count": 3,
    },
    {
        "section": "import_resolution",
        "content": "For test files, always import the source module first and verify the import works before writing any test functions. If the import fails, the entire test file gets 0/N.",
        "helpful_count": 4,
    },

    # test_generation
    {
        "section": "test_generation",
        "content": "Write tests against the specification, not the source code. Read the task description and write tests that verify the spec, then check if the source code passes them.",
        "helpful_count": 3,
    },
    {
        "section": "test_generation",
        "content": "For Flask apps, use `app.test_client()` not `requests`. Set up the test client in setUp() and create a fresh database for each test to avoid state leakage.",
        "helpful_count": 4,
    },
    {
        "section": "test_generation",
        "content": "When testing Flask endpoints, always check `response.status_code` first, then parse `response.get_json()`. Don't assume the response body structure without checking status.",
        "helpful_count": 2,
    },

    # build_ordering
    {
        "section": "build_ordering",
        "content": "Build source files in dependency order: models.py → database.py → validators.py → app.py. Then build test files in same dependency order.",
        "helpful_count": 5,
    },
    {
        "section": "build_ordering",
        "content": "When a source file is rebuilt in a retry iteration, ALL files that import from it must also be rebuilt. Otherwise tests run against stale APIs and fail with import_error.",
        "helpful_count": 6,
    },

    # flask_patterns
    {
        "section": "flask_patterns",
        "content": "Initialize the database inside `create_app()` or before `app.run()`, not at module level. Module-level DB init breaks test isolation.",
        "helpful_count": 3,
    },
    {
        "section": "flask_patterns",
        "content": "For pagination, accept `page` and `per_page` query parameters with sensible defaults (page=1, per_page=20). Return a JSON object with `items`, `page`, `per_page`, and `total` keys.",
        "helpful_count": 2,
    },

    # sqlite_patterns
    {
        "section": "sqlite_patterns",
        "content": "Use context managers for database connections: `with sqlite3.connect(db_path) as conn:`. Never leave connections open or call conn.close() in __init__.",
        "helpful_count": 4,
    },
    {
        "section": "sqlite_patterns",
        "content": "When returning query results, always unpack sqlite3.Row into the dataclass/namedtuple. Never return raw cursor.fetchone() — it's a tuple, not a domain object.",
        "helpful_count": 5,
    },

    # dataclass_patterns
    {
        "section": "dataclass_patterns",
        "content": "For dataclass constructors with defaults, put required fields first and optional fields (with defaults) last. `@dataclass class Bookmark: id: int; url: str; title: str; tags: str = ''; created_at: str = ''`",
        "helpful_count": 2,
    },

    # error_recovery
    {
        "section": "error_recovery",
        "content": "When all 4+ candidates for a test file fail with the same error (e.g., import_error), the problem is in the source file, not the test. Don't keep regenerating the test — fix the source.",
        "helpful_count": 6,
    },
    {
        "section": "error_recovery",
        "content": "For files under 80 lines, skip SEARCH/REPLACE edit repair and use whole-file regeneration instead. Small files are faster and more reliably regenerated than surgically patched.",
        "helpful_count": 3,
    },

    # general
    {
        "section": "general",
        "content": "Always read the manifest's 'Files Built So Far' section and match the exact function signatures and class names shown there. The manifest is the ground truth for APIs.",
        "helpful_count": 5,
    },
    {
        "section": "general",
        "content": "Use stdlib only — sqlite3, json, datetime, dataclasses. Never import external packages (SQLAlchemy, marshmallow, pydantic) unless explicitly requested in the task.",
        "helpful_count": 4,
    },
]


def main():
    path = Path(PLAYBOOK_PATH)

    # Load existing or create new
    if path.exists():
        data = json.loads(path.read_text())
        print(f"📖 Loaded existing playbook: {sum(len(v) for v in data.get('sections', {}).values())} bullets")
    else:
        data = {
            "version": "0.1.0",
            "last_updated": "",
            "token_budget": 8000,
            "metadata": {
                "total_sessions_analyzed": 0,
                "total_deltas_applied": 0,
                "total_bullets_pruned": 0,
            },
            "next_ids": {},
            "sections": {},
        }
        print("✨ Creating new playbook")

    # Section prefixes
    def section_prefix(section):
        parts = section.split("_")
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return section[:2].upper()

    sections = data.get("sections", {})
    next_ids = data.get("next_ids", {})

    added = 0
    for bullet in SEED_BULLETS:
        section = bullet["section"]

        if section not in sections:
            sections[section] = []
        if section not in next_ids:
            next_ids[section] = 1

        # Check for duplicates (simple word overlap)
        content = bullet["content"]
        content_words = set(content.lower().split())
        is_dupe = False
        for existing in sections[section]:
            existing_words = set(existing.get("content", "").lower().split())
            if content_words and existing_words:
                overlap = len(content_words & existing_words) / len(content_words | existing_words)
                if overlap > 0.7:
                    is_dupe = True
                    break

        if is_dupe:
            continue

        prefix = section_prefix(section)
        bid = f"{prefix}-{next_ids[section]:03d}"
        next_ids[section] += 1

        sections[section].append({
            "id": bid,
            "content": content,
            "section": section,
            "helpful_count": bullet.get("helpful_count", 0),
            "harmful_count": 0,
            "source_session": "seed-v1.0",
            "added": datetime.now().isoformat(),
            "last_referenced": datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat(),
        })
        added += 1
        print(f"  ➕ [{bid}] {content[:70]}...")

    data["sections"] = sections
    data["next_ids"] = next_ids
    data["last_updated"] = datetime.now().isoformat()
    data["metadata"]["total_deltas_applied"] = data["metadata"].get("total_deltas_applied", 0) + added

    # Atomic write
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path)

    total = sum(len(v) for v in sections.values())
    print(f"\n✅ Playbook seeded: {added} new bullets added ({total} total)")


if __name__ == "__main__":
    main()
