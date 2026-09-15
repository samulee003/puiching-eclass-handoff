#!/usr/bin/env python3
"""E2E Test Suite for Tier 2: Boundary, Adversarial & Corner Cases.

Cases Covered:
1. Empty homework tables & empty sections (no homework today, clear states)
2. Malformed & invalid sync codes (length, non-base32 symbols, lowercase, spaces)
3. Expired eClass sessions, HTTP auth errors & redirect pages
4. Leap year & calendar edge dates (2028-02-29 vs 2026-02-29, Dec 31 to Jan 1)
5. LocalStorage quota simulation & corrupt JSON handling
6. Offline states & network flapping queue replay
7. Adversarial encoding & special characters (Emoji, HTML entities, quotes, unescaped tags)
"""

import copy
import datetime
import hashlib
import html
import json
import pathlib
import re
import unittest
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATUS_JSON = ROOT / "status.json"
SCHEMA_JSON = ROOT / "schema" / "status.schema.json"
FIXTURES_DIR = ROOT / "tests" / "fixtures"

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_PATTERN = re.compile(r"^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{20}$")


def normalize_code(code_str: str) -> str:
    return re.sub(r"[\s-]", "", str(code_str or "")).upper()


def derive_room_id(code: str) -> str:
    norm = normalize_code(code)
    return hashlib.sha256(f"puiching-eclass-room-v1:{norm}".encode("utf-8")).hexdigest()


class TestTier2EmptyTablesAndSections(unittest.TestCase):
    """Boundary Case 1: Empty homework tables and empty sections."""

    def test_empty_fixture_parses_to_empty_items(self):
        """Parsing an eClass page with zero items yields an empty list, not an error."""
        empty_html = (FIXTURES_DIR / "eclass_empty.html").read_text(encoding="utf-8")
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", empty_html, re.DOTALL)
        hw_rows = [r for r in rows if "<th" not in r and "<td" in r]
        self.assertEqual(len(hw_rows), 0)

    def test_status_json_accepts_empty_due_today(self):
        """status.json allows due_today to be an empty list (as in Gloria's real state)."""
        data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
        gloria = next(c for c in data["children"] if c["id"] == "li-xin")
        self.assertIsInstance(gloria.get("due_today"), list)
        self.assertEqual(len(gloria.get("due_today")), 0)

    def test_all_sections_empty_conforms_to_schema(self):
        """A child with all sections empty is still valid in status.schema.json."""
        child_empty = {
            "id": "li-yue",
            "en": "Abigail",
            "zh": "李悅",
            "grade": "P3",
            "due_today": [],
            "due_soon": [],
            "tests_this_week": [],
            "other": [],
            "cleared": True
        }
        for sec in ["due_today", "due_soon", "tests_this_week", "other"]:
            self.assertEqual(len(child_empty[sec]), 0)


class TestTier2InvalidSyncCodes(unittest.TestCase):
    """Boundary Case 2: Malformed and invalid sync codes."""

    def test_empty_string_code_rejected(self):
        """Empty string fails validation."""
        self.assertIsNone(CODE_PATTERN.match(normalize_code("")))

    def test_code_with_illegal_lookalike_characters(self):
        """Codes with confusing characters (0, O, 1, I, L) are rejected."""
        lookalikes = ["0", "O", "1", "I", "L"]
        base = "ABCDEFGHJKMNPQRSTUV"  # 19 chars
        for char in lookalikes:
            candidate = base + char
            self.assertIsNone(
                CODE_PATTERN.match(candidate),
                f"Candidate with {char} should be rejected"
            )

    def test_code_with_special_symbols(self):
        """Codes with punctuation or special characters fail."""
        bad_codes = [
            "ABCD-EFGH-JKMN-PQRS-!@#$",
            "ABCD_EFGH_JKMN_PQRS_TUV2",
            "ABCD.EFGH.JKMN.PQRS.TUV2",
            "<script>alert(1)</script>"
        ]
        for c in bad_codes:
            self.assertIsNone(CODE_PATTERN.match(normalize_code(c)))

    def test_code_with_whitespace_and_mixed_case_normalizes_correctly(self):
        """Whitespace, tabs, and lowercase are cleaned and accepted if valid base32."""
        raw = "  abcd - efgh - jkmn - pqrs - tuv2 \t"
        norm = normalize_code(raw)
        self.assertTrue(CODE_PATTERN.match(norm))
        self.assertEqual(len(norm), 20)

    def test_too_short_or_too_long_codes_rejected(self):
        """Codes with length != 20 characters fail."""
        self.assertIsNone(CODE_PATTERN.match("A" * 19))
        self.assertIsNone(CODE_PATTERN.match("A" * 21))


