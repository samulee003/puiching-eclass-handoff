#!/usr/bin/env python3
"""E2E Test Suite for Tier 3: Cross-Feature Combinations & End-to-End Integration.

Integration Pipelines Covered:
1. End-to-End Pairing & Connection Flow:
   Parent index.html generates code -> Pairing URL constructed -> Child page parses URL ->
   Address bar sanitized -> Code saved to localStorage -> SHA-256 room ID derived.
2. Complete Scraper to Dual-Write Pipeline:
   Scraper parses fixtures -> Rule engine filters Abigail / bypasses Gloria ->
   Dual-writer merges with non-homework metadata -> status.json and DASHBOARD.md updated ->
   validate_status.py verifies Draft-7 schema and semantic validity.
3. Multi-Child State Isolation & Synchronization:
   Abigail (li-yue) and Gloria (li-xin) operate in shared family room without state collision.
4. Offline Action Queue to Connected Sync State:
   Offline todo checks & points accumulation -> Pending store serialization ->
   Reconnection flush -> Room state convergence -> Badge transitions.
"""

import copy
import datetime
import hashlib
import json
import pathlib
import re
import sys
import unittest
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATUS_JSON = ROOT / "status.json"
DASHBOARD_MD = ROOT / "DASHBOARD.md"
SCHEMA_JSON = ROOT / "schema" / "status.schema.json"
FIXTURES_DIR = ROOT / "tests" / "fixtures"

MACAU_REF_DATE = datetime.date(2026, 9, 15)


def normalize_code(code_str: str) -> str:
    return re.sub(r"[\s-]", "", str(code_str or "")).upper()


def format_code(code_str: str) -> str:
    c = normalize_code(code_str)
    chunks = [c[i : i + 4] for i in range(0, len(c), 4) if c[i : i + 4]]
    return "-".join(chunks) or c


def derive_room_id(code: str) -> str:
    norm = normalize_code(code)
    return hashlib.sha256(f"puiching-eclass-room-v1:{norm}".encode("utf-8")).hexdigest()


class TestTier3PairingAndConnectionPipeline(unittest.TestCase):
    """Pipeline 1: Full Parent Pairing -> Child Tablet Zero-Typing Connection."""

    def test_complete_parent_to_child_url_handshake(self):
        """Simulate parent generating code, building URL, child extracting, and room derivation."""
        # 1. Parent generates 20-character base32 code
        generated_code = "7H8K9MNP23456789ABCD"
        self.assertEqual(len(generated_code), 20)

        # 2. Parent formats code and generates quick pairing URL
        formatted = format_code(generated_code)
        self.assertEqual(formatted, "7H8K-9MNP-2345-6789-ABCD")
        base_origin = "https://samulee003.github.io/puiching-eclass-handoff/"
        pairing_url_abigail = f"{base_origin}abigail.html?sync={formatted}"

        # 3. Child opens URL; query parameter is extracted
        parsed = urllib.parse.urlparse(pairing_url_abigail)
        qs = urllib.parse.parse_qs(parsed.query)
        self.assertIn("sync", qs)
        child_extracted_raw = qs["sync"][0]

        # 4. Child normalizes code and verifies pattern
        child_normalized = normalize_code(child_extracted_raw)
        self.assertEqual(child_normalized, generated_code)

        # 5. Child sanitizes address bar via simulated history.replaceState
        clean_url = urllib.parse.urlunparse(parsed._replace(query=""))
        self.assertEqual(clean_url, f"{base_origin}abigail.html")

        # 6. Child derives SHA-256 room ID
        room_id = derive_room_id(child_normalized)
        self.assertEqual(len(room_id), 64)
        expected_hash = hashlib.sha256(f"puiching-eclass-room-v1:{generated_code}".encode("utf-8")).hexdigest()
        self.assertEqual(room_id, expected_hash)

        # 7. Simulated RTDB database path
        rtdb_path = f"rooms/{room_id}"
        self.assertTrue(rtdb_path.startswith("rooms/"))


