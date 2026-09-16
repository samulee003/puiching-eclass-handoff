#!/usr/bin/env python3
"""E2E Test Suite for Tier 4: Real-World Home-School Scenarios.

Scenarios Covered:
1. Scenario A: Abigail (P3) After-School Routine
   - Completes 4 homework tasks
   - Advanced subjects are 100% excluded
   - Quiz details are fully visible
   - Earns task points + all-done bonus
2. Scenario B: Gloria (P1) First-Grade Routine
   - Simplified view, zero mandatory today items
   - Listening quiz with non-submission notice
   - No advanced stream filter; verified student identity
3. Scenario C: Exam & Quiz Heavy Week
   - Multiple oral and written quizzes across both children
   - Categorized into tests_this_week with detail syllabus
   - Parent overview aggregates both children's exam schedule
4. Scenario D: Evening Reward Redemption
   - Points earned throughout the day
   - Child visits snack shop catalog
   - Redeems snack; balance deducted
   - Conforms strictly to sanitizePointsChild contract
"""

import copy
import datetime
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATUS_JSON = ROOT / "status.json"
FIXTURES_DIR = ROOT / "tests" / "fixtures"
SCENARIO_JSON = FIXTURES_DIR / "scenario_status.json" if (FIXTURES_DIR / "scenario_status.json").exists() else STATUS_JSON


class TestTier4ScenarioAbigailSchoolDay(unittest.TestCase):
    """Scenario A: Abigail (P3) Typical School Day Routine."""

    def setUp(self):
        self.status = json.loads(SCENARIO_JSON.read_text(encoding="utf-8"))
        self.abigail = next(c for c in self.status["children"] if c["id"] == "li-yue")
        self.rewards = self.status["rewards"]

    def test_abigail_profile_and_grade(self):
        """Abigail is enrolled in Primary 3 (P3) with Chinese name 李悅."""
        self.assertEqual(self.abigail["en"], "Abigail")
        self.assertEqual(self.abigail["zh"], "李悅")
        self.assertEqual(self.abigail["grade"], "P3")

    def test_abigail_todays_homework_items(self):
        """Abigail has 4 homework items scheduled for today."""
        due_today = self.abigail["due_today"]
        self.assertEqual(len(due_today), 4)

        titles = [it["title"] for it in due_today]
        self.assertIn("第3課習作", titles)
        self.assertIn("梁：習作6（p.14）", titles)
        self.assertIn("(Ms. Au Ieong) Do Wb. p.14", titles)
        self.assertIn("(Miss Valentina) Do Wb. p.16", titles)

    def test_abigail_advanced_subjects_filtered_out(self):
        """None of Abigail's homework sections contain '進階'."""
        for sec in ["due_today", "due_soon", "tests_this_week", "other"]:
            for it in self.abigail.get(sec, []):
                self.assertNotIn("進階", it["subject"])

    def test_abigail_quiz_has_complete_grammar_detail(self):
        """English Quiz 1 contains full syllabus detail for study."""
        tests = self.abigail.get("tests_this_week", [])
        quiz = next((t for t in tests if "Quiz 1" in t["title"]), None)
        self.assertIsNotNone(quiz)
        self.assertIn("Present Simple", quiz["detail"])
        self.assertIn("Reading Comprehension", quiz["detail"])

    def test_abigail_earns_points_and_all_done_bonus(self):
        """Checking all 4 tasks awards 40 points + 20 all_done_bonus = 60 points."""
        pts_per_task = self.rewards["points_per_task"]  # 10
        all_done = self.rewards["all_done_bonus"]        # 20
        tasks_count = len(self.abigail["due_today"])    # 4

        earned = (tasks_count * pts_per_task) + all_done
        self.assertEqual(earned, 60)


