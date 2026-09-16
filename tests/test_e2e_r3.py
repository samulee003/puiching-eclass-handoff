#!/usr/bin/env python3
"""E2E Test Suite for Requirement 3 (R3): Dual-Write Truth & Compliance Validation.

Features Covered (Tiers 1 & 2):
- F-23: Atomic Dual-Write Update (status.json & DASHBOARD.md 1:1 synchronization)
- F-24: Non-Homework State Preservation (rewards, rules, ui, schedule, cleared, notes)
- F-25: Strict Item Schema Conformance (Draft-7, additionalProperties: false)
- F-26: Automated Compliance Validation (scripts/validate_status.py gate verification)
"""

import copy
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATUS_JSON = ROOT / "status.json"
DASHBOARD_MD = ROOT / "DASHBOARD.md"
SCHEMA_JSON = ROOT / "schema" / "status.schema.json"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate_status.py"
UPDATE_SCRIPT = ROOT / "scripts" / "update_status.py"

from scripts.update_status import (
    update_child_status,
    atomic_write_text,
    validate_item_conformance,
    update_dashboard_markdown,
    normalize_child_id,
)


def run_validator():
    """Run scripts/validate_status.py in-process or via python execution."""
    sys_path_backup = list(sys.path)
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate_status
        return validate_status.main()
    except Exception:
        res = subprocess.run([sys.executable, str(VALIDATE_SCRIPT)], capture_output=True, text=True)
        return res.returncode
    finally:
        sys.path = sys_path_backup


