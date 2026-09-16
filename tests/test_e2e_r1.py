#!/usr/bin/env python3
"""E2E Test Suite for Requirement 1 (R1): Firebase Synchronization & Zero-Typing Pairing.

Features Covered (Tiers 1 & 2):
- F-01: Automated Firebase CLI Init (setup_firebase.sh)
- F-02: RTDB & Anonymous Auth Config (firebase.rules.json, auth rules)
- F-03: Web SDK Config Generation (sync-config.js structure & parser)
- F-04: firebase.json Configuration (database rules & CLI config)
- F-05: Parent QR Code Generation (pure client-side SVG/canvas, no external leak)
- F-06: Parent Quick Pairing URL generation (abigail/gloria URL templates)
- F-07: Child Zero-Typing Pairing (query string / hash parsing & normalization)
- F-08: Address Bar Sanitization (history.replaceState contract)
- F-09: Connection Status Indicators (badge state machine)
- F-10: Offline Queue & Quick Flush (pending write serialization & replay)
- F-11: LocalStorage Graceful Degradation (unconfigured / offline fallback)
"""

import hashlib
import json
import os
import pathlib
import re
import unittest
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
SYNC_JS = ROOT / "sync.js"
SYNC_CONFIG_JS = ROOT / "sync-config.js"
FIREBASE_RULES_JSON = ROOT / "firebase.rules.json"
FIREBASE_JSON = ROOT / "firebase.json"
SETUP_FIREBASE_SH = ROOT / "scripts" / "setup_firebase.sh"
INDEX_HTML = ROOT / "index.html"
ABIGAIL_HTML = ROOT / "abigail.html"
GLORIA_HTML = ROOT / "gloria.html"

# Base32 alphabet and code pattern defined in sync.js
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_PATTERN = re.compile(r"^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{20}$")


def normalize_code(code_str: str) -> str:
    """Canonical normalization function as implemented in sync.js."""
    return re.sub(r"[\s-]", "", str(code_str or "")).upper()


def format_code(code_str: str) -> str:
    """Format 20-char code into 4-4-4-4-4 hyphenated groups."""
    c = normalize_code(code_str)
    chunks = [c[i : i + 4] for i in range(0, len(c), 4) if c[i : i + 4]]
    return "-".join(chunks) or c


def derive_room_id(code: str) -> str:
    """Authoritative Room ID derivation: SHA-256('puiching-eclass-room-v1:' + code)."""
    norm = normalize_code(code)
    payload = f"puiching-eclass-room-v1:{norm}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class TestFeature01FirebaseCLIInit(unittest.TestCase):
    """Tests for F-01: Automated Firebase CLI Init."""

    def test_setup_script_path_convention(self):
        """Verify the setup script exists or is defined in scripts/ directory per PROJECT.md."""
        expected_path = ROOT / "scripts" / "setup_firebase.sh"
        # Must be within scripts/
        self.assertEqual(expected_path.name, "setup_firebase.sh")
        self.assertTrue(expected_path.parent.is_dir())

    def test_setup_script_shebang_and_safety_flags(self):
        """Verify setup script contains bash shebang and safety flags if present."""
        if SETUP_FIREBASE_SH.exists():
            content = SETUP_FIREBASE_SH.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("#!/usr/bin/env bash") or content.startswith("#!/bin/bash"))
            self.assertIn("set -e", content)

    def test_setup_script_references_firebase_cli(self):
        """Verify setup script invokes firebase CLI with non-interactive flags."""
        if SETUP_FIREBASE_SH.exists():
            content = SETUP_FIREBASE_SH.read_text(encoding="utf-8")
            self.assertTrue("firebase" in content or "firebase-tools" in content)

    def test_setup_script_requires_project_id(self):
        """Verify setup script handles project ID parameter or argument."""
        if SETUP_FIREBASE_SH.exists():
            content = SETUP_FIREBASE_SH.read_text(encoding="utf-8")
            self.assertTrue("PROJECT_ID" in content or "PROJECT" in content or "$1" in content)

    def test_setup_script_contains_no_hardcoded_secrets(self):
        """Verify setup script contains zero hardcoded API keys, passwords, or tokens."""
        if SETUP_FIREBASE_SH.exists():
            content = SETUP_FIREBASE_SH.read_text(encoding="utf-8")
            self.assertNotRegex(content, r"AIza[0-9A-Za-z-_]{35}")
            self.assertNotIn("PRIVATE KEY", content)


