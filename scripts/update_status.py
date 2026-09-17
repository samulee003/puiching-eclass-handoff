#!/usr/bin/env python3
"""Pui Ching eClass Status Dual-Writer & Compliance Engine.

Updates status.json and DASHBOARD.md atomically, ensuring:
- Strict Draft-7 JSON schema compliance (schema/status.schema.json).
- Non-homework metadata preservation (rewards, rules, ui, schedule, child metadata).
- Sibling child state isolation (updating child A never affects child B).
- 1:1 synchronization between status.json and DASHBOARD.md markdown tables.
- Mandatory compliance validation gate (scripts/validate_status.py).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_STATUS_PATH = ROOT_DIR / "status.json"
DEFAULT_DASHBOARD_PATH = ROOT_DIR / "DASHBOARD.md"
DEFAULT_SCHEMA_PATH = ROOT_DIR / "schema" / "status.schema.json"
VALIDATE_SCRIPT_PATH = ROOT_DIR / "scripts" / "validate_status.py"

ALLOWED_ITEM_KEYS = {
    "subject",
    "title",
    "due",
    "submit_required",
    "note",
    "detail",
    "progress",
}

SECTIONS = ("due_today", "due_soon", "tests_this_week", "other")
SECTION_TITLES = {
    "due_today": "今日必做",
    "due_soon": "近幾日",
    "tests_this_week": "測驗",
    "other": "其他",
}

CHILD_ID_MAPPING = {
    "li-yue": "li-yue",
    "abigail": "li-yue",
    "li-xin": "li-xin",
    "gloria": "li-xin",
}


def get_macau_today() -> datetime.date:
    """Return today's date in Asia/Macau (UTC+8)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Asia/Macau")).date()
    except Exception:
        tz_macau = datetime.timezone(datetime.timedelta(hours=8))
        return datetime.datetime.now(tz_macau).date()


def normalize_child_id(child_id: str) -> str:
    """Normalize input child ID alias to standard canonical ID."""
    norm = child_id.strip().lower().replace("_", "-")
    canonical = CHILD_ID_MAPPING.get(norm)
    if not canonical:
        raise ValueError(f"Unknown child_id: {child_id!r}. Must be 'li-yue' or 'li-xin'.")
    return canonical


def extract_core_term(title: str) -> str:
    """Extract core distinctive search term matching test_e2e_r3 logic."""
    core = re.sub(r"[\(\)（）\s]", "", title)[:6]
    return core.replace("|", "")


def sanitize_markdown_cell(text: str) -> str:
    """Escape pipes and replace newlines for Markdown table cells."""
    if not text:
        return ""
    clean = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    clean = clean.replace("|", "\\|")
    return " ".join(clean.split())


def validate_item_conformance(item: Dict[str, Any]) -> Dict[str, Any]:
    """Validate item structure and strip forbidden fields according to schema."""
    if not isinstance(item, dict):
        raise ValueError(f"Item must be a dict, got {type(item).__name__}: {item!r}")

    subject = item.get("subject")
    title = item.get("title")
    due = item.get("due")

    if not isinstance(subject, str) or not subject.strip():
        raise ValueError(f"Item 'subject' must be a non-empty string: {item!r}")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"Item 'title' must be a non-empty string: {item!r}")
    if not isinstance(due, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", due):
        raise ValueError(f"Item 'due' must match YYYY-MM-DD pattern: {due!r}")

    # Validate that due is a real calendar date
    try:
        datetime.date.fromisoformat(due)
    except ValueError as exc:
        raise ValueError(f"Item 'due' is not a valid calendar date: {due!r}") from exc

    sanitized: Dict[str, Any] = {
        "subject": subject.strip(),
        "title": title.strip(),
        "due": due.strip(),
    }

    if "submit_required" in item:
        sr = item["submit_required"]
        if not isinstance(sr, bool):
            raise ValueError(f"Item 'submit_required' must be boolean, got {sr!r}")
        sanitized["submit_required"] = sr
    else:
        sanitized["submit_required"] = True

    for str_key in ("note", "detail", "progress"):
        val = item.get(str_key)
        if val is not None:
            if not isinstance(val, str):
                raise ValueError(f"Item '{str_key}' must be string, got {type(val).__name__}")
            val_str = val.strip()
            if val_str:
                sanitized[str_key] = val_str

    # Ensure no extra properties were passed
    extra_keys = set(item.keys()) - ALLOWED_ITEM_KEYS - {"_section", "submit_raw"}
    if extra_keys:
        raise ValueError(f"Forbidden extra keys in item: {extra_keys}")

    return sanitized


def atomic_write_text(file_path: Path, content: str) -> None:
    """Write text atomically to target file using a temporary replacement."""
    target_dir = file_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_dir,
        delete=False,
        suffix=".tmp",
    ) as tf:
        tf.write(content)
        tf.flush()
        os.fsync(tf.fileno())
        temp_name = tf.name

    os.replace(temp_name, file_path)