class TestFeature23AtomicDualWriteUpdate(unittest.TestCase):
    """Tests for F-23: Atomic Dual-Write Update."""

    def setUp(self):
        self.status_data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
        self.dashboard_text = DASHBOARD_MD.read_text(encoding="utf-8")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_status = pathlib.Path(self.temp_dir.name) / "status.json"
        self.temp_dashboard = pathlib.Path(self.temp_dir.name) / "DASHBOARD.md"
        shutil.copy(STATUS_JSON, self.temp_status)
        shutil.copy(DASHBOARD_MD, self.temp_dashboard)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_both_sources_of_truth_exist(self):
        """Both status.json and DASHBOARD.md must exist."""
        self.assertTrue(STATUS_JSON.exists())
        self.assertTrue(DASHBOARD_MD.exists())

    def test_abigail_homework_titles_match_between_json_and_dashboard(self):
        """Every homework item in status.json for Abigail must correspond to an entry in DASHBOARD.md."""
        abigail = next(c for c in self.status_data["children"] if c["id"] == "li-yue")
        for sec in ["due_today", "due_soon", "tests_this_week", "other"]:
            for it in abigail.get(sec, []):
                core_term = re.sub(r"[\(\)（）\s]", "", it["title"])[:6]
                self.assertTrue(
                    any(core_term in line for line in self.dashboard_text.splitlines()),
                    f"Core term {core_term!r} of title {it['title']!r} not found in DASHBOARD.md",
                )

    def test_gloria_homework_titles_match_between_json_and_dashboard(self):
        """Every homework item in status.json for Gloria must correspond to an entry in DASHBOARD.md."""
        gloria = next(c for c in self.status_data["children"] if c["id"] == "li-xin")
        for sec in ["due_today", "due_soon", "tests_this_week", "other"]:
            for it in gloria.get(sec, []):
                core_term = re.sub(r"[\(\)（）\s]", "", it["title"])[:6]
                self.assertTrue(
                    any(core_term in line for line in self.dashboard_text.splitlines()),
                    f"Core term {core_term!r} of title {it['title']!r} not found in DASHBOARD.md",
                )

    def test_closing_loop_section_preserved_in_dashboard(self):
        """DASHBOARD.md must contain the '閉環' section."""
        self.assertIn("## 閉環", self.dashboard_text)

    def test_status_json_updated_at_utc_iso_format(self):
        """status.json updated_at must be valid UTC timestamp ending in 'Z'."""
        updated_at = self.status_data.get("updated_at", "")
        self.assertTrue(updated_at.endswith("Z"), f"updated_at {updated_at!r} must end with 'Z'")
        dt = datetime.datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        self.assertIsInstance(dt, datetime.datetime)

    def test_item_count_consistency(self):
        """Count of items in status.json matches total homework table rows in DASHBOARD.md."""
        total_json_items = sum(
            len(c.get(s, []))
            for c in self.status_data["children"]
            for s in ["due_today", "due_soon", "tests_this_week", "other"]
        )
        md_hw_rows = re.findall(
            r"\|\s*[^|]+\s*\|\s*[^|]+\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|", self.dashboard_text
        )
        self.assertEqual(len(md_hw_rows), total_json_items)

    def test_update_child_status_atomically_updates_both_sources_of_truth(self):
        """update_child_status writes status.json and DASHBOARD.md atomically with 1:1 parity."""
        new_items = {
            "due_today": [
                {
                    "subject": "中文",
                    "title": "第4課生字",
                    "due": "2026-09-15",
                    "submit_required": True,
                }
            ],
            "due_soon": [],
            "tests_this_week": [],
            "other": [],
        }
        update_child_status(
            "li-yue",
            new_items,
            status_path=self.temp_status,
            dashboard_path=self.temp_dashboard,
            validate=True,
        )

        status_on_disk = json.loads(self.temp_status.read_text(encoding="utf-8"))
        abigail = next(c for c in status_on_disk["children"] if c["id"] == "li-yue")
        self.assertEqual(len(abigail["due_today"]), 1)
        self.assertEqual(abigail["due_today"][0]["title"], "第4課生字")
        self.assertTrue(status_on_disk["updated_at"].endswith("Z"))

        dashboard_on_disk = self.temp_dashboard.read_text(encoding="utf-8")
        self.assertIn("第4課生字", dashboard_on_disk)
        self.assertIn("## 閉環", dashboard_on_disk)

    def test_sibling_state_isolation_during_update(self):
        """Updating Abigail never mutates Gloria's data in status.json or DASHBOARD.md."""
        baseline = json.loads(self.temp_status.read_text(encoding="utf-8"))
        gloria_before = next(c for c in baseline["children"] if c["id"] == "li-xin")

        update_child_status(
            "li-yue",
            {"due_today": [], "due_soon": [], "tests_this_week": [], "other": []},
            status_path=self.temp_status,
            dashboard_path=self.temp_dashboard,
            validate=True,
        )

        after = json.loads(self.temp_status.read_text(encoding="utf-8"))
        gloria_after = next(c for c in after["children"] if c["id"] == "li-xin")
        self.assertEqual(gloria_before, gloria_after)

    def test_cli_update_status_dual_write(self):
        """Execute scripts/update_status.py via CLI subprocess."""
        cmd = [
            sys.executable,
            str(UPDATE_SCRIPT),
            "--child",
            "li-yue",
            "--fixture",
            str(ROOT / "tests" / "fixtures" / "eclass_abigail_normal.html"),
            "--status-json",
            str(self.temp_status),
            "--dashboard-md",
            str(self.temp_dashboard),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"CLI failed: {proc.stderr}")
        self.assertIn("Successfully updated", proc.stdout)


class TestFeature24NonHomeworkStatePreservation(unittest.TestCase):
    """Tests for F-24: Non-Homework State Preservation."""

    def setUp(self):
        self.data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))

    def test_rewards_catalog_preserved(self):
        """rewards object and catalog snacks must be preserved."""
        self.assertIn("rewards", self.data)
        rewards = self.data["rewards"]
        self.assertIn("points_per_task", rewards)
        self.assertIn("all_done_bonus", rewards)
        self.assertIn("catalog", rewards)
        snack_ids = [s["id"] for s in rewards["catalog"]]
        self.assertIn("gummy", snack_ids)
        self.assertIn("choco", snack_ids)

    def test_business_rules_preserved(self):
        """rules object is preserved."""
        self.assertIn("rules", self.data)
        rules = self.data["rules"]
        self.assertTrue(rules.get("omit_advanced_subjects_for_li_yue"))
        self.assertTrue(rules.get("li_xin_has_no_advanced_track"))

    def test_scan_schedule_macau_preserved(self):
        """scan_schedule_macau is preserved."""
        self.assertIn("scan_schedule_macau", self.data)
        sched = self.data["scan_schedule_macau"]
        self.assertIn("weekday", sched)
        self.assertIn("sunday", sched)

    def test_ui_configuration_preserved(self):
        """ui config object is preserved."""
        self.assertIn("ui", self.data)
        ui = self.data["ui"]
        self.assertTrue(ui.get("checkable"))

    def test_child_level_metadata_preserved(self):
        """Child non-homework attributes (cleared, chrome_password_saved, login_note, owner) preserved."""
        abigail = next(c for c in self.data["children"] if c["id"] == "li-yue")
        self.assertIn("cleared", abigail)
        self.assertIn("owner", abigail)
        self.assertIn("login_note", abigail)