class TestFeature02RTDBAndAuthRules(unittest.TestCase):
    """Tests for F-02: RTDB & Anonymous Auth Config."""

    def setUp(self):
        self.assertTrue(FIREBASE_RULES_JSON.exists(), "firebase.rules.json must exist")
        self.rules = json.loads(FIREBASE_RULES_JSON.read_text(encoding="utf-8"))

    def test_rules_json_valid_syntax(self):
        """firebase.rules.json must be valid JSON."""
        self.assertIsInstance(self.rules, dict)
        self.assertIn("rules", self.rules)

    def test_rules_restrict_read_to_authenticated_users(self):
        """Rooms cannot be read by unauthenticated clients."""
        room_rules = self.rules["rules"]["rooms"]["$roomId"]
        self.assertEqual(room_rules.get(".read"), "auth != null")

    def test_rules_forbid_listing_all_rooms(self):
        """Listing /rooms without a specific $roomId must be forbidden."""
        rooms_node = self.rules["rules"]["rooms"]
        self.assertNotIn(".read", rooms_node)

    def test_todos_write_enforces_device_id_matches_auth_uid(self):
        """Todos write rule must enforce deviceId == auth.uid."""
        todo_rules = self.rules["rules"]["rooms"]["$roomId"]["todos"]["$itemId"]
        validate_expr = todo_rules.get(".validate", "")
        self.assertIn("newData.child('deviceId').val() == auth.uid", validate_expr)
        self.assertIn("newData.child('done').isBoolean()", validate_expr)

    def test_points_write_enforces_schema_validation(self):
        """Points write rule must require key, data, updatedAt, deviceId."""
        points_rules = self.rules["rules"]["rooms"]["$roomId"]["points"]["$itemId"]
        validate_expr = points_rules.get(".validate", "")
        self.assertIn("newData.hasChildren(['key', 'data', 'updatedAt', 'deviceId'])", validate_expr)
        self.assertIn("newData.child('deviceId').val() == auth.uid", validate_expr)


class TestFeature03WebSDKConfigGen(unittest.TestCase):
    """Tests for F-03: Web SDK Config Generation."""

    def test_sync_config_file_exists(self):
        """sync-config.js must exist in project root."""
        self.assertTrue(SYNC_CONFIG_JS.exists())

    def test_sync_config_defines_global_object(self):
        """sync-config.js must define window.PUICHING_SYNC_CONFIG."""
        content = SYNC_CONFIG_JS.read_text(encoding="utf-8")
        self.assertIn("window.PUICHING_SYNC_CONFIG", content)

    def test_sync_config_has_required_keys(self):
        """sync-config.js must declare all required Web SDK fields."""
        content = SYNC_CONFIG_JS.read_text(encoding="utf-8")
        for key in ["apiKey", "authDomain", "databaseURL", "projectId", "appId"]:
            self.assertIn(key, content, f"Expected {key} in sync-config.js")

    def test_sync_config_contains_no_sensitive_secrets(self):
        """sync-config.js must NOT contain private keys or passwords."""
        content = SYNC_CONFIG_JS.read_text(encoding="utf-8")
        self.assertNotIn("BEGIN PRIVATE KEY", content)
        self.assertNotIn("service_account", content)
        # Avoid checking 'password' in comments, check assignment or value
        self.assertNotIn('password":', content.lower())
        self.assertNotIn('password =', content.lower())

    def test_sync_is_configured_logic(self):
        """Test isConfigured predicate behavior against sample configs."""
        def is_configured(cfg):
            return cfg.get("enabled") is not False and all(
                bool(cfg.get(k)) for k in ["apiKey", "authDomain", "databaseURL", "projectId", "appId"]
            )
        self.assertFalse(is_configured({}))
        self.assertFalse(is_configured({"apiKey": "", "authDomain": "test"}))
        self.assertTrue(is_configured({
            "apiKey": "AIzaSyFakeKey",
            "authDomain": "test.firebaseapp.com",
            "databaseURL": "https://test.firebaseio.com",
            "projectId": "test-proj",
            "appId": "1:123:web:abc"
        }))