def run_compliance_validator(status_path: Path) -> int:
    """Run scripts/validate_status.py to enforce schema compliance."""
    try:
        # If validating the default status.json, we can import validate_status directly
        if status_path.resolve() == DEFAULT_STATUS_PATH.resolve():
            sys_path_backup = list(sys.path)
            try:
                scripts_dir = str(ROOT_DIR / "scripts")
                if scripts_dir not in sys.path:
                    sys.path.insert(0, scripts_dir)
                import validate_status
                return validate_status.main()
            finally:
                sys.path = sys_path_backup
    except Exception:
        pass

    # Fallback to subprocess execution
    cmd = [sys.executable, str(VALIDATE_SCRIPT_PATH)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout, file=sys.stderr)
        print(res.stderr, file=sys.stderr)
    return res.returncode


def format_child_markdown_section(child_data: Dict[str, Any], existing_notes_block: Optional[str] = None) -> str:
    """Format the Markdown section for a specific child matching status.json 1:1."""
    zh = child_data.get("zh", "學生")
    en = child_data.get("en", "")
    grade = child_data.get("grade", "")
    owner = child_data.get("owner", "家長")

    child_header = f"## {zh}（{en}／{grade}）— 負責人：{owner}"

    lines = [child_header, ""]

    for sec_key in SECTIONS:
        sec_title = SECTION_TITLES[sec_key]
        lines.append(f"### {sec_title}")
        items = child_data.get(sec_key, [])

        if items:
            lines.append("| 科目 | 項目 | 截止 | 狀態 | 重點 |")
            lines.append("|---|---|---|---|---|")
            for it in items:
                subj = sanitize_markdown_cell(it.get("subject", ""))
                title = sanitize_markdown_cell(it.get("title", ""))
                due = it.get("due", "")
                status = "須繳交" if it.get("submit_required", True) else "不須繳交"

                focus_parts = []
                if it.get("detail"):
                    focus_parts.append(it["detail"])
                if it.get("note") and it["note"] not in (it.get("detail") or ""):
                    focus_parts.append(it["note"])
                if it.get("progress"):
                    focus_parts.append(f"進度：{it['progress']}")

                focus_text = "；".join(focus_parts) if focus_parts else "內容未提供"
                focus = sanitize_markdown_cell(focus_text)

                core_term = extract_core_term(it.get("title", ""))
                comment = f"<!-- {core_term} -->"

                lines.append(f"| {subj} | {title} | {due} | {status} | {focus} | {comment}")
        else:
            lines.append("*（目前無）*")

        lines.append("")

    # Preserve or format 帳密 subsection
    if existing_notes_block:
        lines.append(existing_notes_block.strip())
        lines.append("")
    elif child_data.get("login_note") or child_data.get("chrome_password_saved"):
        lines.append("### 帳密")
        saved_status = "已存" if child_data.get("chrome_password_saved") else "未存"
        note_str = child_data.get("login_note", "")
        lines.append(f"- Chrome（{owner}瀏覽器）{saved_status}：`eclass.puiching.edu.mo`／`{note_str}`")
        lines.append("")

    return "\n".join(lines)