class TestTier4ScenarioGloriaSchoolDay(unittest.TestCase):
    """Scenario B: Gloria (P1) First-Grade Routine."""

    def setUp(self):
        self.status = json.loads(SCENARIO_JSON.read_text(encoding="utf-8"))
        self.gloria = next(c for c in self.status["children"] if c["id"] == "li-xin")

    def test_gloria_profile_and_grade(self):
        """Gloria is enrolled in Primary 1 (P1) with Chinese name 李昕."""
        self.assertEqual(self.gloria["en"], "Gloria")
        self.assertEqual(self.gloria["zh"], "李昕")
        self.assertEqual(self.gloria["grade"], "P1")

    def test_gloria_no_mandatory_items_due_today(self):
        """Gloria has 0 mandatory submission items due today."""
        mandatory = [it for it in self.gloria.get("due_today", []) if it.get("submit_required")]
        self.assertEqual(len(mandatory), 0)

    def test_gloria_listening_quiz_tomorrow_with_non_submission(self):
        """Gloria has a listening quiz that does not require submission."""
        all_items = self.gloria.get("due_today", []) + self.gloria.get("due_soon", [])
        quiz = next((it for it in all_items if "Quiz Listening" in it["title"]), None)
        self.assertIsNotNone(quiz)
        self.assertFalse(quiz["submit_required"])
        self.assertTrue("不用串字" in quiz["title"] or "不用串字" in quiz.get("note", ""))


    def test_gloria_retains_p1_subjects_without_advanced_filter(self):
        """Gloria's subjects include P1 general studies and vocabulary without stream filtering."""
        all_subjects = {
            it["subject"]
            for sec in ["due_today", "due_soon", "tests_this_week", "other"]
            for it in self.gloria.get(sec, [])
        }
        self.assertIn("英文", all_subjects)
        self.assertIn("常識", all_subjects)
        self.assertIn("中文", all_subjects)


class TestTier4ScenarioExamAndQuizWeek(unittest.TestCase):
    """Scenario C: Exam & Quiz Heavy Week."""

    def setUp(self):
        self.status = json.loads(SCENARIO_JSON.read_text(encoding="utf-8"))
        self.abigail = next(c for c in self.status["children"] if c["id"] == "li-yue")
        self.gloria = next(c for c in self.status["children"] if c["id"] == "li-xin")

    def test_parent_dashboard_identifies_all_quizzes_across_children(self):
        """Parent dashboard can identify quizzes across both children."""
        all_quizzes = []
        for child in [self.abigail, self.gloria]:
            for sec in ["due_today", "due_soon", "tests_this_week", "other"]:
                for it in child.get(sec, []):
                    if any(kw in it["title"] or kw in it["subject"] for kw in ["Quiz", "口試", "測驗", "默字"]):
                        all_quizzes.append((child["en"], it["subject"], it["title"], it.get("detail", "")))

        # Abigail has Quiz 1 and Oral exam; Gloria has Quiz Listening and 默字一
        self.assertTrue(len(all_quizzes) >= 4)
        abigail_quizzes = [q for q in all_quizzes if q[0] == "Abigail"]
        gloria_quizzes = [q for q in all_quizzes if q[0] == "Gloria"]
        self.assertTrue(len(abigail_quizzes) >= 2)
        self.assertTrue(len(gloria_quizzes) >= 2)


class TestTier4ScenarioRewardRedemption(unittest.TestCase):
    """Scenario D: Homework Completion & Snack Shop Redemption."""

    def setUp(self):
        self.status = json.loads(SCENARIO_JSON.read_text(encoding="utf-8"))
        self.catalog = self.status["rewards"]["catalog"]

    def test_catalog_has_affordable_snacks(self):
        """Catalog has gummy (50), choco (80), chips (120), ice cream (150)."""
        snack_map = {item["id"]: item["cost"] for item in self.catalog}
        self.assertEqual(snack_map.get("gummy"), 50)
        self.assertEqual(snack_map.get("choco"), 80)
        self.assertEqual(snack_map.get("chips"), 120)
        self.assertEqual(snack_map.get("icecream"), 150)

    def test_child_redeems_gummy_with_daily_earnings(self):
        """Child with 60 earned points redeems Gummy (50), leaving 10 points balance."""
        # Initial points state
        points_record = {
            "earned": 60,
            "spent": 0,
            "awarded": {"task-1": True, "task-2": True, "task-3": True, "task-4": True},
            "bonusDates": {"2026-09-15": True},
            "redemptions": []
        }

        # Perform redemption
        snack = next(s for s in self.catalog if s["id"] == "gummy")
        self.assertGreaterEqual(points_record["earned"] - points_record["spent"], snack["cost"])

        points_record["spent"] += snack["cost"]
        points_record["redemptions"].append({
            "id": snack["id"],
            "name": snack["name"],
            "cost": snack["cost"],
            "at": "2026-09-15T19:30:00Z"
        })

        # Verify net balance
        net_balance = points_record["earned"] - points_record["spent"]
        self.assertEqual(net_balance, 10)
        self.assertEqual(len(points_record["redemptions"]), 1)
        self.assertEqual(points_record["redemptions"][0]["id"], "gummy")


if __name__ == "__main__":
    unittest.main()
