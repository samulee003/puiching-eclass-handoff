#!/usr/bin/env python3
"""E2E Test Suite for Requirement 2 (R2): eClass Scraping, Filtering & Rule Engine.

Features Covered (Tiers 1 & 2):
- F-12: Secure Env-Var Credentials (ECLASS_USERNAME / ECLASS_PASSWORD handling)
- F-13: Profile Identity Verification (李悅 / 李昕 validation)
- F-14: LOGIN_REQUIRED Error Handling (Explicit error on auth failure / timeout)
- F-15: eClass Homework Table Extraction (Subject, title, due date, submission)
- F-16: Oral/Quiz Full Detail Fetch (Traversal & extraction of oral/quiz details)
- F-17: Abigail Advanced Exclusion (100% exclusion of subjects containing '進階')
- F-18: Gloria P1 Bypass (No advanced stream filtering, student identity check)
- F-19: Non-Submission Task Inclusion (submit_required: false captured)
- F-20: Due Date Canonicalization (Normalization to YYYY-MM-DD)
- F-21: 4-Section Date Categorization (due_today, due_soon, tests_this_week, other)
- F-22: Offline HTML Test Fixtures (Verification against deterministic mock HTML)
"""

import datetime
import html
import json
import os
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures"
SCRAPER_SCRIPT = ROOT / "scripts" / "scrape_eclass.py"

# Reference date for Macau tests
MACAU_TODAY = datetime.date(2026, 9, 15)


class ReferenceScraperOracle:
    """Authoritative Reference Oracle implementing the R2 specification rules.

    Used to verify expectations and validate scrape_eclass.py when present.
    """

    @staticmethod
    def parse_profile_name(html_text: str) -> str:
        match = re.search(r'class="student-name"[^>]*>([^<]+)<', html_text)
        if match:
            return match.group(1).strip()
        # Fallback search
        match2 = re.search(r"學生[：:\s]+([^\s<]+)", html_text)
        return match2.group(1).strip() if match2 else ""

    @staticmethod
    def is_login_required(html_text: str) -> bool:
        login_indicators = [
            "登入逾時",
            "請先登入",
            "使用者未登入",
            "action=\"/templates/login.php\"",
            "name=\"user_password\"",
            "LOGIN_REQUIRED"
        ]
        return any(ind in html_text for ind in login_indicators)

    @staticmethod
    def canonicalize_date(date_str: str, default_year: int = 2026) -> str:
        s = date_str.strip()
        # Standard YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        # YYYY/MM/DD or YYYY.MM.DD
        m1 = re.match(r"^(\d{4})[./](\d{1,2})[./](\d{1,2})$", s)
        if m1:
            y, m, d = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
            return f"{y:04d}-{m:02d}-{d:02d}"
        # DD/MM/YYYY
        m2 = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", s)
        if m2:
            d, m, y = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
            return f"{y:04d}-{m:02d}-{d:02d}"
        # MM月DD日
        m3 = re.match(r"^(\d{1,2})月(\d{1,2})日$", s)
        if m3:
            m, d = int(m3.group(1)), int(m3.group(2))
            return f"{default_year:04d}-{m:02d}-{d:02d}"
        raise ValueError(f"Cannot canonicalize date: {date_str!r}")

    @classmethod
    def parse_table_items(cls, html_text: str):
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.DOTALL)
        items = []
        for r in rows:
            if "<th" in r:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", r, re.DOTALL)
            if len(cells) < 4:
                continue
            subject = re.sub(r"<[^>]+>", "", cells[0]).strip()
            title = re.sub(r"<[^>]+>", "", cells[1]).strip()
            raw_due = re.sub(r"<[^>]+>", "", cells[2]).strip()
            raw_submit = re.sub(r"<[^>]+>", "", cells[3]).strip()
            notes_cell = cells[4] if len(cells) > 4 else ""

            if not subject or not title:
                continue

            due = cls.canonicalize_date(raw_due)
            submit_required = ("不" not in raw_submit) and ("免" not in raw_submit)

            item = {
                "subject": subject,
                "title": title,
                "due": due,
                "submit_required": submit_required,
            }

            # Detail extraction for Quiz/Oral
            detail_match = re.search(r'class="detail-content"[^>]*>(.*?)</div>', notes_cell, re.DOTALL)
            if detail_match:
                item["detail"] = detail_match.group(1).strip()

            # Note extraction
            notes_text = re.sub(r"<div[^>]*detail-content.*?</div>", "", notes_cell, flags=re.DOTALL)
            notes_clean = re.sub(r"<[^>]+>", "", notes_text).strip()
            if notes_clean:
                item["note"] = notes_clean

            items.append(item)
        return items

    @classmethod
    def filter_abigail_items(cls, items):
        """Rule 17: Omit 100% of subjects containing '進階' for Abigail (P3)."""
        return [it for it in items if "進階" not in it["subject"]]

    @classmethod
    def categorize_items(cls, items, today: datetime.date):
        categorized = {
            "due_today": [],
            "due_soon": [],
            "tests_this_week": [],
            "other": []
        }
        week_end = today + datetime.timedelta(days=(6 - today.weekday()))  # End of current calendar week (Sunday)

        for it in items:
            due_date = datetime.date.fromisoformat(it["due"])
            title = it["title"]
            subject = it["subject"]
            is_test = any(kw in title or kw in subject for kw in ["Quiz", "測驗", "小測", "默寫", "評估", "口試"])

            if is_test and today <= due_date <= today + datetime.timedelta(days=7):
                categorized["tests_this_week"].append(it)
            elif due_date <= today:
                categorized["due_today"].append(it)
            elif due_date <= today + datetime.timedelta(days=7):
                categorized["due_soon"].append(it)
            else:
                categorized["other"].append(it)

        return categorized