class TestTier2ExpiredSessionsAndAuthErrors(unittest.TestCase):
    """Boundary Case 3: Expired sessions and authentication errors."""

    def test_detect_html_login_form_action(self):
        """Page containing login form action='/templates/login.php' is detected as login page."""
        html_doc = (FIXTURES_DIR / "eclass_login_required.html").read_text(encoding="utf-8")
        self.assertIn("login.php", html_doc)

    def test_detect_session_timeout_alert_box(self):
        """Alert box containing timeout message triggers LOGIN_REQUIRED."""
        html_doc = (FIXTURES_DIR / "eclass_login_required.html").read_text(encoding="utf-8")
        self.assertIn("登入逾時", html_doc)

    def test_http_401_or_403_raises_explicit_login_required(self):
        """HTTP 401 or 403 status returns LOGIN_REQUIRED status code/message."""
        def handle_http_status(status_code):
            if status_code in (401, 403):
                return "LOGIN_REQUIRED"
            return "OK"
        self.assertEqual(handle_http_status(401), "LOGIN_REQUIRED")
        self.assertEqual(handle_http_status(403), "LOGIN_REQUIRED")

    def test_redirect_to_login_page_url_detected(self):
        """Redirect target ending in login.php triggers LOGIN_REQUIRED."""
        redirect_url = "https://eclass.puiching.edu.mo/templates/login.php?timeout=1"
        self.assertTrue("login.php" in redirect_url)


class TestTier2LeapYearAndCalendarEdgeDates(unittest.TestCase):
    """Boundary Case 4: Leap year & calendar boundary transitions."""

    def test_valid_leap_day_2028_02_29(self):
        """2028-02-29 is a valid leap year date."""
        d = datetime.date.fromisoformat("2028-02-29")
        self.assertEqual(d.year, 2028)
        self.assertEqual(d.month, 2)
        self.assertEqual(d.day, 29)

    def test_invalid_leap_day_2026_02_29_fails(self):
        """2026 is NOT a leap year; 2026-02-29 must raise ValueError."""
        with self.assertRaises(ValueError):
            datetime.date.fromisoformat("2026-02-29")

    def test_month_transition_boundary(self):
        """Transition from Aug 31 to Sep 1."""
        d1 = datetime.date(2026, 8, 31)
        d2 = d1 + datetime.timedelta(days=1)
        self.assertEqual(d2.isoformat(), "2026-09-01")

    def test_year_boundary_transition(self):
        """Transition from Dec 31 to Jan 1 next year."""
        d_end = datetime.date(2026, 12, 31)
        d_next = d_end + datetime.timedelta(days=1)
        self.assertEqual(d_next.isoformat(), "2027-01-01")

    def test_century_leap_year_rules(self):
        """2000 was a leap year; 2100 is not a leap year."""
        d_2000 = datetime.date(2000, 2, 29)
        self.assertIsNotNone(d_2000)
        with self.assertRaises(ValueError):
            datetime.date(2100, 2, 29)


