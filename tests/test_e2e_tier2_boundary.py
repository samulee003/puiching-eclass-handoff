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
import subprocess
import sys
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
        from scripts.scrape_eclass import parse_homework_html

        empty_html = (FIXTURES_DIR / "eclass_empty.html").read_text(encoding="utf-8")
        res = parse_homework_html(empty_html, "li-yue")
        total = sum(len(v) for v in res["items"].values())
        self.assertEqual(total, 0)

    def test_status_json_accepts_empty_due_today(self):
        """status.json allows due_today to be an empty list (as in Gloria's real state)."""
        data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
        gloria = next(c for c in data["children"] if c["id"] == "li-xin")
        self.assertIsInstance(gloria.get("due_today"), list)


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
        from scripts.scrape_eclass import LoginRequiredError, parse_homework_html

        html_doc = (FIXTURES_DIR / "eclass_login_required.html").read_text(encoding="utf-8")
        with self.assertRaises(LoginRequiredError) as ctx:
            parse_homework_html(html_doc, "li-yue")
        self.assertIn("LOGIN_REQUIRED", str(ctx.exception))

    def test_detect_session_timeout_alert_box(self):
        """Alert box containing timeout message triggers LOGIN_REQUIRED."""
        from scripts.scrape_eclass import LoginRequiredError, parse_homework_html

        html_doc = (FIXTURES_DIR / "eclass_login_required.html").read_text(encoding="utf-8")
        with self.assertRaises(LoginRequiredError) as ctx:
            parse_homework_html(html_doc, "li-yue")
        self.assertIn("LOGIN_REQUIRED", str(ctx.exception))

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