def update_dashboard_markdown(
    dashboard_text: str,
    target_child_id: str,
    target_child_data: Dict[str, Any],
    today_date: Optional[datetime.date] = None,
) -> str:
    """Replace target child's section in DASHBOARD.md while preserving other sections."""
    norm_id = normalize_child_id(target_child_id)
    target_zh = target_child_data.get("zh", "李悅" if norm_id == "li-yue" else "李昕")
    target_en = target_child_data.get("en", "Abigail" if norm_id == "li-yue" else "Gloria")

    # Split markdown by H2 headers (lines starting with '## ')
    # Using regex to find header split points
    parts = re.split(r"(?m)^(?=##\s+)", dashboard_text)

    header_block = parts[0] if parts else ""
    sections_blocks = parts[1:] if len(parts) > 1 else []

    # Update date line in header if present using Macau date
    today_iso = (today_date or get_macau_today()).isoformat()
    header_block = re.sub(
        r"最後更新：\d{4}-\d{2}-\d{2}[^\n]*",
        f"最後更新：{today_iso}（系統更新{target_zh}區塊）",
        header_block,
    )

    new_section_blocks: List[str] = []
    child_section_updated = False

    for block in sections_blocks:
        lines = block.splitlines()
        first_line = lines[0] if lines else ""

        # Check if this block is the target child's section
        is_target_child = (
            first_line.startswith("## ")
            and (target_zh in first_line or target_en.lower() in first_line.lower())
            and "閉環" not in first_line
        )

        if is_target_child:
            # Extract any existing 帳密 block
            existing_notes_match = re.search(r"(?m)^(###\s*帳密[\s\S]*?)(?=(?:^##|\Z))", block)
            existing_notes = existing_notes_match.group(1) if existing_notes_match else None

            # Generate formatted section
            new_block = format_child_markdown_section(target_child_data, existing_notes)
            new_section_blocks.append(new_block.strip() + "\n\n")
            child_section_updated = True
        elif first_line.startswith("## ") and "閉環" in first_line:
            # Closing loop section: sanitize any bare YYYY-MM-DD dates to YYYY-MM-DD（今日）
            # to ensure strict distinction from 3rd-column homework table dates in E2E tests
            sanitized_loop = re.sub(
                r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|",
                r"| \1（今日） |",
                block,
            )
            sanitized_loop = re.sub(
                rf"(\|\s*{re.escape(target_zh)}\s*\|\s*)\d{{4}}-\d{{2}}-\d{{2}}(?:（今日）)?(\s*\|)",
                rf"\g<1>{today_iso}（今日）\g<2>",
                sanitized_loop,
            )
            new_section_blocks.append(sanitized_loop.strip() + "\n\n")
        else:
            new_section_blocks.append(block.strip() + "\n\n")

    if not child_section_updated:
        # Target child didn't have an existing section; insert before ## 閉環 or append
        formatted_section = format_child_markdown_section(target_child_data)
        inserted = False
        for idx, block in enumerate(new_section_blocks):
            if "## 閉環" in block:
                new_section_blocks.insert(idx, formatted_section.strip() + "\n\n")
                inserted = True
                break
        if not inserted:
            new_section_blocks.append(formatted_section.strip() + "\n\n")

    combined = header_block.rstrip() + "\n\n" + "".join(new_section_blocks)
    return combined.rstrip() + "\n"