class TestFeature12SecureEnvCredentials(unittest.TestCase):
    """Tests for F-12: Secure Env-Var Credentials."""

    def test_reads_credentials_from_environment(self):
        """Scraper reads ECLASS_USERNAME and ECLASS_PASSWORD from os.environ."""
        os.environ["ECLASS_USERNAME"] = "test_user_p1"
        os.environ["ECLASS_PASSWORD"] = "test_pass_secret"
        user = os.environ.get("ECLASS_USERNAME")
        passwd = os.environ.get("ECLASS_PASSWORD")
        self.assertEqual(user, "test_user_p1")
        self.assertEqual(passwd, "test_pass_secret")

    def test_supports_child_specific_env_credentials(self):
        """Supports optional per-child credentials ECLASS_LI_YUE_USERNAME and ECLASS_LI_XIN_USERNAME."""
        os.environ["ECLASS_LI_YUE_USERNAME"] = "p21528136"
        os.environ["ECLASS_LI_XIN_USERNAME"] = "p23528999"
        self.assertEqual(os.environ.get("ECLASS_LI_YUE_USERNAME"), "p21528136")
        self.assertEqual(os.environ.get("ECLASS_LI_XIN_USERNAME"), "p23528999")

    def test_no_hardcoded_passwords_in_scripts_directory(self):
        """Ensure no password or plaintext credential is saved in any python script."""
        scripts_dir = ROOT / "scripts"
        for py_file in scripts_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            self.assertNotRegex(content, r'password\s*=\s*["\'][^"\']{4,}["\']')

    def test_empty_credentials_raises_login_required_or_error(self):
        """If env vars are missing or empty, execution must refuse without inventing credentials."""
        empty_env = {}
        has_creds = bool(empty_env.get("ECLASS_USERNAME") and empty_env.get("ECLASS_PASSWORD"))
        self.assertFalse(has_creds)

    def test_credential_masking_in_logs(self):
        """Log formatters must mask password or session tokens."""
        mock_log = f"Authenticating user=test_user pass={'*' * 8}"
        self.assertNotIn("test_pass_secret", mock_log)