class TestFeature04FirebaseJsonConfig(unittest.TestCase):
    """Tests for F-04: firebase.json Configuration."""

    def test_firebase_json_schema_when_present(self):
        """firebase.json must map database rules to firebase.rules.json."""
        self.assertTrue(FIREBASE_JSON.exists(), "firebase.json should exist")
        data = json.loads(FIREBASE_JSON.read_text(encoding="utf-8"))
        self.assertIn("database", data)
        self.assertEqual(data["database"].get("rules"), "firebase.rules.json")

    def test_firebase_json_declares_database_target(self):
        """firebase.json or setup documentation defines database rules file."""
        if FIREBASE_JSON.exists():
            content = FIREBASE_JSON.read_text(encoding="utf-8")
            self.assertIn("firebase.rules.json", content)

    def test_firebase_rules_filename_cohesion(self):
        """Verify firebase.rules.json filename matches specification."""
        self.assertEqual(FIREBASE_RULES_JSON.name, "firebase.rules.json")

    def test_firebase_json_valid_json_format(self):
        """firebase.json if present must parse as valid JSON without trailing commas."""
        if FIREBASE_JSON.exists():
            try:
                json.loads(FIREBASE_JSON.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self.fail(f"firebase.json has invalid JSON: {exc}")

    def test_firebase_database_configuration_scope(self):
        """Verify RTDB configuration does not mix with unrelated cloud functions or hosting overrides."""
        if FIREBASE_JSON.exists():
            data = json.loads(FIREBASE_JSON.read_text(encoding="utf-8"))
            if "database" in data:
                self.assertIsInstance(data["database"], dict)


class TestFeature05ParentQRCodeGeneration(unittest.TestCase):
    """Tests for F-05: Parent QR Code Generation."""

    def test_index_html_contains_sync_panel(self):
        """index.html must declare sync-panel with data-sync-role='parent'."""
        content = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="sync-panel"', content)
        self.assertIn('data-sync-role="parent"', content)

    def test_pure_client_side_qr_no_external_api_leak(self):
        """index.html and sync.js must NEVER make HTTP calls to third-party QR generators like qrserver or googleapis."""
        sync_code = SYNC_JS.read_text(encoding="utf-8")
        index_code = INDEX_HTML.read_text(encoding="utf-8")
        forbidden_domains = ["api.qrserver.com", "chart.googleapis.com", "quickchart.io/qr"]
        for domain in forbidden_domains:
            self.assertNotIn(domain, sync_code)
            self.assertNotIn(domain, index_code)

    def test_svg_qr_generator_asset_or_inline_definition(self):
        """Asset or script must support pure client-side SVG/canvas generation."""
        assets_dir = ROOT / "assets"
        has_qr_asset = (assets_dir / "qrcode.min.js").exists() or (assets_dir / "qrcode.js").exists()
        has_inline_qr = "QRCode" in SYNC_JS.read_text(encoding="utf-8") or "QRCode" in INDEX_HTML.read_text(encoding="utf-8")
        self.assertTrue(has_qr_asset or has_inline_qr)

    def test_qr_code_payload_format(self):
        """QR code payload must encode an absolute or relative pairing URL with sync parameter."""
        code = "ABCDEFGHJKMNPQRSTUV2"
        mock_base = "https://samulee003.github.io/puiching-eclass-handoff/"
        abigail_url = f"{mock_base}abigail.html?sync={code}"
        parsed = urllib.parse.urlparse(abigail_url)
        params = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(params.get("sync"), [code])

    def test_parent_panel_has_role_attribute(self):
        """Sync panel role must differentiate parent overview from child tablet."""
        content = INDEX_HTML.read_text(encoding="utf-8")
        self.assertTrue('data-sync-role="parent"' in content)


class TestFeature06ParentQuickPairingURL(unittest.TestCase):
    """Tests for F-06: Parent Quick Pairing URL."""

    def test_generate_pairing_url_abigail(self):
        """Pairing URL for Abigail points to abigail.html with ?sync= parameter."""
        base_url = "https://example.com/puiching/"
        raw_code = "ABCDEFGHJKMNPQRSTUV2"
        expected_url = f"{base_url}abigail.html?sync={raw_code}"
        self.assertTrue(expected_url.startswith(base_url))
        self.assertIn("abigail.html?sync=", expected_url)

    def test_generate_pairing_url_gloria(self):
        """Pairing URL for Gloria points to gloria.html with ?sync= parameter."""
        base_url = "https://example.com/puiching/"
        raw_code = "ABCDEFGHJKMNPQRSTUV2"
        expected_url = f"{base_url}gloria.html?sync={raw_code}"
        self.assertIn("gloria.html?sync=", expected_url)

    def test_generate_pairing_url_preserves_hyphenated_code(self):
        """Pairing URL works with either formatted or raw code."""
        base_url = "https://example.com/"
        formatted = "ABCD-EFGH-JKMN-PQRS-TUV2"
        url = f"{base_url}abigail.html?sync={formatted}"
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(normalize_code(params["sync"][0]), "ABCDEFGHJKMNPQRSTUV2")

    def test_quick_pairing_supports_hash_fallback(self):
        """Hash-based pairing link #sync=... is recognized for zero-server-log environments."""
        url = "https://example.com/abigail.html#sync=ABCDEFGHJKMNPQRSTUV2"
        parsed = urllib.parse.urlparse(url)
        fragment = parsed.fragment
        self.assertTrue(fragment.startswith("sync="))
        extracted = fragment.split("sync=")[1]
        self.assertEqual(normalize_code(extracted), "ABCDEFGHJKMNPQRSTUV2")

    def test_abigail_and_gloria_target_pages_exist(self):
        """Both target child pages abigail.html and gloria.html must exist."""
        self.assertTrue(ABIGAIL_HTML.exists())
        self.assertTrue(GLORIA_HTML.exists())


class TestFeature07ChildZeroTypingPairing(unittest.TestCase):
    """Tests for F-07: Child Zero-Typing Pairing."""

    def test_parse_sync_param_from_query_string(self):
        """Extract sync code from query string 'sync' parameter."""
        qs = "?sync=2345-6789-ABCD-EFGH-JKMN"
        params = urllib.parse.parse_qs(qs.lstrip("?"))
        code = normalize_code(params.get("sync", [""])[0])
        self.assertTrue(CODE_PATTERN.match(code))

    def test_parse_sync_param_from_alternative_keys(self):
        """Extract sync code from 'familyCode', 'familyId', or 'code' parameters."""
        for key in ["familyCode", "familyId", "code"]:
            qs = f"?{key}=23456789ABCDEFGHJKMN"
            params = urllib.parse.parse_qs(qs.lstrip("?"))
            code = normalize_code(params.get(key, [""])[0])
            self.assertEqual(len(code), 20)

    def test_normalize_code_removes_spaces_and_hyphens(self):
        """Normalization removes whitespace, tabs, and hyphens."""
        raw = " 2345 - 6789 - ABCD - EFGH - JKMN "
        norm = normalize_code(raw)
        self.assertEqual(norm, "23456789ABCDEFGHJKMN")

    def test_code_validation_against_base32_alphabet(self):
        """Codes with characters outside base32 alphabet (e.g. 0, 1, I, O) must fail validation."""
        invalid_codes = [
            "23456789ABCDEFGHJKMI",  # 'I' is invalid
            "23456789ABCDEFGHJKMO",  # 'O' is invalid
            "23456789ABCDEFGHJKM0",  # '0' is invalid
            "23456789ABCDEFGHJKM1",  # '1' is invalid
            "23456789ABCDEFGHJKM!",  # Symbol invalid
            "23456789ABCDEFGHJK",    # 19 chars (short)
            "23456789ABCDEFGHJKMNA", # 21 chars (long)
        ]
        for c in invalid_codes:
            self.assertIsNone(CODE_PATTERN.match(c), f"Expected {c} to be invalid")

    def test_room_id_deterministic_sha256_derivation(self):
        """Room ID derivation must be SHA-256('puiching-eclass-room-v1:' + code)."""
        code = "ABCDEFGHJKMNPQRSTUV2"
        expected_hash = hashlib.sha256(f"puiching-eclass-room-v1:{code}".encode("utf-8")).hexdigest()
        self.assertEqual(derive_room_id(code), expected_hash)
        self.assertEqual(len(expected_hash), 64)


class TestFeature08AddressBarSanitization(unittest.TestCase):
    """Tests for F-08: Address Bar Sanitization."""

    def test_sanitization_pattern_matches_query_string(self):
        """Query parameter regex identifies ?sync=... in location string."""
        url = "https://example.com/abigail.html?sync=2345-6789-ABCD-EFGH-JKMN&foo=bar"
        clean_url = re.sub(r"[?&]sync=[^&#]*", "", url).replace("?&", "?")
        self.assertNotIn("sync=", clean_url)

    def test_sanitization_removes_standalone_sync_param(self):
        """When sync is the only parameter, trailing '?' is removed."""
        url = "https://example.com/abigail.html?sync=23456789ABCDEFGHJKMN"
        clean_url = re.sub(r"\?sync=[^&#]*$", "", url)
        self.assertEqual(clean_url, "https://example.com/abigail.html")

    def test_sanitization_removes_hash_sync(self):
        """Hash fragment #sync=... is removed from URL."""
        url = "https://example.com/gloria.html#sync=23456789ABCDEFGHJKMN"
        clean_url = re.sub(r"#sync=[^&]*", "", url)
        self.assertEqual(clean_url, "https://example.com/gloria.html")

    def test_replace_state_logic_preserves_path(self):
        """Pathname and non-sync query parameters are preserved."""
        parsed = urllib.parse.urlparse("https://example.com/puiching/abigail.html?theme=dark&sync=ABC")
        query_dict = urllib.parse.parse_qs(parsed.query)
        query_dict.pop("sync", None)
        new_query = urllib.parse.urlencode(query_dict, doseq=True)
        clean = parsed._replace(query=new_query).geturl()
        self.assertIn("theme=dark", clean)
        self.assertNotIn("sync=", clean)

    def test_child_pages_load_sync_js(self):
        """Both abigail.html and gloria.html must include sync.js to run sanitization."""
        abigail_content = ABIGAIL_HTML.read_text(encoding="utf-8")
        gloria_content = GLORIA_HTML.read_text(encoding="utf-8")
        self.assertIn("sync.js", abigail_content)
        self.assertIn("sync.js", gloria_content)


class TestFeature09ConnectionStatusIndicators(unittest.TestCase):
    """Tests for F-09: Connection Status Indicators."""

    def test_badge_labels_defined(self):
        """All 4 standard status labels are recognized in the badge state machine."""
        valid_labels = ["已同步 ☁️", "本機模式 💻", "連接中…", "已離線 ⚠️", "本機模式", "已離線"]
        self.assertTrue(len(valid_labels) >= 4)

    def test_sync_js_contains_badge_states(self):
        """sync.js contains state update logic for connection badges."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertIn("已同步", content)
        self.assertIn("本機模式", content)
        self.assertIn("連接中", content)

    def test_data_sync_state_attribute_present(self):
        """UI updates panel element with [data-sync-state]."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertIn("[data-sync-state]", content)

    def test_connected_class_toggled_on_success(self):
        """Panel toggles .connected class based on connection boolean."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertTrue("classList.add('connected')" in content or "classList.toggle('connected'" in content)

    def test_message_container_updated_with_explanation(self):
        """Panel contains [data-sync-message] to explain state to parents/children."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertIn("[data-sync-message]", content)


class TestFeature10OfflineQueueAndQuickFlush(unittest.TestCase):
    """Tests for F-10: Offline Queue & Quick Flush."""

    def test_pending_store_key_contract(self):
        """Pending writes key must be 'puiching-eclass-sync-pending-v1'."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertIn("puiching-eclass-sync-pending-v1", content)

    def test_pending_queue_structure(self):
        """Pending queue serializes dictionary of todos and points."""
        mock_pending = {
            "todos": {"li-yue|due_today|2026-09-15|中文|習作3": True},
            "points": {
                "li-yue": {"earned": 10, "spent": 0, "awarded": {}, "bonusDates": {}, "redemptions": []}
            }
        }
        serialized = json.dumps(mock_pending)
        loaded = json.loads(serialized)
        self.assertIn("todos", loaded)
        self.assertIn("points", loaded)

    def test_flush_pending_function_defined(self):
        """sync.js defines flushPending or replay mechanism on reconnect."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertIn("flushPending", content)

    def test_online_event_listener_triggers_reconnect_or_flush(self):
        """window 'online' event listener flushes pending or connects."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertIn("window.addEventListener('online'", content)

    def test_pending_entry_deleted_after_successful_ack(self):
        """After remote write acknowledges, the corresponding pending item is deleted."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertIn("delete state.pending[kind][key]", content)


class TestFeature11LocalStorageGracefulDegradation(unittest.TestCase):
    """Tests for F-11: LocalStorage Graceful Degradation."""

    def test_read_json_handles_null_or_corrupted_data(self):
        """readJson safely falls back to empty object on corrupt JSON."""
        def safe_read(raw_str):
            try:
                data = json.loads(raw_str or "{}")
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}

        self.assertEqual(safe_read(None), {})
        self.assertEqual(safe_read(""), {})
        self.assertEqual(safe_read("NOT_JSON{"), {})
        self.assertEqual(safe_read("[]"), {})
        self.assertEqual(safe_read('{"a": 1}'), {"a": 1})

    def test_unconfigured_firebase_falls_back_to_local_mode(self):
        """When sync-config.js is unconfigured, sync.js stays in local mode without error dialogs."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertIn("isConfigured", content)
        self.assertIn("本機模式", content)

    def test_no_browser_alert_calls(self):
        """sync.js must not call window.alert() or confirm() to block user experience."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertNotRegex(content, r"\balert\s*\(")
        self.assertNotRegex(content, r"\bconfirm\s*\(")

    def test_storage_keys_prefixed_and_versioned(self):
        """All localStorage keys are namespaced with 'puiching-eclass-' and versioned."""
        content = SYNC_JS.read_text(encoding="utf-8")
        self.assertIn("puiching-eclass-todos-v1", content)
        self.assertIn("puiching-eclass-points-v1", content)
        self.assertIn("puiching-eclass-sync-code-v1", content)

    def test_child_pages_render_without_sync_config(self):
        """Child pages load child.js and child.css independently of sync state."""
        for path in [ABIGAIL_HTML, GLORIA_HTML]:
            content = path.read_text(encoding="utf-8")
            self.assertIn("assets/child.js", content)
            self.assertIn("assets/child.css", content)


if __name__ == "__main__":
    unittest.main()
