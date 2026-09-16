#!/usr/bin/env python3
"""Unified Test Runner for puiching-eclass-handoff E2E Test Suite.

Discovers and runs all 4 Tiers of tests:
- Tier 1: Feature Coverage (R1, R2, R3)
- Tier 2: Boundary & Corner Cases
- Tier 3: Cross-Feature Integration
- Tier 4: Real-World Scenarios

Produces a structured tier-by-tier report and exits with 0 on success.
"""

import io
import os
import pathlib
import sys
import time
import unittest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent

# Ensure project root and tests directory are on PYTHONPATH
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TESTS_DIR))


def run_suite_with_summary():
    loader = unittest.TestLoader()

    tier_suites = [
        ("Tier 1: R1 Firebase & Pairing (Features 1–11)", "test_e2e_r1"),
        ("Tier 1: R2 eClass Scraper & Rules (Features 12–22)", "test_e2e_r2"),
        ("Tier 1: R3 Dual-Write & Compliance (Features 23–26)", "test_e2e_r3"),
        ("Tier 2: Boundary & Corner Cases", "test_e2e_tier2_boundary"),
        ("Tier 3: Cross-Feature Integration", "test_e2e_tier3_integration"),
        ("Tier 4: Real-World Home-School Scenarios", "test_e2e_tier4_scenarios"),
    ]

    print("=" * 80)
    print("  培正 eClass 雙孩功課看板 (puiching-eclass-handoff) E2E Test Suite Runner")
    print(f"  Project Root: {PROJECT_ROOT}")
    print(f"  Execution Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 80)

    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_errors = 0
    tier_results = []

    start_all = time.time()

    for title, module_name in tier_suites:
        try:
            mod = __import__(module_name)
            suite = loader.loadTestsFromModule(mod)
        except Exception as exc:
            print(f"[-] Error loading module {module_name}: {exc}")
            total_errors += 1
            tier_results.append((title, 0, 0, 1))
            continue

        suite_count = suite.countTestCases()
        total_tests += suite_count

        # Run the suite capturing output
        buffer = io.StringIO()
        runner = unittest.TextTestRunner(stream=buffer, verbosity=1)
        result = runner.run(suite)

        passed = suite_count - len(result.failures) - len(result.errors)
        total_passed += passed
        total_failed += len(result.failures)
        total_errors += len(result.errors)

        status_flag = "PASS" if result.wasSuccessful() else "FAIL"
        tier_results.append((title, suite_count, passed, len(result.failures) + len(result.errors)))

        print(f"\n[{status_flag}] {title}")
        print(f"       Total Tests: {suite_count} | Passed: {passed} | Failures: {len(result.failures)} | Errors: {len(result.errors)}")

        if not result.wasSuccessful():
            print("       Details:")
            for failure in result.failures:
                print(f"       - FAIL: {failure[0]}")
                print(f"         {failure[1].strip()[:200]}...")
            for error in result.errors:
                print(f"       - ERROR: {error[0]}")
                print(f"         {error[1].strip()[:200]}...")

    elapsed = time.time() - start_all

    print("\n" + "=" * 80)
    print("                           SUMMARY OF TEST RESULTS")
    print("=" * 80)
    print(f"{'Test Tier':<55} | {'Count':<6} | {'Passed':<6} | {'Status'}")
    print("-" * 80)
    for title, count, passed, err_count in tier_results:
        status_str = "PASS" if err_count == 0 else f"FAIL ({err_count})"
        print(f"{title:<55} | {count:<6} | {passed:<6} | {status_str}")
    print("-" * 80)
    print(f"Total Test Cases: {total_tests}")
    print(f"Total Passed:     {total_passed}")
    print(f"Total Failed:     {total_failed}")
    print(f"Total Errors:     {total_errors}")
    print(f"Total Time:       {elapsed:.2f} seconds")

    # Coverage Quality Gates check
    quality_gates_passed = True
    tier1_count = sum(c for t, c, p, e in tier_results if "Tier 1" in t)
    tier2_count = sum(c for t, c, p, e in tier_results if "Tier 2" in t)
    tier3_count = sum(c for t, c, p, e in tier_results if "Tier 3" in t)
    tier4_count = sum(c for t, c, p, e in tier_results if "Tier 4" in t)

    print("\nCoverage Quality Gates:")
    print(f"- Tier 1 Feature Coverage: {tier1_count} tests (target >= 130): {'MET' if tier1_count >= 130 else 'NOT MET'}")
    print(f"- Tier 2 Boundary Cases:   {tier2_count} tests (target >= 15):  {'MET' if tier2_count >= 15 else 'NOT MET'}")
    print(f"- Tier 3 Integration:      {tier3_count} tests (target >= 4):   {'MET' if tier3_count >= 4 else 'NOT MET'}")
    print(f"- Tier 4 Real-World:       {tier4_count} tests (target >= 4):   {'MET' if tier4_count >= 4 else 'NOT MET'}")

    if total_failed > 0 or total_errors > 0:
        print("\n>> OVERALL RESULT: FAILED <<")
        return 1
    else:
        print("\n>> OVERALL RESULT: ALL TESTS PASSED SUCCESSFULLY <<")
        return 0


if __name__ == "__main__":
    sys.exit(run_suite_with_summary())
