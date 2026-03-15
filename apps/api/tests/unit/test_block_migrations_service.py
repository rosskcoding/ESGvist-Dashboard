"""
Unit tests for block schema migrations (app.services.block_migrations).
"""

from app.services.block_migrations import migrate_block_data, needs_migration


class TestBlockMigrations:
    def test_needs_migration_true_for_timeline_v1(self):
        assert needs_migration("timeline", {"schema_version": 1, "items": []}) is True

    def test_migrate_timeline_v1_to_v2(self):
        migrated = migrate_block_data(
            "timeline",
            {
                "schema_version": 1,
                "items": [
                    {
                        "event_id": "e1",
                        "date": "2024",
                        "icon": None,
                    }
                ],
            },
        )
        assert migrated["schema_version"] == 2
        assert "events" in migrated
        assert len(migrated["events"]) == 1
        e0 = migrated["events"][0]
        assert e0["date_start"] == "2024"
        assert e0["date_kind"] == "year"
        assert "tags" in e0 and e0["tags"] == []
        assert "auto_sort_by_date" in migrated