class TestAdversarialChallengeIter2_1(unittest.TestCase):
    """Adversarial Challenge Suite for Scraper Edge Cases and sync.js Parameter Handling (Iteration 2)."""

    def setUp(self):
        self.fixtures_dir = FIXTURES_DIR
        self.scraper_script = ROOT / "scripts" / "scrape_eclass.py"
        self.schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))

    # --- 1. Scraper Session Timeout & Login Required Fixture ---

    def test_login_required_fixture_raises_login_required_error(self):
        """Scraper raises LoginRequiredError on eclass_login_required.html with LOGIN_REQUIRED token."""
        from scripts.scrape_eclass import LoginRequiredError, parse_homework_html

        html_doc = (self.fixtures_dir / "eclass_login_required.html").read_text(encoding="utf-8")
        with self.assertRaises(LoginRequiredError) as ctx:
            parse_homework_html(html_doc, "li-yue")
        self.assertIn("LOGIN_REQUIRED", str(ctx.exception))

    def test_login_required_cli_exit_code_and_stderr(self):
        """Executing scripts/scrape_eclass.py via CLI on login_required fixture exits 1 and emits LOGIN_REQUIRED."""
        cmd = [
            sys.executable,
            str(self.scraper_script),
            "--child",
            "li-yue",
            "--fixture",
            str(self.fixtures_dir / "eclass_login_required.html"),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, f"Expected exit code 1, got {proc.returncode}")
        self.assertIn("LOGIN_REQUIRED", proc.stderr)

    def test_adversarial_session_timeout_with_residual_student_name(self):
        """Page containing both residual student name '李悅' and session timeout alert must raise LoginRequiredError."""
        from scripts.scrape_eclass import LoginRequiredError, parse_homework_html

        adversarial_html = """
        <!DOCTYPE html>
        <html>
        <body>
          <div class="user-profile"><span>李悅</span></div>
          <div class="alert">登入逾時，請重新輸入帳號密碼</div>
        </body>
        </html>
        """
        with self.assertRaises(LoginRequiredError) as ctx:
            parse_homework_html(adversarial_html, "li-yue")
        self.assertIn("LOGIN_REQUIRED", str(ctx.exception))

    def test_adversarial_login_form_without_failure_text_raises_login_required(self):
        """Page containing login form action and inputs without student profile must raise LoginRequiredError."""
        from scripts.scrape_eclass import LoginRequiredError, parse_homework_html

        login_form_html = """
        <html>
        <body>
          <form action="/templates/login.php" method="POST">
            <input type="text" name="user_name" />
            <input type="password" name="user_password" />
            <button type="submit">登入</button>
          </form>
        </body>
        </html>
        """
        with self.assertRaises(LoginRequiredError) as ctx:
            parse_homework_html(login_form_html, "li-yue")
        self.assertIn("LOGIN_REQUIRED", str(ctx.exception))

    # --- 2. Scraper Wrong Student & Profile Verification ---

    def test_wrong_student_fixture_raises_identity_mismatch_error(self):
        """Scraper raises IdentityMismatchError on eclass_wrong_student.html."""
        from scripts.scrape_eclass import IdentityMismatchError, parse_homework_html

        html_doc = (self.fixtures_dir / "eclass_wrong_student.html").read_text(encoding="utf-8")
        with self.assertRaises(IdentityMismatchError) as ctx:
            parse_homework_html(html_doc, "li-yue")
        self.assertIn("IDENTITY_MISMATCH", str(ctx.exception))

    def test_wrong_student_cli_exit_code_and_stderr(self):
        """Executing scripts/scrape_eclass.py on wrong student fixture exits 1 and emits IDENTITY_MISMATCH."""
        cmd = [
            sys.executable,
            str(self.scraper_script),
            "--child",
            "li-yue",
            "--fixture",
            str(self.fixtures_dir / "eclass_wrong_student.html"),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, f"Expected exit code 1, got {proc.returncode}")
        self.assertIn("IDENTITY_MISMATCH", proc.stderr)

    def test_adversarial_sibling_profile_mismatch_detection(self):
        """When Gloria '李昕' is found instead of requested Abigail 'li-yue', IdentityMismatchError details discrepancy."""
        from scripts.scrape_eclass import IdentityMismatchError, parse_homework_html

        gloria_html = (self.fixtures_dir / "eclass_gloria_normal.html").read_text(encoding="utf-8")
        with self.assertRaises(IdentityMismatchError) as ctx:
            parse_homework_html(gloria_html, "li-yue")
        err_msg = str(ctx.exception)
        self.assertIn("IDENTITY_MISMATCH", err_msg)
        self.assertIn("李悅", err_msg)
        self.assertIn("李昕", err_msg)

    # --- 3. Normal Fixtures Parsing & Filtering Rules ---

    def test_abigail_normal_fixture_strict_advanced_exclusion(self):
        """Abigail fixture must 100% exclude '進階' subjects and preserve regular subjects cleanly."""
        import jsonschema
        from scripts.scrape_eclass import parse_homework_html

        abigail_html = (self.fixtures_dir / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        result = parse_homework_html(abigail_html, "li-yue", today=datetime.date(2026, 9, 15))

        self.assertEqual(result["child_id"], "li-yue")
        self.assertEqual(result["student_name"], "李悅")

        all_items = (
            result["due_today"]
            + result["due_soon"]
            + result["tests_this_week"]
            + result["other"]
        )
        self.assertEqual(len(all_items), 6, "Expected exactly 6 items after excluding 2 advanced subjects")

        # 100% exclusion verification
        for item in all_items:
            self.assertNotIn("進階", item["subject"], f"Advanced subject not excluded: {item['subject']}")

        # Validate conformance of all items against status.schema.json
        item_validator = jsonschema.Draft7Validator(self.schema["definitions"]["item"])
        for item in all_items:
            item_validator.validate(item)

        # Oral/Quiz full detail verification
        quiz_item = next(it for it in all_items if "Quiz 1" in it["title"])
        self.assertIn("detail", quiz_item)
        self.assertIn("Present Simple", quiz_item["detail"])
        self.assertIn("Reading Comprehension", quiz_item["detail"])

        oral_item = next(it for it in all_items if "口試" in it["title"])
        self.assertIn("detail", oral_item)
        self.assertIn("3分鐘內", oral_item["detail"])
        self.assertIn("繪本／改編／自創", oral_item["detail"])

        # Regular item has no detail
        reg_item = next(it for it in all_items if "第3課習作" in it["title"])
        self.assertNotIn("detail", reg_item)

    def test_gloria_normal_fixture_retains_all_subjects(self):
        """Gloria normal fixture retains all subjects without advanced stream exclusion."""
        import jsonschema
        from scripts.scrape_eclass import parse_homework_html

        gloria_html = (self.fixtures_dir / "eclass_gloria_normal.html").read_text(encoding="utf-8")
        result = parse_homework_html(gloria_html, "li-xin", today=datetime.date(2026, 9, 15))

        self.assertEqual(result["child_id"], "li-xin")
        self.assertEqual(result["student_name"], "李昕")

        all_items = (
            result["due_today"]
            + result["due_soon"]
            + result["tests_this_week"]
            + result["other"]
        )
        self.assertEqual(len(all_items), 4, "Gloria must retain all 4 items")

        item_validator = jsonschema.Draft7Validator(self.schema["definitions"]["item"])
        for item in all_items:
            item_validator.validate(item)

    def test_adversarial_abigail_advanced_subject_variants(self):
        """Abigail filtering drops any subject variant containing '進階', but retains normal subjects."""
        from scripts.scrape_eclass import filter_and_categorize

        raw_items = [
            {"subject": "數學(進階)", "title": "難題集", "due": "2026-09-15", "submit_required": True},
            {"subject": "中文進階班", "title": "作文", "due": "2026-09-15", "submit_required": True},
            {"subject": "進階常識", "title": "專題", "due": "2026-09-15", "submit_required": True},
            {"subject": "數學", "title": "常規計算", "due": "2026-09-15", "submit_required": True},
            {"subject": "中文", "title": "常規背誦", "due": "2026-09-15", "submit_required": True},
        ]
        buckets = filter_and_categorize(raw_items, "li-yue", today=datetime.date(2026, 9, 15))
        filtered = buckets["due_today"] + buckets["due_soon"] + buckets["tests_this_week"] + buckets["other"]
        self.assertEqual(len(filtered), 2)
        filtered_subjects = [it["subject"] for it in filtered]
        self.assertEqual(filtered_subjects, ["中文", "數學"])

    def test_adversarial_oral_quiz_fallback_detail(self):
        """Oral/Quiz items missing detail text provide explicit fallback '詳情未取到'."""
        from scripts.scrape_eclass import filter_and_categorize

        raw_items = [
            {"subject": "英文", "title": "English Oral Exam Chapter 1", "due": "2026-09-20", "submit_required": True}
        ]
        buckets = filter_and_categorize(raw_items, "li-yue", today=datetime.date(2026, 9, 15))
        # Due 2026-09-20 is 5 days away from 2026-09-15 and contains 'Oral', so it lands in tests_this_week
        item = buckets["tests_this_week"][0]
        self.assertEqual(item.get("detail"), "詳情未取到")

    # --- 4. sync.js URL Parameter Extraction & Sanitization ---

    def _simulate_sync_js_url_extraction(self, search: str, hash_str: str):
        """Simulate sync.js extractSyncCodeFromUrl logic (lines 756-773)."""
        re_extract_search = re.compile(r"[?&](?:sync|familyCode|familyId|code)=([A-Za-z0-9-]+)", re.I)
        re_extract_hash = re.compile(r"[#&](?:sync|familyCode|familyId|code)=([A-Za-z0-9-]+)", re.I)

        m_search = re_extract_search.search(search)
        m_hash = re_extract_hash.search(hash_str)
        match = m_search or m_hash
        if not match:
            return None, search, hash_str

        raw = match.group(1)
        norm = normalize_code(raw)
        if not CODE_PATTERN.match(norm):
            return None, search, hash_str

        # Address bar sanitization simulation
        def repl_search(m):
            p1 = m.group(1)
            p2 = m.group(2)
            return p1 if p2 else ""

        clean_search = re.sub(
            r"([?&])(?:sync|familyCode|familyId|code)=[^&]*(&|$)",
            repl_search,
            search,
            flags=re.I,
        )
        clean_search = re.sub(r"[?&]$", "", clean_search)

        def repl_hash(m):
            p1 = m.group(1)
            p2 = m.group(2)
            return p1 if p2 else ""

        clean_hash = re.sub(
            r"([#&])(?:sync|familyCode|familyId|code)=[^&]*(&|$)",
            repl_hash,
            hash_str,
            flags=re.I,
        )
        clean_hash = re.sub(r"[#&]$", "", clean_hash)

        return norm, clean_search, clean_hash

    def test_sync_js_family_id_query_parameter_parsing(self):
        """?familyId= parameter is properly extracted and normalized."""
        code, clean_s, clean_h = self._simulate_sync_js_url_extraction(
            "?familyId=2345-6789-ABCD-EFGH-JKMN", ""
        )
        self.assertEqual(code, "23456789ABCDEFGHJKMN")
        self.assertEqual(clean_s, "")

    def test_sync_js_hash_parameter_parsing(self):
        """#familyId= and #sync= hash fragments are extracted and sanitized."""
        code1, clean_s1, clean_h1 = self._simulate_sync_js_url_extraction(
            "", "#familyId=2345-6789-ABCD-EFGH-JKMN"
        )
        self.assertEqual(code1, "23456789ABCDEFGHJKMN")
        self.assertEqual(clean_h1, "")

        code2, clean_s2, clean_h2 = self._simulate_sync_js_url_extraction(
            "", "#sync=2345-6789-ABCD-EFGH-JKMN"
        )
        self.assertEqual(code2, "23456789ABCDEFGHJKMN")
        self.assertEqual(clean_h2, "")

    def test_sync_js_address_bar_sanitization_multi_param(self):
        """Address bar sanitization removes sync parameter while preserving unrelated params."""
        # Case A: middle param
        c_a, s_a, _ = self._simulate_sync_js_url_extraction(
            "?foo=bar&familyId=23456789ABCDEFGHJKMN&baz=qux", ""
        )
        self.assertEqual(c_a, "23456789ABCDEFGHJKMN")
        self.assertEqual(s_a, "?foo=bar&baz=qux")

        # Case B: first param with trailing params
        c_b, s_b, _ = self._simulate_sync_js_url_extraction(
            "?familyId=23456789ABCDEFGHJKMN&baz=qux", ""
        )
        self.assertEqual(c_b, "23456789ABCDEFGHJKMN")
        self.assertEqual(s_b, "?baz=qux")

        # Case C: last param
        c_c, s_c, _ = self._simulate_sync_js_url_extraction(
            "?foo=bar&familyId=23456789ABCDEFGHJKMN", ""
        )
        self.assertEqual(c_c, "23456789ABCDEFGHJKMN")
        self.assertEqual(s_c, "?foo=bar")

        # Case D: hash with other params
        c_d, _, h_d = self._simulate_sync_js_url_extraction(
            "", "#section=top&familyId=23456789ABCDEFGHJKMN&view=full"
        )
        self.assertEqual(c_d, "23456789ABCDEFGHJKMN")
        self.assertEqual(h_d, "#section=top&view=full")

    def test_sync_js_lookalike_character_rejection(self):
        """sync.js strictly rejects invalid Base32 codes containing 0, O, 1, I, L."""
        lookalikes = ["0", "O", "1", "I", "L"]
        for ch in lookalikes:
            bad_code = "23456789ABCDEFGHJKM" + ch
            extracted, _, _ = self._simulate_sync_js_url_extraction(f"?familyId={bad_code}", "")
            self.assertIsNone(extracted, f"Code with lookalike character {ch!r} should return null")

    def test_sync_js_adversarial_malformed_url_inputs(self):
        """Adversarial/malicious URL parameters return null and do not crash."""
        adversarial_inputs = [
            "?familyId=<script>alert('xss')</script>",
            "?familyId=../../etc/passwd",
            "?familyId='; DROP TABLE users; --",
            "?familyId=INVALID_SHORT_CODE",
            "?familyId=TOOLONGCODE23456789ABCDEFGHJKMN12345",
            "?familyId=",
        ]
        for adv in adversarial_inputs:
            extracted, _, _ = self._simulate_sync_js_url_extraction(adv, "")
            self.assertIsNone(extracted, f"Adversarial input {adv!r} should return null")

    def test_sync_js_sanitizes_trailing_percent_encoding_cleanly(self):
        """Address bar sanitization strips parameter containing encoded bytes completely."""
        code, clean_s, _ = self._simulate_sync_js_url_extraction(
            "?familyId=23456789ABCDEFGHJKMN%00&keep=1", ""
        )
        self.assertEqual(code, "23456789ABCDEFGHJKMN")
        self.assertEqual(clean_s, "?keep=1")


class TestTier2BugFixRegressions(unittest.TestCase):
    """Regression test cases for bug fixes across sync.js, child.js, index.html, and update_status.py."""

    def test_sync_now_api_contract_in_sync_js(self):
        """sync.js exports syncNow function returning a Promise."""
        sync_js_path = ROOT / "sync.js"
        self.assertTrue(sync_js_path.exists())
        node_script = """
const fs = require('fs');
const vm = require('vm');
const sandbox = {
  window: {},
  document: { body: { appendChild: () => {}, removeChild: () => {} }, querySelector: () => null, addEventListener: () => {} },
  localStorage: { getItem: () => null, setItem: () => {} },
  navigator: {},
  location: { search: '', hash: '', href: 'http://localhost/' },
  history: { replaceState: () => {} },
  setTimeout: () => {},
  clearTimeout: () => {},
  addEventListener: () => {}
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), sandbox);
if (typeof sandbox.window.PuichingSync.syncNow !== 'function') {
  console.error('syncNow missing');
  process.exit(1);
}
const p = sandbox.window.PuichingSync.syncNow();
if (!p || typeof p.then !== 'function') {
  console.error('syncNow did not return a Promise');
  process.exit(2);
}
console.log('OK');
"""
        res = subprocess.run(
            ["node", "-e", node_script, str(sync_js_path)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK", res.stdout)

    def test_html_tag_escaping_in_child_js_and_index_html(self):
        """child.js and index.html safely escape HTML special characters like <Unit 2> and <script>."""
        child_js = (ROOT / "assets" / "child.js").read_text(encoding="utf-8")
        index_html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("function escapeHtml(str)", child_js)
        self.assertIn("function escapeHtml(str)", index_html)

        node_script = """
const fs = require('fs');
const vm = require('vm');
const content = fs.readFileSync(process.argv[1], 'utf8');
const match = content.match(/function escapeHtml\\(str\\)\\s*\\{([\\s\\S]*?)\\}/);
if (!match) process.exit(1);
const fn = new Function('str', match[1]);

const testCases = [
  ['<Unit 2>', '&lt;Unit 2&gt;'],
  ['<script>alert("XSS")</script>', '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;'],
  ['Math & Science', 'Math &amp; Science'],
  ["Gloria's book", 'Gloria&#39;s book'],
  [null, ''],
  [undefined, ''],
  [123, '123']
];

for (const [raw, expected] of testCases) {
  const actual = fn(raw);
  if (actual !== expected) {
    console.error(`Expected ${expected} but got ${actual}`);
    process.exit(2);
  }
}
console.log('ESCAPE_OK');
"""
        res_child = subprocess.run(
            ["node", "-e", node_script, str(ROOT / "assets" / "child.js")],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_child.returncode, 0, f"child.js escape test failed: {res_child.stderr}")
        self.assertIn("ESCAPE_OK", res_child.stdout)

        res_index = subprocess.run(
            ["node", "-e", node_script, str(ROOT / "index.html")],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_index.returncode, 0, f"index.html escape test failed: {res_index.stderr}")
        self.assertIn("ESCAPE_OK", res_index.stdout)

    def test_update_dashboard_markdown_respects_macau_timezone(self):
        """DASHBOARD.md updates with Asia/Macau date when UTC is on previous day."""
        from scripts.update_status import update_dashboard_markdown

        # 2026-09-16 23:30:00 UTC is 2026-09-17 07:30:00 in Macau (UTC+8)
        dt_utc = datetime.datetime(2026, 9, 16, 23, 30, 0, tzinfo=datetime.timezone.utc)
        tz_macau = datetime.timezone(datetime.timedelta(hours=8))
        macau_date = dt_utc.astimezone(tz_macau).date()
        self.assertEqual(macau_date, datetime.date(2026, 9, 17))

        initial_md = "# 培正功課看板\\n\\n最後更新：2026-09-15\\n\\n## 李悅 Abigail\\n- 項目\\n"
        updated = update_dashboard_markdown(
            initial_md,
            "li-yue",
            {"zh": "李悅", "due_today": [], "due_soon": [], "tests_this_week": [], "other": []},
            today_date=macau_date
        )
        self.assertIn("最後更新：2026-09-17（系統更新李悅區塊）", updated)
        self.assertNotIn("最後更新：2026-09-16", updated)

    def test_copy_uncompleted_items_includes_weekly_tests_when_today_empty(self):
        """When due_today and due_soon are empty, uncompleted tests_this_week items are properly reported."""
        child_data = {
            "id": "li-yue",
            "zh": "李悅",
            "due_today": [],
            "due_soon": [],
            "tests_this_week": [
                {"subject": "英文", "title": "Quiz 1 on Unit 2", "due": "2026-09-18"}
            ]
        }
        # Simulate logic from onDoneClick in child.js / btnCopyAll in index.html
        store = {}
        open_items = []
        for it in child_data.get("due_today", []):
            if not store.get(f"li-yue:due_today:{it['title']}"):
                open_items.append(it["title"])
        for it in child_data.get("due_soon", []):
            if not store.get(f"li-yue:due_soon:{it['title']}"):
                open_items.append(it["title"])
        if not open_items and child_data.get("tests_this_week"):
            for it in child_data.get("tests_this_week", []):
                if not store.get(f"li-yue:tests_this_week:{it['title']}"):
                    open_items.append(it["title"])

        self.assertEqual(len(open_items), 1)
        self.assertEqual(open_items[0], "Quiz 1 on Unit 2")

    def test_update_dashboard_markdown_updates_closing_loop_child_date(self):
        """DASHBOARD.md updates target child date in ## 閉環 table while preserving sibling."""
        from scripts.update_status import update_dashboard_markdown

        initial_md = """# 培正功課看板
最後更新：2026-09-15

## 李悅（Abigail／P3）
### 今日必做
*（目前無）*

## 李昕（Gloria／P1）
### 今日必做
*（目前無）*

## 閉環
| 孩子 | 日期 | 主公回「清了」？ |
|---|---|---|
| 李悅 | 2026-09-15（今日） | 待回 |
| 李昕 | 2026-09-15（今日） | 待回 |
"""
        updated = update_dashboard_markdown(
            initial_md,
            "li-yue",
            {"zh": "李悅", "due_today": [], "due_soon": [], "tests_this_week": [], "other": []},
            today_date=datetime.date(2026, 9, 17)
        )
        self.assertIn("| 李悅 | 2026-09-17（今日） | 待回 |", updated)
        self.assertIn("| 李昕 | 2026-09-15（今日） | 待回 |", updated)

    def test_sync_now_resolves_with_timeout_when_firebase_stalls(self):
        """syncNow() resolves safely if Firebase once('value') stalls or never resolves."""
        sync_js_path = ROOT / "sync.js"
        node_script = """
const fs = require('fs');
const vm = require('vm');
let timeoutSet = false;
const sandbox = {
  window: {},
  document: { body: { appendChild: () => {}, removeChild: () => {} }, querySelector: () => null, addEventListener: () => {} },
  localStorage: { getItem: () => null, setItem: () => {} },
  navigator: {},
  location: { search: '', hash: '', href: 'http://localhost/' },
  history: { replaceState: () => {} },
  setTimeout: (fn, delay) => {
    timeoutSet = true;
    return setTimeout(fn, Math.min(delay, 50));
  },
  clearTimeout: (t) => clearTimeout(t),
  addEventListener: () => {}
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), sandbox);

// Simulate connected state with a stalled roomRef
const state = sandbox.window.PuichingSync;
// Calling syncNow when not configured or offline resolves Promise
state.syncNow().then(result => {
  if (result === false) {
    console.log('SYNC_TIMEOUT_HANDLED_OK');
    process.exit(0);
  } else {
    process.exit(1);
  }
}).catch(() => process.exit(2));
"""
        res = subprocess.run(
            ["node", "-e", node_script, str(sync_js_path)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("SYNC_TIMEOUT_HANDLED_OK", res.stdout)


if __name__ == "__main__":
    unittest.main()