class TestFeature25StrictItemSchemaConformance(unittest.TestCase):
    """Tests for F-25: Strict Item Schema Conformance."""

    def setUp(self):
        self.schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
        self.data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))

    def test_item_definition_has_additional_properties_false(self):
        """Item definition must forbid extra properties: additionalProperties: false."""
        item_def = self.schema["definitions"]["item"]
        self.assertFalse(item_def.get("additionalProperties"))

    def test_no_extra_fields_in_existing_items(self):
        """All items in status.json have only permitted fields."""
        allowed_keys = {"subject", "title", "due", "submit_required", "note", "detail", "progress"}
        for child in self.data["children"]:
            for sec in ["due_today", "due_soon", "tests_this_week", "other"]:
                for it in child.get(sec, []):
                    extra = set(it.keys()) - allowed_keys
                    self.assertEqual(extra, set(), f"Item {it!r} has forbidden keys: {extra}")

    def test_item_due_date_strictly_matches_regex(self):
        """Due dates must match pattern ^\\d{4}-\\d{2}-\\d{2}$."""
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for child in self.data["children"]:
            for sec in ["due_today", "due_soon", "tests_this_week", "other"]:
                for it in child.get(sec, []):
                    self.assertTrue(pattern.match(it["due"]))

    def test_item_due_date_is_valid_calendar_day(self):
        """Due dates must be real calendar dates (e.g. not 2026-02-30)."""
        for child in self.data["children"]:
            for sec in ["due_today", "due_soon", "tests_this_week", "other"]:
                for it in child.get(sec, []):
                    due_date = datetime.date.fromisoformat(it["due"])
                    self.assertIsInstance(due_date, datetime.date)

    def test_root_schema_version_is_string(self):
        """schema_version must be a string."""
        self.assertIsInstance(self.data.get("schema_version"), str)


class TestFeature26AutomatedComplianceValidation(unittest.TestCase):
    """Tests for F-26: Automated Compliance Validation."""

    def test_validate_status_script_exists(self):
        """scripts/validate_status.py must exist and be executable."""
        self.assertTrue(VALIDATE_SCRIPT.exists())

    def test_status_json_passes_validation(self):
        """Running scripts/validate_status.py against current status.json returns exit code 0."""
        code = run_validator()
        self.assertEqual(code, 0, "validate_status.py must succeed with exit code 0")

    def test_validator_fails_on_invalid_calendar_date(self):
        """Validator must fail on invalid date like 2026-02-31."""
        bad_item = {
            "subject": "測試",
            "title": "非法日期作業",
            "due": "2026-02-31",
            "submit_required": True,
        }
        with self.assertRaises(ValueError) as ctx:
            validate_item_conformance(bad_item)
        self.assertIn("is not a valid calendar date", str(ctx.exception))

    def test_validator_fails_on_forbidden_extra_property(self):
        """Validator must reject item with extra forbidden property like 'completed'."""
        import jsonschema

        schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
        bad_item = {
            "subject": "中文",
            "title": "生字",
            "due": "2026-09-15",
            "completed": True,  # Forbidden
        }
        v = jsonschema.Draft7Validator(schema["definitions"]["item"])
        errors = list(v.iter_errors(bad_item))
        self.assertTrue(len(errors) >= 1)
        with self.assertRaises(ValueError) as ctx:
            validate_item_conformance(bad_item)
        self.assertIn("Forbidden extra keys", str(ctx.exception))

    def test_validator_fails_on_unparseable_updated_at(self):
        """Validator flags malformed updated_at timestamp."""
        bad_ts = "INVALID_TIMESTAMP"
        with self.assertRaises(ValueError):
            datetime.datetime.fromisoformat(bad_ts.replace("Z", "+00:00"))


