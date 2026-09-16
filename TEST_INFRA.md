# Test Infrastructure Specification (TEST_INFRA.md)

## 1. Executive Summary & Test Architecture

The **puiching-eclass-handoff** test harness is an opaque-box, requirement-driven E2E verification system designed to validate the B+C Lazy Integration solution for the Pui Ching Middle School Macau (培正中學) eClass homework dashboard.

The architecture enforces strict separation of concerns:
- **Opaque-Box Requirement Verification**: Tests validate interfaces, schemas, contracts, and observable behaviors against `ORIGINAL_REQUEST.md` and `PROJECT.md`, without coupling to internal implementation quirks.
- **Progressive Testability**: The test suite can run in phases or as a unified suite. Tests verify components at unit, contract, integration, and scenario levels.
- **Zero External Dependencies**: Implemented in standard Python 3 (`unittest`), making it runnable on any machine or CI pipeline (`GitHub Actions`) without external network access or fragile browser drivers.
- **Mock & Reference Oracles**: Incorporates deterministic offline HTML fixtures, JSON schema validators, SHA-256 room derivations, and base32 pairing code oracles.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Test Suite Architecture                                       │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  [ Tier 1: Feature Coverage (>=5 tests / feature) ]                                            │
│  ├── test_e2e_r1.py              (Features 1–11: Firebase, RTDB, Pairing, QR, Queue, UI)       │
│  ├── test_e2e_r2.py              (Features 12–22: eClass Scraper, Filter, Detail, Auth Gate)   │
│  └── test_e2e_r3.py              (Features 23–26: Dual-Write, Non-HW State, Draft-7 Schema)   │
│                                                                                                 │
│  [ Tier 2: Boundary & Corner Cases ]                                                           │
│  └── test_e2e_tier2_boundary.py  (Empty tables, bad codes, leap years, session timeouts, quota)│
│                                                                                                 │
│  [ Tier 3: Cross-Feature Integration ]                                                         │
│  └── test_e2e_tier3_integration.py (Scraper -> Dual-Write -> Validation -> Sync -> Pairing)     │
│                                                                                                 │
│  [ Tier 4: Real-World Scenarios ]                                                              │
│  └── test_e2e_tier4_scenarios.py (Abigail P3 school day, Gloria P1 day, Exam rush, Rewards)   │
│                                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Runner & Infrastructure:                                                                        │
│  ├── tests/run_all_tests.py      (Automated Python test runner with colorized tier reports)     │
│  ├── tests/run_all_tests.sh      (POSIX shell wrapper script)                                   │
│  └── tests/fixtures/             (Deterministic HTML fixtures for eClass & login mocks)         │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Feature Inventory & Test Mapping

All 26 features identified in `PROJECT.md` are mapped to dedicated test cases:

| Feature ID | Feature Name | Requirement | Test Suite File | Minimum Target Tests |
|---|---|---|---|---|
| **F-01** | Automated Firebase CLI Init | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-02** | RTDB & Anonymous Auth Config | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-03** | Web SDK Config Generation | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-04** | firebase.json Configuration | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-05** | Parent QR Code Generation | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-06** | Parent Quick Pairing URL | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-07** | Child Zero-Typing Pairing | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-08** | Address Bar Sanitization | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-09** | Connection Status Indicators | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-10** | Offline Queue & Quick Flush | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-11** | LocalStorage Graceful Degradation | R1 | `tests/test_e2e_r1.py` | 5 tests |
| **F-12** | Secure Env-Var Credentials | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-13** | Profile Identity Verification | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-14** | LOGIN_REQUIRED Error Handling | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-15** | eClass Homework Table Extraction | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-16** | Oral/Quiz Full Detail Fetch | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-17** | Abigail Advanced Exclusion | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-18** | Gloria P1 Bypass | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-19** | Non-Submission Task Inclusion | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-20** | Due Date Canonicalization | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-21** | 4-Section Date Categorization | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-22** | Offline HTML Test Fixtures | R2 | `tests/test_e2e_r2.py` | 5 tests |
| **F-23** | Atomic Dual-Write Update | R3 | `tests/test_e2e_r3.py` | 5 tests |
| **F-24** | Non-Homework State Preservation | R3 | `tests/test_e2e_r3.py` | 5 tests |
| **F-25** | Strict Item Schema Conformance | R3 | `tests/test_e2e_r3.py` | 5 tests |
| **F-26** | Automated Compliance Validation | R3 | `tests/test_e2e_r3.py` | 5 tests |

---

## 3. Four-Tier Test Methodology

### Tier 1: Feature Coverage (Opaque-Box Specification Verification)
- **R1 Suite (`test_e2e_r1.py`)**: Tests Firebase CLI scripts, RTDB security rules syntax (`firebase.rules.json`), `firebase.json` schema, Web SDK config generation (`sync-config.js`), client pairing URL generation, QR code SVG generation, zero-typing query parameter extraction (`?sync=`, `#sync=`), history sanitization regex/logic, status indicator badge transitions, offline queue serialization, and unconfigured degradation.
- **R2 Suite (`test_e2e_r2.py`)**: Tests credential ingestion from environment variables (no hardcoded passwords), identity verification for Abigail (李悅) and Gloria (李昕), strict `LOGIN_REQUIRED` rejection without data fabrication, HTML table parsing, oral/quiz detail extraction, 100% "進階" exclusion for Abigail, non-filtering for Gloria, `submit_required: false` inclusion, date canonicalization to `YYYY-MM-DD`, and 4-section categorization.
- **R3 Suite (`test_e2e_r3.py`)**: Tests synchronized updates of `status.json` and `DASHBOARD.md`, preservation of non-homework keys (`rewards`, `rules`, `scan_schedule_macau`, `ui`, `cleared`, `owner`, `chrome_password_saved`), strict Draft-7 JSON Schema compliance (`additionalProperties: false`), and execution of `scripts/validate_status.py`.