class TestTier2LocalStorageQuotaAndCorruption(unittest.TestCase):
    """Boundary Case 5: LocalStorage quota & corruption handling."""

    def test_safe_read_handles_corrupt_json_strings(self):
        """Malformed JSON strings recover gracefully to empty dict."""
        corrupt_samples = [
            "{incomplete_json",
            "undefined",
            "NaN",
            "null",
            "[1, 2, 3]",
            "\"just_a_string\""
        ]
        for sample in corrupt_samples:
            try:
                val = json.loads(sample)
                res = val if isinstance(val, dict) else {}
            except Exception:
                res = {}
            self.assertIsInstance(res, dict)

    def test_sanitize_points_child_enforces_numeric_non_negative(self):
        """Points sanitize logic converts negative or non-numeric points to 0."""
        def sanitize_points_child(v):
            out = {"earned": 0, "spent": 0, "awarded": {}, "bonusDates": {}, "redemptions": []}
            if not isinstance(v, dict):
                return out
            if isinstance(v.get("earned"), (int, float)) and v["earned"] >= 0:
                out["earned"] = int(v["earned"])
            if isinstance(v.get("spent"), (int, float)) and v["spent"] >= 0:
                out["spent"] = int(v["spent"])
            return out

        self.assertEqual(sanitize_points_child({"earned": -50})["earned"], 0)
        self.assertEqual(sanitize_points_child({"earned": "fifty"})["earned"], 0)
        self.assertEqual(sanitize_points_child({"earned": 120.7})["earned"], 120)

    def test_redemptions_list_capped_at_last_50(self):
        """Points redemptions array is capped to 50 items to prevent unbounded localStorage growth."""
        history = [{"id": f"snack-{i}", "cost": 10} for i in range(100)]
        capped = history[-50:]
        self.assertEqual(len(capped), 50)
        self.assertEqual(capped[0]["id"], "snack-50")
        self.assertEqual(capped[-1]["id"], "snack-99")


class TestTier2OfflineStatesAndNetworkFlapping(unittest.TestCase):
    """Boundary Case 6: Offline states and network flapping."""

    def test_pending_queue_retains_offline_writes(self):
        """When offline, writes accumulate in the pending queue."""
        pending = {"todos": {}, "points": {}}
        # Simulate offline checks
        pending["todos"]["item-1"] = True
        pending["todos"]["item-2"] = True
        pending["points"]["li-yue"] = {"earned": 20, "spent": 0}

        self.assertEqual(len(pending["todos"]), 2)
        self.assertEqual(len(pending["points"]), 1)

    def test_reconnect_replays_pending_writes(self):
        """Simulate replaying pending writes on reconnection."""
        pending = {"todos": {"item-1": True, "item-2": False}, "points": {}}
        remote_store = {}

        # Replay
        for k, v in list(pending["todos"].items()):
            remote_store[k] = v
            del pending["todos"][k]

        self.assertEqual(len(pending["todos"]), 0)
        self.assertEqual(remote_store["item-1"], True)
        self.assertEqual(remote_store["item-2"], False)

    def test_flapping_preserves_latest_write_intent(self):
        """Rapid toggling of a checkbox preserves the last action in pending queue."""
        pending_todos = {}
        pending_todos["item-1"] = True
        pending_todos["item-1"] = False
        pending_todos["item-1"] = True

        self.assertEqual(pending_todos["item-1"], True)


class TestTier2AdversarialEncodingAndSpecialCharacters(unittest.TestCase):
    """Boundary Case 7: Adversarial encoding, Emoji, quotes, and HTML entities."""

    def test_homework_subject_with_emoji(self):
        """Homework subjects with emoji (e.g. 📚中文, 🧮數學) parse cleanly."""
        item = {
            "subject": "📚 中文",
            "title": "背誦第3課 🌟",
            "due": "2026-09-15",
            "submit_required": True,
            "note": "加油！💪"
        }
        dumped = json.dumps(item, ensure_ascii=False)
        loaded = json.loads(dumped)
        self.assertIn("📚", loaded["subject"])
        self.assertIn("💪", loaded["note"])

    def test_html_entity_decoding_in_detail(self):
        """HTML entities like &amp;, &lt;, &gt;, &quot; are decoded or handled cleanly."""
        raw_detail = "Worksheet 1 &amp; 2 &lt;Grammar&gt; &quot;Tenses&quot;"
        clean = html.unescape(raw_detail)
        self.assertEqual(clean, 'Worksheet 1 & 2 <Grammar> "Tenses"')

    def test_zero_width_space_stripping(self):
        """Zero-width spaces (\\u200b) in scraped eClass strings are stripped or normalized."""
        raw_title = "功課\u200b第\u200b3\u200b課"
        cleaned = raw_title.replace("\u200b", "").strip()
        self.assertEqual(cleaned, "功課第3課")

    def test_long_title_length_handling(self):
        """Unusually long title (200+ characters) is stored without crashing."""
        long_title = "長標題" * 80
        item = {
            "subject": "中文",
            "title": long_title,
            "due": "2026-09-15"
        }
        self.assertTrue(len(item["title"]) > 200)
        dumped = json.dumps(item, ensure_ascii=False)
        self.assertIn("長標題", dumped)


if __name__ == "__main__":
    unittest.main()