class TestAdversarialChallengeIter2_2(unittest.TestCase):
    """Adversarial Challenge Suite for Dual-Writer and Validator Compliance (Iteration 2)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_status = pathlib.Path(self.temp_dir.name) / "status.json"
        self.temp_dashboard = pathlib.Path(self.temp_dir.name) / "DASHBOARD.md"
        shutil.copy(STATUS_JSON, self.temp_status)
        shutil.copy(DASHBOARD_MD, self.temp_dashboard)
        self.schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _extract_markdown_child_section(self, md_text: str, child_zh: str) -> str:
        parts = re.split(r"(?m)^(?=##\s+)", md_text)
        for p in parts:
            if p.strip().startswith("## ") and child_zh in p and "閉環" not in p:
                return p.strip()
        return ""

    def test_adversarial_abigail_update_preserves_gloria_completely(self):
        """Updating Abigail never mutates Gloria in status.json or DASHBOARD.md."""
        baseline_json = json.loads(self.temp_status.read_text(encoding="utf-8"))
        gloria_json_before = copy.deepcopy(
            next(c for c in baseline_json["children"] if c["id"] == "li-xin")
        )
        baseline_md = self.temp_dashboard.read_text(encoding="utf-8")
        gloria_md_before = self._extract_markdown_child_section(baseline_md, "李昕")
        self.assertTrue(len(gloria_md_before) > 0, "Gloria section must exist in baseline MD")

        # Adversarially update Abigail with completely new items across all sections
        abigail_new = {
            "due_today": [
                {
                    "subject": "中文",
                    "title": "新中文寫作（第一課）",
                    "due": "2026-09-15",
                    "submit_required": True,
                    "note": "寫在作文本",
                }
            ],
            "due_soon": [
                {
                    "subject": "數學",
                    "title": "練習冊 p.20-22",
                    "due": "2026-09-16",
                    "submit_required": False,
                    "detail": "做單數題即可",
                }
            ],
            "tests_this_week": [
                {
                    "subject": "英文",
                    "title": "Vocabulary Dictation",
                    "due": "2026-09-18",
                    "submit_required": True,
                }
            ],
            "other": [],
        }

        update_child_status(
            "li-yue",
            abigail_new,
            status_path=self.temp_status,
            dashboard_path=self.temp_dashboard,
            validate=True,
        )

        after_json = json.loads(self.temp_status.read_text(encoding="utf-8"))
        gloria_json_after = next(c for c in after_json["children"] if c["id"] == "li-xin")
        self.assertEqual(
            gloria_json_before,
            gloria_json_after,
            "Gloria's status.json data must remain 100% bit-for-bit identical after Abigail update",
        )

        after_md = self.temp_dashboard.read_text(encoding="utf-8")
        gloria_md_after = self._extract_markdown_child_section(after_md, "李昕")
        self.assertEqual(
            gloria_md_before,
            gloria_md_after,
            "Gloria's DASHBOARD.md markdown block must remain 100% bit-for-bit identical",
        )

        # Verify Abigail is updated
        abigail_after = next(c for c in after_json["children"] if c["id"] == "li-yue")
        self.assertEqual(len(abigail_after["due_today"]), 1)
        self.assertEqual(abigail_after["due_today"][0]["title"], "新中文寫作（第一課）")
        self.assertIn("新中文寫作", after_md)
        self.assertIn("## 閉環", after_md)

    def test_adversarial_gloria_update_preserves_abigail_completely(self):
        """Updating Gloria never mutates Abigail in status.json or DASHBOARD.md."""
        baseline_json = json.loads(self.temp_status.read_text(encoding="utf-8"))
        abigail_json_before = copy.deepcopy(
            next(c for c in baseline_json["children"] if c["id"] == "li-yue")
        )
        baseline_md = self.temp_dashboard.read_text(encoding="utf-8")
        abigail_md_before = self._extract_markdown_child_section(baseline_md, "李悅")
        self.assertTrue(len(abigail_md_before) > 0, "Abigail section must exist in baseline MD")

        gloria_new = {
            "due_today": [
                {
                    "subject": "常識",
                    "title": "帶植物葉子一片",
                    "due": "2026-09-15",
                    "submit_required": True,
                }
            ],
            "due_soon": [],
            "tests_this_week": [],
            "other": [],
        }

        update_child_status(
            "li-xin",
            gloria_new,
            status_path=self.temp_status,
            dashboard_path=self.temp_dashboard,
            validate=True,
        )

        after_json = json.loads(self.temp_status.read_text(encoding="utf-8"))
        abigail_json_after = next(c for c in after_json["children"] if c["id"] == "li-yue")
        self.assertEqual(
            abigail_json_before,
            abigail_json_after,
            "Abigail's status.json data must remain 100% bit-for-bit identical after Gloria update",
        )

        after_md = self.temp_dashboard.read_text(encoding="utf-8")
        abigail_md_after = self._extract_markdown_child_section(after_md, "李悅")
        self.assertEqual(
            abigail_md_before,
            abigail_md_after,
            "Abigail's DASHBOARD.md markdown block must remain 100% bit-for-bit identical",
        )

    def test_adversarial_preservation_of_all_non_homework_properties(self):
        """Dual-write preserves all non-homework properties: rewards, rules, schedule, ui, cleared, metadata."""
        baseline = json.loads(self.temp_status.read_text(encoding="utf-8"))
        # Set cleared: true on Abigail to verify it is NOT clobbered or reset to false
        for c in baseline["children"]:
            if c["id"] == "li-yue":
                c["cleared"] = True
                c["custom_flag_for_test"] = "test_value"
        self.temp_status.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")

        expected_rewards = copy.deepcopy(baseline["rewards"])
        expected_rules = copy.deepcopy(baseline["rules"])
        expected_schedule = copy.deepcopy(baseline["scan_schedule_macau"])
        expected_ui = copy.deepcopy(baseline["ui"])
        expected_repo = baseline["repo"]
        expected_tz = baseline["timezone"]
        expected_version = baseline["schema_version"]

        # Run update
        update_child_status(
            "li-yue",
            {"due_today": [], "due_soon": [], "tests_this_week": [], "other": []},
            status_path=self.temp_status,
            dashboard_path=self.temp_dashboard,
            validate=True,
        )

        after = json.loads(self.temp_status.read_text(encoding="utf-8"))
        self.assertEqual(after["rewards"], expected_rewards, "rewards object must be preserved")
        self.assertEqual(after["rules"], expected_rules, "rules object must be preserved")
        self.assertEqual(after["scan_schedule_macau"], expected_schedule, "scan_schedule_macau must be preserved")
        self.assertEqual(after["ui"], expected_ui, "ui object must be preserved")
        self.assertEqual(after["repo"], expected_repo, "repo must be preserved")
        self.assertEqual(after["timezone"], expected_tz, "timezone must be preserved")
        self.assertEqual(after["schema_version"], expected_version, "schema_version must be preserved")

        abigail = next(c for c in after["children"] if c["id"] == "li-yue")
        self.assertEqual(abigail["cleared"], True, "cleared: true must be preserved across updates")
        self.assertEqual(abigail.get("custom_flag_for_test"), "test_value", "custom child metadata preserved")
        self.assertTrue(abigail["chrome_password_saved"])
        self.assertEqual(abigail["owner"], "grok-liubei")
        self.assertIn("p21528136", abigail["login_note"])

    def test_adversarial_atomic_dual_write_failure_safety(self):
        """Atomic dual-write must not mutate files and leave no temp files on validation error."""
        status_before = self.temp_status.read_text(encoding="utf-8")
        dashboard_before = self.temp_dashboard.read_text(encoding="utf-8")

        bad_items = {
            "due_today": [
                {
                    "subject": "中文",
                    "title": "非法作業",
                    "due": "2026-02-31",  # Invalid date
                    "submit_required": True,
                }
            ]
        }

        with self.assertRaises(ValueError) as ctx:
            update_child_status(
                "li-yue",
                bad_items,
                status_path=self.temp_status,
                dashboard_path=self.temp_dashboard,
                validate=True,
            )
        self.assertIn("not a valid calendar date", str(ctx.exception))

        # Assert files on disk are completely unchanged
        status_after = self.temp_status.read_text(encoding="utf-8")
        dashboard_after = self.temp_dashboard.read_text(encoding="utf-8")
        self.assertEqual(status_before, status_after, "status.json must not be modified on error")
        self.assertEqual(dashboard_before, dashboard_after, "DASHBOARD.md must not be modified on error")

        # Assert no leftover .tmp files
        tmp_files = list(pathlib.Path(self.temp_dir.name).glob("*.tmp"))
        self.assertEqual(len(tmp_files), 0, f"No .tmp files should be left behind: {tmp_files}")

    def test_adversarial_validator_rejection_of_forbidden_extra_properties(self):
        """Validator strictly rejects extra properties (e.g. completed: true, points: 10, is_done: true)."""
        import jsonschema

        item_validator = jsonschema.Draft7Validator(self.schema["definitions"]["item"])

        forbidden_cases = [
            {"subject": "中文", "title": "作業", "due": "2026-09-15", "completed": True},
            {"subject": "英文", "title": "Quiz", "due": "2026-09-16", "is_done": False},
            {"subject": "數學", "title": "習作", "due": "2026-09-17", "points": 10},
            {"subject": "常識", "title": "觀察", "due": "2026-09-18", "score": 100},
            {"subject": "導師", "title": "通知", "due": "2026-09-19", "tags": ["urgent"]},
        ]

        for bad_item in forbidden_cases:
            # 1. Schema rejection
            errors = list(item_validator.iter_errors(bad_item))
            self.assertTrue(
                len(errors) >= 1,
                f"Draft7Validator should reject item with forbidden property: {bad_item}",
            )
            # 2. update_status validation rejection
            with self.assertRaises(ValueError) as ctx:
                validate_item_conformance(bad_item)
            self.assertIn("Forbidden extra keys", str(ctx.exception))

    def test_adversarial_validator_rejection_of_invalid_calendar_dates(self):
        """Validator strictly rejects all non-existent and invalid calendar dates."""
        invalid_dates = [
            "2026-02-31",  # Feb 31 does not exist
            "2026-02-29",  # 2026 is not a leap year
            "2026-04-31",  # April has only 30 days
            "2026-06-31",  # June has only 30 days
            "2026-09-31",  # September has only 30 days
            "2026-11-31",  # November has only 30 days
            "2026-13-01",  # Month 13
            "2026-00-15",  # Month 0
            "2026-09-00",  # Day 0
            "2026-09-32",  # Day 32
            "2026/09/15",  # Slashes instead of dashes
            "15-09-2026",  # DD-MM-YYYY
            "2026-9-15",   # Missing leading zero
            "invalid-date",
            "",
        ]

        for bad_date in invalid_dates:
            bad_item = {
                "subject": "測試科",
                "title": f"測試作業-{bad_date}",
                "due": bad_date,
                "submit_required": True,
            }
            with self.assertRaises(ValueError, msg=f"Should reject due date: {bad_date!r}") as ctx:
                validate_item_conformance(bad_item)
            err_msg = str(ctx.exception)
            self.assertTrue(
                "must match YYYY-MM-DD pattern" in err_msg
                or "is not a valid calendar date" in err_msg,
                f"Expected calendar date error for {bad_date!r}, got: {err_msg}",
            )

    def test_adversarial_validator_rejection_of_invalid_iso_timestamps(self):
        """Validator strictly rejects invalid updated_at ISO timestamps."""
        import jsonschema

        root_validator = jsonschema.Draft7Validator(self.schema)
        base_data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))

        invalid_timestamps = [
            ("INVALID_TIMESTAMP", "unparseable string"),
            ("2026-09-15 14:26:26", "missing T separator"),
            ("2026-09-15T14:26:26", "missing Z or offset"),
            ("2026-02-31T14:26:26Z", "invalid calendar date (Feb 31)"),
            ("2026-13-01T14:26:26Z", "invalid month 13"),
            ("2026-09-15T25:00:00Z", "invalid hour 25"),
            ("2026-09-15T14:60:00Z", "invalid minute 60"),
            ("2026-09-15T14:26:60Z", "invalid second 60"),
            ("", "empty string"),
        ]

        for bad_ts, desc in invalid_timestamps:
            test_data = copy.deepcopy(base_data)
            test_data["updated_at"] = bad_ts

            # Either schema pattern fails or datetime parser fails
            schema_errors = list(root_validator.iter_errors(test_data))
            ts_schema_err = any(e.path and e.path[0] == "updated_at" for e in schema_errors)

            semantic_err = False
            try:
                dt = datetime.datetime.fromisoformat(bad_ts.replace("Z", "+00:00"))
                if dt.year < 2000 or dt.month > 12 or dt.day > 31:
                    semantic_err = True
            except (ValueError, AttributeError):
                semantic_err = True

            self.assertTrue(
                ts_schema_err or semantic_err,
                f"Timestamp {bad_ts!r} ({desc}) should be rejected by schema or datetime parser",
            )


if __name__ == "__main__":
    unittest.main()