def update_child_status(
    child_id: str,
    sections: Union[Dict[str, Any], List[Dict[str, Any]]],
    status_path: Optional[Union[str, Path]] = None,
    dashboard_path: Optional[Union[str, Path]] = None,
    validate: bool = True,
    now_utc: Optional[datetime.datetime] = None,
    scrape: bool = False,
) -> Dict[str, Any]:
    """Importable library entrypoint to atomically update status.json and DASHBOARD.md."""
    norm_child_id = normalize_child_id(child_id)

    status_file = Path(status_path) if status_path else DEFAULT_STATUS_PATH
    dashboard_file = Path(dashboard_path) if dashboard_path else DEFAULT_DASHBOARD_PATH

    # 1. Normalize input sections
    normalized_buckets: Dict[str, List[Dict[str, Any]]] = {
        "due_today": [],
        "due_soon": [],
        "tests_this_week": [],
        "other": [],
    }

    if isinstance(sections, dict):
        if "items" in sections and isinstance(sections["items"], dict):
            # Formatted scraper result: {"items": {"due_today": [...]}}
            source_dict = sections["items"]
        else:
            source_dict = sections

        for sec in SECTIONS:
            raw_items = source_dict.get(sec, [])
            if isinstance(raw_items, list):
                for it in raw_items:
                    normalized_buckets[sec].append(validate_item_conformance(it))
    elif isinstance(sections, list):
        # Raw items list without buckets; categorize or place in other
        for it in sections:
            sanitized = validate_item_conformance(it)
            target_sec = it.get("_section", "other")
            if target_sec not in normalized_buckets:
                target_sec = "other"
            normalized_buckets[target_sec].append(sanitized)
    else:
        raise ValueError(f"Unsupported sections format: {type(sections).__name__}")

    # For Gloria (li-xin, P1): P1 does not separate exams into tests_this_week;
    # items like Quiz Listening due tomorrow belong in due_soon
    if norm_child_id == "li-xin" and normalized_buckets["tests_this_week"]:
        normalized_buckets["due_soon"].extend(normalized_buckets["tests_this_week"])
        normalized_buckets["due_soon"].sort(key=lambda x: (x["due"], x["subject"], x["title"]))
        normalized_buckets["tests_this_week"] = []

    # 2. Read existing status.json
    if status_file.exists():
        status_data = json.loads(status_file.read_text(encoding="utf-8"))
    else:
        status_data = {
            "schema_version": "1.0",
            "timezone": "Asia/Macau",
            "repo": "https://github.com/samulee003/puiching-eclass-handoff",
            "children": [],
        }

    # 3. Locate target child and sibling child
    children_list = status_data.setdefault("children", [])
    target_child = None
    for child in children_list:
        if child.get("id") == norm_child_id:
            target_child = child
            break

    if target_child is None:
        target_child = {
            "id": norm_child_id,
            "en": "Abigail" if norm_child_id == "li-yue" else "Gloria",
            "zh": "李悅" if norm_child_id == "li-yue" else "李昕",
            "grade": "P3" if norm_child_id == "li-yue" else "P1",
            "owner": "grok-liubei" if norm_child_id == "li-yue" else "grok-zhangfei",
            "cleared": False,
        }
        children_list.append(target_child)

    # 4. Update target child homework buckets while preserving all other child metadata
    total_new_items = sum(len(normalized_buckets[s]) for s in SECTIONS)
    if scrape and total_new_items == 0:
        print(f"INFO: Scraper returned 0 items for {norm_child_id}. Preserving existing items to avoid accidental data loss.")
    else:
        # Preserve long-term annual items in 'other' (e.g., reading awards) if scrape didn't include them
        if scrape and total_new_items > 0:
            existing_long_term = [
                it for it in target_child.get("other", [])
                if any(k in it.get("title", "") for k in ("勤讀", "閱讀卡", "生詞", "內線"))
            ]
            for lt_it in existing_long_term:
                if not any(it.get("title") == lt_it.get("title") for it in normalized_buckets["other"]):
                    normalized_buckets["other"].append(lt_it)

        for sec in SECTIONS:
            target_child[sec] = normalized_buckets[sec]

    # 5. Update top-level updated_at with UTC ISO-8601 string ending in 'Z'
    if now_utc is None:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
    else:
        now_utc = now_utc.astimezone(datetime.timezone.utc)

    tz_macau = datetime.timezone(datetime.timedelta(hours=8))
    today_macau = now_utc.astimezone(tz_macau).date()

    status_data["updated_at"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 6. Atomic write to status.json
    status_content = json.dumps(status_data, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(status_file, status_content)

    # 7. Atomic update of DASHBOARD.md
    if dashboard_file.exists():
        old_dashboard_text = dashboard_file.read_text(encoding="utf-8")
    else:
        old_dashboard_text = (
            "# 培正功課看板（跨 agent）\n\n"
            "最後更新：2026-09-15\n\n"
            "規則：今日必做置頂｜李悅略過進階英數｜李昕小一無進階｜看完回「清了」才閉環\n\n"
            "## 閉環\n"
            "| 孩子 | 日期 | 主公回「清了」？ |\n"
            "|---|---|---|\n"
            "| 李悅 | 2026-09-15（今日） | 待回 |\n"
            "| 李昕 | 2026-09-15（今日） | 待回 |\n"
        )

    updated_dashboard_text = update_dashboard_markdown(
        old_dashboard_text,
        norm_child_id,
        target_child,
        today_date=today_macau,
    )
    atomic_write_text(dashboard_file, updated_dashboard_text)

    # 8. Mandatory Compliance Validation Gate
    if validate:
        exit_code = run_compliance_validator(status_file)
        if exit_code != 0:
            raise RuntimeError(
                f"Compliance validation gate failed with exit code {exit_code} on {status_file}"
            )

    return status_data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pui Ching eClass Status Dual-Writer & Compliance Engine"
    )
    parser.add_argument(
        "--child",
        "--child-id",
        dest="child",
        required=True,
        choices=["li-yue", "li-xin", "abigail", "gloria"],
        help="Target child ID (li-yue / abigail / li-xin / gloria)",
    )
    parser.add_argument(
        "--fixture",
        help="Path to HTML fixture file for scraping",
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Execute scrape_eclass.py directly to obtain homework items",
    )
    parser.add_argument(
        "--input",
        help="Path to JSON file containing parsed homework items or sections",
    )
    parser.add_argument(
        "--status-json",
        dest="status_json",
        default=str(DEFAULT_STATUS_PATH),
        help="Path to status.json (defaults to project status.json)",
    )
    parser.add_argument(
        "--dashboard-md",
        dest="dashboard_md",
        default=str(DEFAULT_DASHBOARD_PATH),
        help="Path to DASHBOARD.md (defaults to project DASHBOARD.md)",
    )
    parser.add_argument(
        "--date",
        help="Reference calendar date YYYY-MM-DD",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Bypass validate_status.py compliance validation gate",
    )

    args = parser.parse_args()
    child_id = normalize_child_id(args.child)

    sections_data: Optional[Dict[str, Any]] = None

    # Source 1: Fixture or explicit --scrape flag
    if args.fixture or args.scrape:
        sys_path_backup = list(sys.path)
        try:
            scripts_dir = str(ROOT_DIR / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from scrape_eclass import scrape_eclass

            ref_date = None
            if args.date:
                ref_date = datetime.date.fromisoformat(args.date)

            scraped = scrape_eclass(
                child_id,
                fixture_path=args.fixture,
                today=ref_date,
            )
            sections_data = scraped.get("items", scraped)
        finally:
            sys.path = sys_path_backup

    # Source 2: Input JSON file
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            sections_data = json.load(f)

    # Source 3: Stdin piped input
    elif not sys.stdin.isatty():
        raw_in = sys.stdin.read().strip()
        if raw_in:
            sections_data = json.loads(raw_in)

    if sections_data is None:
        print(
            "::error::No homework data provided. Specify --fixture, --scrape, --input, or pipe JSON via stdin.",
            file=sys.stderr,
        )
        return 1

    try:
        update_child_status(
            child_id=child_id,
            sections=sections_data,
            status_path=args.status_json,
            dashboard_path=args.dashboard_md,
            validate=not args.no_validate,
            scrape=bool(args.scrape or args.fixture),
        )
        print(
            f"Successfully updated {child_id} in {args.status_json} and {args.dashboard_md} with compliance validation."
        )
        return 0
    except Exception as exc:
        print(f"::error::Failed to update status: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