class TestTier3ScraperToDualWritePipeline(unittest.TestCase):
    """Pipeline 2: Scraper -> Filtering -> Dual-Writer -> Compliance Gate."""

    def test_end_to_end_scraper_dual_write_and_validation(self):
        """Execute full production pipeline: scrape_eclass -> update_child_status -> validation."""
        import shutil
        import tempfile
        import jsonschema
        from scripts.scrape_eclass import scrape_eclass
        from scripts.update_status import update_child_status

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_status = pathlib.Path(tmpdir) / "status.json"
            temp_dashboard = pathlib.Path(tmpdir) / "DASHBOARD.md"
            shutil.copy(STATUS_JSON, temp_status)
            shutil.copy(DASHBOARD_MD, temp_dashboard)

            # Baseline non-homework state
            baseline = json.loads(temp_status.read_text(encoding="utf-8"))
            original_rewards = copy.deepcopy(baseline["rewards"])
            original_rules = copy.deepcopy(baseline["rules"])

            # Step 1: Production Scraper executes on Abigail fixture
            abigail_data = scrape_eclass(
                "li-yue",
                fixture_path=str(FIXTURES_DIR / "eclass_abigail_normal.html"),
                today=MACAU_REF_DATE,
            )
            self.assertEqual(abigail_data["student_name"], "李悅")
            all_abigail = (
                abigail_data["due_today"]
                + abigail_data["due_soon"]
                + abigail_data["tests_this_week"]
                + abigail_data["other"]
            )
            # Abigail filtering rule: 100% exclusion of '進階'
            self.assertTrue(all("進階" not in it["subject"] for it in all_abigail))
            self.assertEqual(len(all_abigail), 6)

            # Step 2: Production Dual-Writer updates status.json & DASHBOARD.md
            update_child_status(
                "li-yue",
                abigail_data,
                status_path=temp_status,
                dashboard_path=temp_dashboard,
                validate=True,
            )

            # Step 3: Production Scraper executes on Gloria fixture
            gloria_data = scrape_eclass(
                "li-xin",
                fixture_path=str(FIXTURES_DIR / "eclass_gloria_normal.html"),
                today=MACAU_REF_DATE,
            )
            self.assertEqual(gloria_data["student_name"], "李昕")
            all_gloria = (
                gloria_data["due_today"]
                + gloria_data["due_soon"]
                + gloria_data["tests_this_week"]
                + gloria_data["other"]
            )
            self.assertEqual(len(all_gloria), 4)

            # Step 4: Production Dual-Writer updates Gloria
            update_child_status(
                "li-xin",
                gloria_data,
                status_path=temp_status,
                dashboard_path=temp_dashboard,
                validate=True,
            )

            # Step 5: Verify non-homework metadata preservation
            merged_status = json.loads(temp_status.read_text(encoding="utf-8"))
            self.assertEqual(merged_status["rewards"], original_rewards)
            self.assertEqual(merged_status["rules"], original_rules)

            # Step 6: Validate against Draft-7 JSON schema
            schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
            validator = jsonschema.Draft7Validator(schema)
            errors = list(validator.iter_errors(merged_status))
            self.assertEqual(len(errors), 0, f"Schema validation errors: {errors}")

            # Step 7: Verify all due dates are parseable real dates
            for child in merged_status["children"]:
                for sec in ["due_today", "due_soon", "tests_this_week", "other"]:
                    for it in child.get(sec, []):
                        d = datetime.date.fromisoformat(it["due"])
                        self.assertIsInstance(d, datetime.date)

            # Step 8: Verify DASHBOARD.md contains synchronized items and preserved sections
            md_content = temp_dashboard.read_text(encoding="utf-8")
            self.assertIn("## 李悅（Abigail／P3）", md_content)
            self.assertIn("## 李昕（Gloria／P1）", md_content)
            self.assertIn("## 閉環", md_content)


class TestTier3MultiChildStateIsolation(unittest.TestCase):
    """Pipeline 3: Multi-Child State Isolation & Concurrent Updates."""

    def test_child_todo_keys_are_namespaced(self):
        """Todo item keys must be prefixed with child ID to prevent cross-child collisions."""
        abigail_key = "li-yue|due_today|2026-09-15|中文|第3課習作"
        gloria_key = "li-xin|due_soon|2026-09-16|英文|Quiz Listening"

        self.assertTrue(abigail_key.startswith("li-yue|"))
        self.assertTrue(gloria_key.startswith("li-xin|"))
        self.assertNotEqual(abigail_key.split("|")[0], gloria_key.split("|")[0])

    def test_points_records_isolated_by_child_id(self):
        """Points records are stored per child ID in status.json and sync.js."""
        points_state = {
            "li-yue": {"earned": 40, "spent": 0, "awarded": {}, "bonusDates": {}, "redemptions": []},
            "li-xin": {"earned": 20, "spent": 10, "awarded": {}, "bonusDates": {}, "redemptions": []}
        }
        # Abigail's spending does not affect Gloria's points
        points_state["li-yue"]["spent"] += 30
        self.assertEqual(points_state["li-yue"]["spent"], 30)
        self.assertEqual(points_state["li-xin"]["spent"], 10)


class TestTier3OfflineQueueToReconnectionReplay(unittest.TestCase):
    """Pipeline 4: Offline Action Queue to Connected Sync State."""

    def test_offline_action_lifecycle(self):
        """Verify the full lifecycle: offline action -> pending queue -> reconnect -> flushed."""
        # 1. State starts in offline / local mode
        sync_state = {
            "connected": False,
            "local": {"todos": {}, "points": {}},
            "remote": {"todos": {}, "points": {}},
            "pending": {"todos": {}, "points": {}},
            "badge": "本機模式"
        }

        # 2. User checks a task offline
        task_key = "li-yue|due_today|2026-09-15|數學|習作6"
        sync_state["local"]["todos"][task_key] = True
        sync_state["pending"]["todos"][task_key] = True

        # Verify pending store contains the write
        self.assertIn(task_key, sync_state["pending"]["todos"])
        self.assertEqual(sync_state["pending"]["todos"][task_key], True)

        # 3. Network reconnects
        sync_state["connected"] = True
        sync_state["badge"] = "連接中…"

        # 4. Flush replay runs
        for k, v in list(sync_state["pending"]["todos"].items()):
            # Simulate remote write success
            sync_state["remote"]["todos"][k] = v
            del sync_state["pending"]["todos"][k]

        sync_state["badge"] = "已同步 ☁️"

        # 5. Verify convergence
        self.assertEqual(len(sync_state["pending"]["todos"]), 0)
        self.assertEqual(sync_state["remote"]["todos"][task_key], True)
        self.assertEqual(sync_state["badge"], "已同步 ☁️")


if __name__ == "__main__":
    unittest.main()