### Tier 2: Boundary & Corner Cases (`test_e2e_tier2_boundary.py`)
- **Empty Homework States**: Graceful handling of days with zero homework, empty sections, or children with all tasks cleared.
- **Invalid & Malformed Sync Codes**: Codes with incorrect length (not 20 characters), illegal characters (lowercase, `I`, `L`, `O`, `0`, `1`), trailing spaces, non-base32 symbols.
- **Authentication Failures & Expired Sessions**: eClass redirects to login page, HTTP 401/403 responses, session timeout during pagination, HTML response with "登入逾時" or "請重新登入".
- **Leap Year & Calendar Edge Dates**: Leap days (e.g. `2028-02-29`), invalid dates (e.g. `2026-02-29`), month transitions (Aug 31 -> Sep 1), year boundaries (Dec 31 -> Jan 1).
- **LocalStorage Quota & Storage Unavailability**: Simulation of `QuotaExceededError`, incognito mode restrictions, corrupt local JSON.
- **Network State Flapping**: Flapping between connected and disconnected, queuing writes while offline and asserting sequential replay.

### Tier 3: Cross-Feature Integration (`test_e2e_tier3_integration.py`)
- **Complete Scraper-to-Dashboard Pipeline**:
  1. eClass scraper ingests mock fixtures with environment credentials.
  2. Rule engine filters Abigail's advanced subjects and retains Gloria's subjects.
  3. Scraper outputs normalized dictionary to Dual-writer.
  4. Dual-writer updates `status.json` and `DASHBOARD.md` while preserving existing non-homework metadata.
  5. `scripts/validate_status.py` executes against updated `status.json` and asserts exit code 0.
- **Complete Parent-to-Child Sync Pipeline**:
  1. Parent interface generates 20-character base32 code and SHA-256 room reference.
  2. Parent UI generates pairing URLs (`abigail.html?sync=...`).
  3. Child interface extracts URL parameter, sanitizes browser history, and writes code to localStorage.
  4. Child marks homework item as done; writes are added to local pending queue.
  5. On simulated connection, pending queue flushes to room reference and updates status badge to "已同步 ☁️".

### Tier 4: Real-World Scenarios (`test_e2e_tier4_scenarios.py`)
- **Scenario 1: Abigail (P3) Typical School Day**:
  - Chinese lesson 3 worksheet (due today, submit required).
  - Math workbook (due today, note included).
  - English spelling challenge (due today, submit_required: false).
  - English quiz (due tomorrow, full grammar detail extracted).
  - Advanced math omitted completely.
- **Scenario 2: Gloria (P1) Typical School Day**:
  - English quiz listening (due tomorrow, not requiring spelling).
  - General Studies worksheet (due next week).
  - Chinese vocabulary practice.
  - Zero advanced filtering applied; correct identity verified.
- **Scenario 3: Exam & Quiz Heavy Week**:
  - Multiple quizzes across both children sorted into `tests_this_week`.
  - Due dates properly canonicalized and categorized.
- **Scenario 4: Homework Completion & Snack Shop Redemption**:
  - Abigail finishes 4 homework items (earning 40 points) + daily bonus (20 points) = 60 points.
  - Redeems Gummy candy (50 points); balance updates to 10 points.
  - Points record structure conforms to `sanitizePointsChild` contract (`{earned: 60, spent: 50, awarded: {...}, bonusDates: {...}, redemptions: [...]}`).

---

## 4. Coverage Thresholds & Quality Gates

The test suite enforces the following quantitative quality thresholds:

| Metric | Target Threshold | Method of Verification |
|---|---|---|
| **Tier 1 Feature Tests** | >= 5 tests per feature (>=130 tests total) | Automated count in `run_all_tests.py` |
| **Tier 2 Boundary Tests** | >= 15 boundary & corner tests | Automated count in `run_all_tests.py` |
| **Tier 3 Integration Tests** | >= 8 end-to-end integration workflows | Automated count in `run_all_tests.py` |
| **Tier 4 Scenario Tests** | >= 4 end-to-end real-world scenarios | Automated count in `run_all_tests.py` |
| **Draft-7 Schema Compliance** | 100% pass on `status.json` outputs | `scripts/validate_status.py` exit code 0 |
| **Pass Rate** | 100% of applicable tests must pass | `tests/run_all_tests.sh` exit code 0 |

---

## 5. Execution & Verification

### Running the Entire Test Suite
```bash
# Using the Python test runner (detailed report):
python3 tests/run_all_tests.py

# Or using standard unittest:
python3 -m unittest discover -s tests -p "test_*.py"

# Or using the shell wrapper:
bash tests/run_all_tests.sh
```

### Running Specific Tiers
```bash
# Tier 1: R1 Firebase & Pairing
python3 -m unittest tests/test_e2e_r1.py

# Tier 1: R2 eClass Scraper & Rules
python3 -m unittest tests/test_e2e_r2.py

# Tier 1: R3 Dual-Write & Compliance
python3 -m unittest tests/test_e2e_r3.py

# Tier 2: Boundary & Corner Cases
python3 -m unittest tests/test_e2e_tier2_boundary.py

# Tier 3: Cross-Feature Integration
python3 -m unittest tests/test_e2e_tier3_integration.py

# Tier 4: Real-World Scenarios
python3 -m unittest tests/test_e2e_tier4_scenarios.py
```