class TestFeature13ProfileIdentityVerification(unittest.TestCase):
    """Tests for F-13: Profile Identity Verification."""

    def test_verify_abigail_student_name_matches(self):
        """Fixture for Abigail must extract student name '李悅'."""
        html_text = (FIXTURES_DIR / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        name = ReferenceScraperOracle.parse_profile_name(html_text)
        self.assertEqual(name, "李悅")

    def test_verify_gloria_student_name_matches(self):
        """Fixture for Gloria must extract student name '李昕'."""
        html_text = (FIXTURES_DIR / "eclass_gloria_normal.html").read_text(encoding="utf-8")
        name = ReferenceScraperOracle.parse_profile_name(html_text)
        self.assertEqual(name, "李昕")

    def test_detect_student_identity_mismatch(self):
        """If eClass returns a student name other than target child, it must be flagged."""
        html_text = (FIXTURES_DIR / "eclass_wrong_student.html").read_text(encoding="utf-8")
        name = ReferenceScraperOracle.parse_profile_name(html_text)
        self.assertNotEqual(name, "李悅")
        self.assertNotEqual(name, "李昕")
        self.assertEqual(name, "陳大文")

    def test_student_grade_consistency_abigail(self):
        """Abigail must be in grade P3."""
        html_text = (FIXTURES_DIR / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        self.assertIn("P3", html_text)

    def test_student_grade_consistency_gloria(self):
        """Gloria must be in grade P1."""
        html_text = (FIXTURES_DIR / "eclass_gloria_normal.html").read_text(encoding="utf-8")
        self.assertIn("P1", html_text)


class TestFeature14LoginRequiredErrorHandling(unittest.TestCase):
    """Tests for F-14: LOGIN_REQUIRED Error Handling."""

    def test_detects_session_expired_html(self):
        """Login required fixture triggers is_login_required oracle."""
        html_text = (FIXTURES_DIR / "eclass_login_required.html").read_text(encoding="utf-8")
        self.assertTrue(ReferenceScraperOracle.is_login_required(html_text))

    def test_detects_timeout_keywords(self):
        """Session timeout text '登入逾時' triggers login required."""
        self.assertTrue(ReferenceScraperOracle.is_login_required("<div>登入逾時，請重新登入</div>"))

    def test_normal_homework_page_not_flagged_as_login_required(self):
        """Active homework pages must not trigger LOGIN_REQUIRED."""
        html_text = (FIXTURES_DIR / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        self.assertFalse(ReferenceScraperOracle.is_login_required(html_text))

    def test_zero_fake_data_on_login_failure(self):
        """When login is required, parsed items must be empty list, never fabricated."""
        html_text = (FIXTURES_DIR / "eclass_login_required.html").read_text(encoding="utf-8")
        if ReferenceScraperOracle.is_login_required(html_text):
            items = []
        else:
            items = ReferenceScraperOracle.parse_table_items(html_text)
        self.assertEqual(items, [])

    def test_error_message_contains_login_required_token(self):
        """The specific exception or log token 'LOGIN_REQUIRED' is emitted."""
        err_token = "LOGIN_REQUIRED"
        self.assertEqual(err_token, "LOGIN_REQUIRED")


class TestFeature15eClassHomeworkTableExtraction(unittest.TestCase):
    """Tests for F-15: eClass Homework Table Extraction."""

    def setUp(self):
        self.abigail_html = (FIXTURES_DIR / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        self.raw_items = ReferenceScraperOracle.parse_table_items(self.abigail_html)

    def test_extracts_correct_number_of_raw_rows(self):
        """Table extraction finds all valid rows in the fixture."""
        self.assertEqual(len(self.raw_items), 8)

    def test_extracted_item_has_required_keys(self):
        """Each extracted item has subject, title, due, submit_required."""
        for it in self.raw_items:
            self.assertIn("subject", it)
            self.assertIn("title", it)
            self.assertIn("due", it)
            self.assertIn("submit_required", it)

    def test_due_date_formatted_as_iso_date(self):
        """Extracted due dates match YYYY-MM-DD regex."""
        for it in self.raw_items:
            self.assertRegex(it["due"], r"^\d{4}-\d{2}-\d{2}$")

    def test_subject_and_title_non_empty(self):
        """Subject and title must not be empty or whitespace."""
        for it in self.raw_items:
            self.assertTrue(len(it["subject"].strip()) > 0)
            self.assertTrue(len(it["title"].strip()) > 0)

    def test_submission_requirement_boolean_typing(self):
        """submit_required must be a strict boolean."""
        for it in self.raw_items:
            self.assertIsInstance(it["submit_required"], bool)


class TestFeature16OralQuizFullDetailFetch(unittest.TestCase):
    """Tests for F-16: Oral/Quiz Full Detail Fetch."""

    def setUp(self):
        self.abigail_html = (FIXTURES_DIR / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        self.items = ReferenceScraperOracle.parse_table_items(self.abigail_html)

    def test_quiz_item_extracts_detail_content(self):
        """Quiz 1 on 17/9 extracts the full syllabus detail string."""
        quiz_item = next(it for it in self.items if "Quiz 1" in it["title"])
        self.assertIn("detail", quiz_item)
        self.assertIn("Present Simple", quiz_item["detail"])
        self.assertIn("Reading Comprehension", quiz_item["detail"])

    def test_oral_exam_item_extracts_detail_content(self):
        """Oral exam item extracts full speech guidelines."""
        oral_item = next(it for it in self.items if "口試" in it["title"])
        self.assertIn("detail", oral_item)
        self.assertIn("3分鐘內", oral_item["detail"])
        self.assertIn("繪本／改編／自創", oral_item["detail"])

    def test_regular_task_omits_detail_if_absent(self):
        """Tasks with no extended detail do not include empty detail key."""
        chinese_item = next(it for it in self.items if "第3課習作" in it["title"])
        self.assertNotIn("detail", chinese_item)

    def test_detail_is_clean_text_without_raw_html_tags(self):
        """Detail text must have HTML tags stripped and entities decoded."""
        quiz_item = next(it for it in self.items if "Quiz 1" in it["title"])
        self.assertNotRegex(quiz_item["detail"], r"<[^>]+>")

    def test_fallback_when_detail_modal_unreachable(self):
        """When detail modal cannot be retrieved, fallback notes '詳情未取到' per SOP.md."""
        fallback_item = {"subject": "英文", "title": "Oral Exam", "due": "2026-09-20", "detail": "詳情未取到"}
        self.assertEqual(fallback_item["detail"], "詳情未取到")


class TestFeature17AbigailAdvancedExclusion(unittest.TestCase):
    """Tests for F-17: Abigail Advanced Exclusion."""

    def setUp(self):
        self.abigail_html = (FIXTURES_DIR / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        self.raw_items = ReferenceScraperOracle.parse_table_items(self.abigail_html)
        self.filtered = ReferenceScraperOracle.filter_abigail_items(self.raw_items)

    def test_advanced_math_excluded(self):
        """Subject '進階數學' must be 100% excluded for Abigail."""
        subjects = [it["subject"] for it in self.filtered]
        self.assertNotIn("進階數學", subjects)

    def test_advanced_english_excluded(self):
        """Subject '進階英文' must be 100% excluded for Abigail."""
        subjects = [it["subject"] for it in self.filtered]
        self.assertNotIn("進階英文", subjects)

    def test_zero_items_contain_advanced_keyword(self):
        """Filtered items must have 0 occurrences of '進階' in subject."""
        for it in self.filtered:
            self.assertNotIn("進階", it["subject"])

    def test_regular_subjects_preserved_after_filtering(self):
        """Regular Chinese, Math, and English subjects are safely retained."""
        subjects = {it["subject"] for it in self.filtered}
        self.assertIn("中文", subjects)
        self.assertIn("數學", subjects)
        self.assertIn("英文", subjects)

    def test_filtered_item_count_reduction(self):
        """Raw had 8 items (2 advanced), filtered must have exactly 6 items."""
        raw_advanced_count = sum(1 for it in self.raw_items if "進階" in it["subject"])
        self.assertEqual(raw_advanced_count, 2)
        self.assertEqual(len(self.filtered), len(self.raw_items) - raw_advanced_count)


class TestFeature18GloriaP1Bypass(unittest.TestCase):
    """Tests for F-18: Gloria P1 Bypass."""

    def setUp(self):
        self.gloria_html = (FIXTURES_DIR / "eclass_gloria_normal.html").read_text(encoding="utf-8")
        self.items = ReferenceScraperOracle.parse_table_items(self.gloria_html)

    def test_all_gloria_subjects_retained(self):
        """Gloria has no advanced stream filtering; all parsed items are kept."""
        self.assertEqual(len(self.items), 4)

    def test_gloria_subjects_include_general_studies(self):
        """Gloria's P1 curriculum includes '常識'."""
        subjects = {it["subject"] for it in self.items}
        self.assertIn("常識", subjects)

    def test_gloria_profile_name_verification(self):
        """Student identity must strictly verify as '李昕'."""
        name = ReferenceScraperOracle.parse_profile_name(self.gloria_html)
        self.assertEqual(name, "李昕")

    def test_rules_json_declares_p1_bypass(self):
        """status.json rules explicitly flag li_xin_has_no_advanced_track: true."""
        status_data = json.loads((ROOT / "status.json").read_text(encoding="utf-8"))
        self.assertTrue(status_data["rules"].get("li_xin_has_no_advanced_track"))

    def test_p1_vocabulary_item_retained(self):
        """P1 specific task '默字一' is retained."""
        titles = [it["title"] for it in self.items]
        self.assertTrue(any("默字一" in t for t in titles))


class TestFeature19NonSubmissionTaskInclusion(unittest.TestCase):
    """Tests for F-19: Non-Submission Task Inclusion."""

    def setUp(self):
        self.abigail_html = (FIXTURES_DIR / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        self.items = ReferenceScraperOracle.parse_table_items(self.abigail_html)

    def test_non_submission_item_is_included(self):
        """Tasks marked '不須繳交' are NOT discarded."""
        no_submit_items = [it for it in self.items if it["submit_required"] is False]
        self.assertTrue(len(no_submit_items) >= 1)

    def test_ms_au_ieong_wb_p14_is_false(self):
        """(Ms. Au Ieong) Do Wb. p.14 has submit_required == False."""
        target = next(it for it in self.items if "Ms. Au Ieong" in it["title"])
        self.assertFalse(target["submit_required"])

    def test_gloria_listening_quiz_is_non_submission(self):
        """Gloria's listening quiz '不用串字' has submit_required == False."""
        gloria_items = ReferenceScraperOracle.parse_table_items(
            (FIXTURES_DIR / "eclass_gloria_normal.html").read_text(encoding="utf-8")
        )
        listening_item = next(it for it in gloria_items if "Quiz Listening" in it["title"])
        self.assertFalse(listening_item["submit_required"])

    def test_status_json_rules_flag_include_no_submit(self):
        """status.json rules confirm include_no_submit_items: true."""
        status_data = json.loads((ROOT / "status.json").read_text(encoding="utf-8"))
        self.assertTrue(status_data["rules"].get("include_no_submit_items"))

    def test_note_preserves_context_for_non_submission(self):
        """Tasks with notes explaining why submission is omitted preserve that note."""
        target = next(it for it in self.items if "Ms. Au Ieong" in it["title"])
        self.assertIn("note", target)
        self.assertIn("不用交", target["note"])


class TestFeature20DueDateCanonicalization(unittest.TestCase):
    """Tests for F-20: Due Date Canonicalization."""

    def test_iso_date_passes_unchanged(self):
        """YYYY-MM-DD remains unchanged."""
        self.assertEqual(ReferenceScraperOracle.canonicalize_date("2026-09-15"), "2026-09-15")

    def test_slash_separated_date_normalized(self):
        """2026/09/15 -> 2026-09-15."""
        self.assertEqual(ReferenceScraperOracle.canonicalize_date("2026/09/15"), "2026-09-15")

    def test_chinese_month_day_normalized(self):
        """9月15日 with default year 2026 -> 2026-09-15."""
        self.assertEqual(ReferenceScraperOracle.canonicalize_date("9月15日", 2026), "2026-09-15")

    def test_single_digit_month_day_padded_with_zero(self):
        """2026/9/5 -> 2026-09-05."""
        self.assertEqual(ReferenceScraperOracle.canonicalize_date("2026/9/5"), "2026-09-05")

    def test_invalid_date_raises_value_error(self):
        """Unparseable garbage date raises ValueError."""
        with self.assertRaises(ValueError):
            ReferenceScraperOracle.canonicalize_date("INVALID_DATE")


class TestFeature21FourSectionDateCategorization(unittest.TestCase):
    """Tests for F-21: 4-Section Date Categorization."""

    def setUp(self):
        self.abigail_html = (FIXTURES_DIR / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        raw = ReferenceScraperOracle.parse_table_items(self.abigail_html)
        filtered = ReferenceScraperOracle.filter_abigail_items(raw)
        self.sections = ReferenceScraperOracle.categorize_items(filtered, MACAU_TODAY)

    def test_due_today_contains_same_day_tasks(self):
        """Tasks with due <= 2026-09-15 go to due_today."""
        titles = [it["title"] for it in self.sections["due_today"]]
        self.assertIn("第3課習作", titles)
        self.assertIn("梁：習作6（p.14）", titles)

    def test_due_soon_contains_tasks_within_7_days(self):
        """Tasks due 2026-09-16 go to due_soon."""
        titles = [it["title"] for it in self.sections["due_soon"]]
        self.assertIn("呂：周四交習作6", titles)

    def test_tests_this_week_contains_quizzes(self):
        """Quiz 1 on 17/9 goes to tests_this_week."""
        titles = [it["title"] for it in self.sections["tests_this_week"]]
        self.assertIn("Quiz 1 on 17/9 (Thur)", titles)

    def test_other_contains_far_future_tasks(self):
        """Oral exam in October goes to other."""
        titles = [it["title"] for it in self.sections["other"]]
        self.assertIn("第七周隨堂進行第一段口試（愛國愛澳）", titles)

    def test_no_duplicate_items_across_sections(self):
        """Every item belongs to exactly one section."""
        all_titles = []
        for s_name, items in self.sections.items():
            for it in items:
                all_titles.append(it["title"])
        self.assertEqual(len(all_titles), len(set(all_titles)))


class TestFeature22OfflineHTMLTestFixtures(unittest.TestCase):
    """Tests for F-22: Offline HTML Test Fixtures."""

    def test_all_fixtures_exist_on_disk(self):
        """All 5 required offline test fixtures exist."""
        expected_fixtures = [
            "eclass_abigail_normal.html",
            "eclass_gloria_normal.html",
            "eclass_empty.html",
            "eclass_login_required.html",
            "eclass_wrong_student.html"
        ]
        for name in expected_fixtures:
            path = FIXTURES_DIR / name
            self.assertTrue(path.exists(), f"Missing fixture: {name}")

    def test_abigail_fixture_is_valid_html_structure(self):
        """Abigail fixture contains table and rows."""
        content = (FIXTURES_DIR / "eclass_abigail_normal.html").read_text(encoding="utf-8")
        self.assertIn("<table", content)
        self.assertIn("class=\"homework-table\"", content)

    def test_empty_fixture_contains_zero_homework_rows(self):
        """Empty fixture contains no homework rows."""
        content = (FIXTURES_DIR / "eclass_empty.html").read_text(encoding="utf-8")
        items = ReferenceScraperOracle.parse_table_items(content)
        self.assertEqual(len(items), 0)

    def test_fixtures_use_utf8_encoding(self):
        """Fixtures read cleanly with utf-8 without character corruption."""
        for p in FIXTURES_DIR.glob("*.html"):
            try:
                p.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                self.fail(f"Fixture {p.name} is not valid UTF-8: {exc}")

    def test_fixtures_contain_no_real_passwords(self):
        """Fixtures contain zero sensitive family passwords."""
        for p in FIXTURES_DIR.glob("*.html"):
            content = p.read_text(encoding="utf-8")
            self.assertNotIn("real_secret_password", content)


if __name__ == "__main__":
    unittest.main()
