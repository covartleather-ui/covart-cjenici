"""Offline regression tests for change-only price-list publication."""
import csv
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_price_lists as mod


class PublicationTests(unittest.TestCase):
    def test_reordering_is_not_a_change_but_duplicates_and_values_are(self):
        rows = [{"name": "A", "price": "10"}, {"name": "B", "price": "20"}]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            current = root / "current"
            current.mkdir()
            (current / "manifest.json").write_text(json.dumps({
                "files": {"webshop_csv": "current/products.csv"}
            }))
            with (current / "products.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["name", "price"], delimiter=";")
                writer.writeheader()
                writer.writerows(rows)
            with patch.object(mod, "ROOT", root), patch.object(mod, "CURRENT", current):
                self.assertTrue(mod.current_rows_match({"webshop_csv": rows[::-1]}))
                self.assertFalse(mod.current_rows_match({"webshop_csv": rows + rows[:1]}))
                self.assertFalse(mod.current_rows_match({
                    "webshop_csv": [rows[0], {"name": "B", "price": "21"}]
                }))

    def run_main(self, event, cron, last_date, matches):
        source = {
            "products": {"nodes": [{"title": "Belt", "vendor": "Covart", "variants": {
                "nodes": [{"sku": "B1", "barcode": "COV0000001", "price": "60",
                           "compareAtPrice": None, "availableForSale": True,
                           "anchor": {"value": "60"}}]}}]},
            "workshop": {"nodes": []},
            "service": {"nodes": [{"active": {"value": "true"}, "name": {"value": "Delivery"},
                                   "current": {"value": "8"}, "anchor": {"value": "8"}}]},
        }
        with patch.object(mod, "EVENT_NAME", event), patch.object(mod, "SCHEDULE_CRON", cron), \
             patch.object(mod, "datetime") as clock, \
             patch.object(mod, "load_state", return_value={"last_sequence": 34, "last_date": last_date}), \
             patch.object(mod, "ensure_identifiers"), patch.object(mod, "graphql", return_value=source), \
             patch.object(mod, "current_rows_match", return_value=matches) as compare, \
             patch.object(mod, "clean_current", side_effect=RuntimeError("publication reached")) as publish:
            clock.now.return_value = datetime(2026, 10, 23, 7, 35, tzinfo=mod.TZ)
            if matches:
                mod.main()
                publish.assert_not_called()
            else:
                with self.assertRaisesRegex(RuntimeError, "publication reached"):
                    mod.main()
                publish.assert_called_once()
            compare.assert_called_once()

    def test_unchanged_next_day_does_not_publish(self):
        self.run_main("schedule", "35 5 * * *", "2026-10-22", True)

    def test_manual_and_push_runs_do_not_force_unchanged_publication(self):
        for event in ("workflow_dispatch", "push"):
            with self.subTest(event=event):
                self.run_main(event, "", "2026-10-22", True)

    def test_changed_same_day_is_not_suppressed_by_morning_slot(self):
        self.run_main("schedule", "35 5 * * *", "2026-10-23", False)

    def test_changed_hourly_run_publishes(self):
        self.run_main("schedule", "45 * * * *", "2026-10-22", False)


    def test_new_publication_preserves_historical_archives(self):
        source = {
            "products": {"nodes": [{
                "title": "Belt", "vendor": "Covart",
                "variants": {"nodes": [{
                    "sku": "B1", "barcode": "COV0000001",
                    "price": "60", "compareAtPrice": None,
                    "availableForSale": True, "anchor": {"value": "60"}
                }]}
            }]},
            "workshop": {"nodes": []},
            "service": {"nodes": [{
                "active": {"value": "true"}, "name": {"value": "Delivery"},
                "current": {"value": "8"}, "anchor": {"value": "8"}
            }]},
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "archive"
            historical = archive / "2026-09-25" / "old.csv"
            historical.parent.mkdir(parents=True)
            historical.write_text("previous valid cjenik", encoding="utf-8")
            with patch.multiple(mod, ROOT=root, CURRENT=root / "current",
                                ARCHIVE=archive, STATE_FILE=root / "state.json",
                                EVENT_NAME="push", SCHEDULE_CRON=""), \
                 patch.object(mod, "ensure_identifiers"), \
                 patch.object(mod, "load_state", return_value={
                     "last_sequence": 38, "last_barcode_number": 117
                 }), \
                 patch.object(mod, "current_rows_match", return_value=False), \
                 patch.object(mod, "graphql", return_value=source):
                mod.main()
            self.assertTrue(historical.exists())
            self.assertEqual(historical.read_text(encoding="utf-8"),
                             "previous valid cjenik")


if __name__ == "__main__":
    unittest.main()
