#!/usr/bin/env python3
"""Pui Ching eClass Homework Scraper & Rule Filtering Engine.

Features:
- Authentication via environment variables (ECLASS_USERNAME, ECLASS_PASSWORD, or child-specific).
- Offline / deterministic fixture mode (--fixture / --offline-html).
- Profile identity verification (李悅 for Abigail, 李昕 for Gloria).
- Error handling: explicit LOGIN_REQUIRED on auth failure / session timeout.
- Business filtering rules:
    * Abigail (P3, li-yue): 100% exclusion of subjects containing '進階'.
    * Gloria (P1, li-xin): No advanced stream filtering; identity verified.
    * Common: Ingest all tasks regardless of submit_required status.
    * Full detail extraction for oral/quiz/assessment items.
- Categorization into 4 sections: due_today, due_soon, tests_this_week, other.
- Output strictly conforms to schema/status.schema.json#/definitions/item.
"""

from __future__ import annotations

import argparse
import datetime
import html
from html.parser import HTMLParser
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

ECLASS_BASE_URL = "https://eclass.puiching.edu.mo/templates/"
ECLASS_LOGIN_URL = "https://eclass.puiching.edu.mo/login.php"
ECLASS_HOMEWORK_URL = "https://eclass.puiching.edu.mo/home/eService/homework/index.php"

STUDENT_MAPPING = {
    "li-yue": {"zh": "李悅", "en": "Abigail", "grade": "P3"},
    "abigail": {"zh": "李悅", "en": "Abigail", "grade": "P3"},
    "li-xin": {"zh": "李昕", "en": "Gloria", "grade": "P1"},
    "gloria": {"zh": "李昕", "en": "Gloria", "grade": "P1"},
}

TEST_KEYWORDS = (
    "quiz",
    "口試",
    "測驗",
    "默寫",
    "默字",
    "評估",
    "assessment",
    "exam",
    "oral",
)

LOGIN_FAILURE_INDICATORS = (
    "登入失敗",
    "登入逾時",
    "請先登入",
    "未登入",
    "使用者未登入",
    "重新輸入帳號密碼",
    "用戶名稱或密碼不正確",
    "invalid username or password",
    "會話已過期",
    "session timeout",
    "session expired",
    "請重新登入",
)


class EClassScrapeError(Exception):
    """Base exception for eClass scraping errors."""


class LoginRequiredError(EClassScrapeError):
    """Raised when authentication is missing, invalid, or session has expired."""


class IdentityMismatchError(EClassScrapeError):
    """Raised when the logged-in student profile does not match the target child."""


def get_macau_today() -> datetime.date:
    """Return today's date in Asia/Macau (UTC+8)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Asia/Macau")).date()
    except Exception:
        tz_macau = datetime.timezone(datetime.timedelta(hours=8))
        return datetime.datetime.now(tz_macau).date()


def canonicalize_date(date_str: str, default_year: Optional[int] = None) -> str:
    """Normalize various date formats to YYYY-MM-DD."""
    date_str = date_str.strip()
    if not date_str:
        raise ValueError("Empty date string")

    today = get_macau_today()
    if default_year is None:
        default_year = today.year

    # Check for relative keywords
    if any(k in date_str for k in ("今日", "今天", "today")):
        return today.isoformat()
    if any(k in date_str for k in ("明日", "明天", "tomorrow")):
        return (today + datetime.timedelta(days=1)).isoformat()
    if any(k in date_str for k in ("後天", "后天")):
        return (today + datetime.timedelta(days=2)).isoformat()

    # 1. Match YYYY-MM-DD or YYYY/MM/DD
    m1 = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", date_str)
    if m1:
        y, m, d = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        return datetime.date(y, m, d).isoformat()

    # 2. Match DD/MM/YYYY or DD-MM-YYYY (4-digit year at end)
    m2 = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", date_str)
    if m2:
        d, m, y = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        return datetime.date(y, m, d).isoformat()

    # 3. Match Chinese format with year: YYYY年M月D日
    m3 = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_str)
    if m3:
        y, m, d = int(m3.group(1)), int(m3.group(2)), int(m3.group(3))
        return datetime.date(y, m, d).isoformat()

    # 4. Match Chinese format without year: M月D日 (allows trailing day-of-week like (三) or times)
    m4 = re.search(r"(\d{1,2})月(\d{1,2})日", date_str)
    if m4:
        m, d = int(m4.group(1)), int(m4.group(2))
        return datetime.date(default_year, m, d).isoformat()

    # 5. Match MM/DD or MM-DD (e.g. 09/16, 9/16, 09-16)
    m5 = re.search(r"(?:^|[^\d])(\d{1,2})[/-](\d{1,2})(?:$|[^\d])", date_str)
    if m5:
        p1, p2 = int(m5.group(1)), int(m5.group(2))
        if 1 <= p1 <= 12 and 1 <= p2 <= 31:
            return datetime.date(default_year, p1, p2).isoformat()

    raise ValueError(f"Unable to parse date string: {date_str!r}")


class SimpleDOMParser(HTMLParser):
    """Robust HTML table & text extractor with complete nested table support."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: List[List[Dict[str, Any]]] = []
        self.table_stack: List[Dict[str, Any]] = []
        self.row_stack: List[Dict[str, Any]] = []
        self.cell_stack: List[Dict[str, Any]] = []

        self.in_detail = False
        self.in_btn = False
        self.full_text_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if t == "table":
            new_table = {"rows": [], "attrs": attr_dict}
            self.table_stack.append(new_table)
            self.tables.append(new_table["rows"])
        elif t == "tr":
            if self.table_stack:
                cur_t_id = id(self.table_stack[-1])
                # Close previous row in same table if not explicitly closed
                if self.row_stack and self.row_stack[-1]["table_id"] == cur_t_id:
                    self._close_row(self.row_stack[-1])
                new_row = {"cells": [], "attrs": attr_dict, "table_id": cur_t_id}
                self.row_stack.append(new_row)
                self.table_stack[-1]["rows"].append(new_row)
        elif t in ("th", "td"):
            if self.row_stack:
                cur_r_id = id(self.row_stack[-1])
                if self.cell_stack and self.cell_stack[-1]["row_id"] == cur_r_id:
                    self._close_cell(self.cell_stack[-1])
                new_cell = {
                    "text_parts": [],
                    "note_parts": [],
                    "detail_parts": [],
                    "is_th": (t == "th"),
                    "attrs": attr_dict,
                    "row_id": cur_r_id,
                }
                self.cell_stack.append(new_cell)

            cls = attr_dict.get("class", "").lower()
            if "detail-content" in cls:
                self.in_detail = True
            elif "btn-detail" in cls:
                self.in_btn = True
        elif t == "img":
            title_attr = html.unescape(attr_dict.get("title", "")).strip()
            alt_attr = html.unescape(attr_dict.get("alt", "")).strip()
            src_attr = attr_dict.get("src", "").lower()

            if "attach" in src_attr or title_attr in ("附件", "attachment") or alt_attr in ("附件", "attachment"):
                if self.cell_stack:
                    self.cell_stack[-1]["has_attachment"] = True

            candidate_text = title_attr if title_attr and title_attr not in ("附件", "attachment", "icon", "新", "下載", "view") else alt_attr
            if candidate_text and candidate_text not in ("附件", "attachment", "icon", "新", "下載", "view"):
                if self.cell_stack:
                    self.cell_stack[-1]["detail_parts"].append(candidate_text)
        else:
            cls = attr_dict.get("class", "").lower()
            if "detail-content" in cls:
                self.in_detail = True
            elif "btn-detail" in cls:
                self.in_btn = True

    def _close_cell(self, target_cell: Optional[Dict[str, Any]] = None) -> None:
        if not self.cell_stack:
            return
        cell = self.cell_stack.pop() if target_cell is None else target_cell
        if target_cell is not None and cell in self.cell_stack:
            self.cell_stack.remove(cell)

        raw_text = " ".join(cell["text_parts"])
        clean_text = html.unescape(" ".join(raw_text.split())).strip()
        clean_note = html.unescape(" ".join(" ".join(cell["note_parts"]).split())).strip() or None

        raw_detail_lines = []
        for part in cell["detail_parts"]:
            for line in part.splitlines():
                cl = html.unescape(" ".join(line.split())).strip()
                if cl:
                    raw_detail_lines.append(cl)
        clean_detail = " ".join(raw_detail_lines).strip() or None

        cell_data = {
            "text": clean_text,
            "note_text": clean_note,
            "detail": clean_detail,
            "has_attachment": cell.get("has_attachment", False),
            "is_th": cell["is_th"],
            "attrs": cell["attrs"],
        }
        for r in reversed(self.row_stack):
            if id(r) == cell["row_id"]:
                r["cells"].append(cell_data)
                break
        self.in_detail = False
        self.in_btn = False

    def _close_row(self, target_row: Optional[Dict[str, Any]] = None) -> None:
        if not self.row_stack:
            return
        row = self.row_stack.pop() if target_row is None else target_row
        if target_row is not None and row in self.row_stack:
            self.row_stack.remove(row)
        cur_r_id = id(row)
        while self.cell_stack and self.cell_stack[-1]["row_id"] == cur_r_id:
            self._close_cell(self.cell_stack[-1])

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("th", "td"):
            if self.cell_stack:
                self._close_cell()
        elif t == "tr":
            if self.row_stack:
                self._close_row()
        elif t == "table":
            if self.table_stack:
                cur_t_id = id(self.table_stack[-1])
                while self.row_stack and self.row_stack[-1]["table_id"] == cur_t_id:
                    self._close_row(self.row_stack[-1])
                self.table_stack.pop()
        elif t in ("div", "span", "p") and self.in_detail:
            self.in_detail = False
        elif t == "a" and self.in_btn:
            self.in_btn = False

    def handle_data(self, data: str) -> None:
        clean = data.strip()
        if clean:
            self.full_text_parts.append(clean)
        if self.cell_stack:
            self.cell_stack[-1]["text_parts"].append(data)
            if self.in_detail:
                self.cell_stack[-1]["detail_parts"].append(data)
            elif not self.in_btn and clean != "查看詳情":
                self.cell_stack[-1]["note_parts"].append(data)

    def get_full_text(self) -> str:
        return " ".join(self.full_text_parts)


COMMON_PUI_CHING_SUBJECTS = {
    "中文", "英文", "數學", "常識", "視覺藝術", "視藝", "音樂", "體育",
    "聖經", "電腦", "普通話", "圖書", "品德", "班主任", "跨學科", "自然",
    "Chinese", "English", "Mathematics", "Maths", "General Studies", "Science",
    "Music", "Visual Arts", "PE", "P.E.", "Bible", "Computer",
}


def parse_homework_table_rows(tables: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Parse extracted tables into standardized raw homework item dictionaries."""
    raw_items: List[Dict[str, Any]] = []
    seen_signatures = set()

    print(f"DEBUG: Total tables found: {len(tables)}")
    for i, t in enumerate(tables):
        if not t:
            continue
        first_rows = [" | ".join(c.get("text", "")[:20] for c in r.get("cells", [])[:6]) for r in t[:3]]
        # Print diagnostic if matching potential homework content
        matches_kw = any(
            any(any(k in c.get("text", "") for k in ("科目", "學科", "家課", "功課", "期限", "截止", "繳交", "課題", "中文", "英文", "數學")) for c in r.get("cells", []))
            for r in t
        )
        if matches_kw or len(t) > 3:
            print(f"DEBUG Table {i} ({len(t)} rows): {first_rows}")

    for table in tables:
        if not table:
            continue

        header_indices: Dict[str, int] = {}
        header_row_index = -1

        # 1. Detect headers in any row
        for r_idx, row_obj in enumerate(table):
            row_cells = row_obj.get("cells", [])
            cell_texts = [c.get("text", "") for c in row_cells]

            # Check if this row is a header row
            has_subject = any("科目" in t or "學科" in t or t.lower() == "subject" for t in cell_texts)
            has_other_col = any(
                any(k in t for k in ("截止", "期限", "限期", "繳交", "內容", "標題", "課題", "家課", "功課", "要求", "due", "title"))
                for t in cell_texts
            )

            # Also check if row has th cells
            is_th_header = any(c.get("is_th") for c in row_cells) and len(row_cells) >= 3

            if (has_subject and has_other_col) or (is_th_header and not header_indices):
                header_row_index = r_idx
                for col_idx, cell in enumerate(row_cells):
                    txt = cell["text"].strip()
                    txt_lower = txt.lower()
                    if "組別" in txt or "班別" in txt:
                        header_indices["subject_group"] = col_idx
                    elif "科目" in txt or txt == "學科" or "學科" in txt or txt_lower == "subject":
                        if "subject" not in header_indices or "組別" not in txt:
                            header_indices["subject"] = col_idx
                    elif any(k in txt for k in ("派發", "發布", "發佈", "給予", "開始")):
                        header_indices["issue_date"] = col_idx
                    elif any(k in txt for k in ("限期", "截止", "期限", "交課日期", "繳交日期", "due")):
                        header_indices["due"] = col_idx
                    elif any(k in txt for k in ("繳交", "狀態", "要求", "submit", "方式")):
                        header_indices["submit"] = col_idx
                    elif any(k in txt for k in ("備註", "說明", "note", "附件")):
                        header_indices["note"] = col_idx
                    elif any(k in txt for k in ("詳情", "detail")):
                        header_indices["detail"] = col_idx
                    elif any(k in txt for k in ("項目", "標題", "功課", "名稱", "課題")) or ("內容" in txt and "詳情" not in txt):
                        header_indices["title"] = col_idx
                    elif "日期" in txt and "due" not in header_indices and "issue_date" not in header_indices:
                        header_indices["due"] = col_idx
                break

        # Fallback column mapping if no explicit header row was identified
        data_rows: List[Dict[str, Any]] = []
        if header_row_index >= 0:
            data_rows = table[header_row_index + 1:]
        else:
            data_rows = table
            first_len = len(data_rows[0].get("cells", [])) if data_rows else 0
            if first_len >= 3:
                header_indices = {
                    "subject": 0,
                    "title": 1,
                    "due": 2,
                    "submit": 3 if first_len > 3 else -1,
                    "note": 4 if first_len > 4 else -1,
                    "detail": 5 if first_len > 5 else -1,
                }

        # Process data rows
        for r_idx, row_obj in enumerate(data_rows):
            cells = row_obj.get("cells", [])
            row_attrs = row_obj.get("attrs", {})
            if not cells:
                continue

            if len(data_rows) > 5:
                print(f"DEBUG ROW {r_idx} (len {len(cells)}): {[c.get('text', '') for c in cells]}")

            item_data: Dict[str, Any] = {}

            # 1. Attribute matching by cell class and sub-fields
            for cell in cells:
                cls = cell.get("attrs", {}).get("class", "").lower()
                txt = cell.get("text", "")
                if "subject" in cls:
                    item_data["subject"] = txt
                elif "title" in cls:
                    item_data["title"] = txt
                elif "due" in cls:
                    item_data["due"] = txt
                elif "submit" in cls or "status" in cls:
                    item_data["submit_raw"] = txt
                elif "note" in cls:
                    item_data["note"] = cell.get("note_text") or txt
                    if cell.get("detail"):
                        item_data["detail"] = cell["detail"]
                elif "detail" in cls:
                    item_data["detail"] = cell.get("detail") or txt

            # 2. Attribute matching by column index
            def get_col(col_name: str) -> str:
                idx = header_indices.get(col_name, -1)
                if 0 <= idx < len(cells):
                    return cells[idx]["text"]
                return ""

            if "subject" not in item_data or not item_data["subject"]:
                item_data["subject"] = get_col("subject") or get_col("subject_group")
            if "title" not in item_data or not item_data["title"]:
                item_data["title"] = get_col("title")
            if "due" not in item_data or not item_data["due"]:
                item_data["due"] = get_col("due") or row_attrs.get("data-due", "")
            if "submit_raw" not in item_data or not item_data["submit_raw"]:
                item_data["submit_raw"] = get_col("submit")
            if "note" not in item_data or not item_data["note"]:
                note_col = header_indices.get("note", -1)
                if 0 <= note_col < len(cells):
                    item_data["note"] = cells[note_col].get("note_text") or cells[note_col]["text"]
                    if cells[note_col].get("detail"):
                        item_data["detail"] = cells[note_col]["detail"]
            if "detail" not in item_data or not item_data["detail"]:
                detail_col = header_indices.get("detail", -1)
                if 0 <= detail_col < len(cells) and cells[detail_col].get("detail"):
                    item_data["detail"] = cells[detail_col].get("detail") or cells[detail_col]["text"]

            # Also check title cell or any other cell for embedded detail (e.g. img[title] tooltips)
            if "detail" not in item_data or not item_data["detail"]:
                title_col = header_indices.get("title", -1)
                if 0 <= title_col < len(cells) and cells[title_col].get("detail"):
                    item_data["detail"] = cells[title_col]["detail"]
                else:
                    for c in cells:
                        if c.get("detail"):
                            item_data["detail"] = c["detail"]
                            break

            # If item has attachment and note doesn't mention it, record attachment
            if any(c.get("has_attachment") for c in cells):
                cur_note = item_data.get("note") or ""
                if "附件" not in cur_note:
                    item_data["note"] = f"{cur_note} 附件".strip() if cur_note else "附件"

            # Heuristic fallback if subject or due missing from standard column mapping
            if not item_data.get("subject") or not item_data.get("due"):
                for c in cells:
                    c_txt = c.get("text", "").strip()
                    if not item_data.get("subject"):
                        if c_txt in COMMON_PUI_CHING_SUBJECTS or c_txt.startswith("進階"):
                            item_data["subject"] = c_txt
                    if not item_data.get("due"):
                        try:
                            _ = canonicalize_date(c_txt)
                            item_data["due"] = c_txt
                        except ValueError:
                            pass

            subject = item_data.get("subject", "").strip()
            # Strip grade/class prefixes like 'P3B 中文' -> '中文', 'P1E 英文' -> '英文'
            subject = re.sub(r"^P\d[A-Z]?\s*", "", subject).strip()
            title = item_data.get("title", "").strip()
            due_raw = item_data.get("due", "").strip()

            if not subject or not title or not due_raw:
                if len(data_rows) > 5:
                    print(f"DEBUG ROW {r_idx} SKIPPED (missing required): subject={subject!r}, title={title!r}, due_raw={due_raw!r}")
                continue

            try:
                due_iso = canonicalize_date(due_raw)
            except ValueError as ve:
                if len(data_rows) > 5:
                    print(f"DEBUG ROW {r_idx} SKIPPED (invalid date {due_raw!r}): {ve}")
                continue

            submit_str = item_data.get("submit_raw", "").strip()
            note_str = item_data.get("note", "") or ""
            combined_desc = f"{title} {note_str} {submit_str}"

            if any(k in combined_desc for k in ("不須", "不用", "免交", "不需要", "不用默寫", "不用交", "不需繳交", "免繳交")):
                submit_required = False
            elif any(k in submit_str for k in ("不須", "不用", "免交", "不需要", "no")):
                submit_required = False
            elif any(k in submit_str for k in ("須繳交", "要交", "需要", "yes", "必須")):
                submit_required = True
            else:
                submit_required = True

            note = item_data.get("note", "").strip() or None
            detail = item_data.get("detail", "").strip() or None

            # Detect progress patterns
            progress = None
            for field_txt in (detail or "", note or "", title):
                prog_match = re.search(r"(?:進度|progress)[：:\s]*(\d+/\d+)", field_txt, re.I)
                if prog_match:
                    progress = prog_match.group(1)
                    break
                if any(k in field_txt for k in ("勤讀", "閱讀卡", "獎勵")):
                    p_match = re.search(r"(\d+/\d+)", field_txt)
                    if p_match:
                        progress = p_match.group(1)
                        break

            if detail and progress and detail.strip() in (progress, f"進度：{progress}", f"進度:{progress}"):
                detail = None

            if detail and detail.strip() == title.strip():
                detail = None

            sig = (subject, title, due_iso)
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            raw_item: Dict[str, Any] = {
                "subject": subject,
                "title": title,
                "due": due_iso,
                "submit_required": submit_required,
            }
            if note:
                raw_item["note"] = note
            if detail:
                raw_item["detail"] = detail
            if progress:
                raw_item["progress"] = progress

            if row_attrs.get("data-section"):
                raw_item["_section"] = row_attrs["data-section"]

            raw_items.append(raw_item)

    return raw_items


def verify_identity_and_auth(
    full_text: str,
    child_id: str,
    html_content: Optional[str] = None,
) -> Tuple[bool, str]:
    """Verify login status and child profile identity.

    Raises:
        LoginRequiredError: When login failed, session expired, or credentials required.
        IdentityMismatchError: When logged-in student doesn't match requested child.
    """
    lower_text = full_text.lower()
    raw_html_lower = (html_content or "").lower()

    # 1. Check explicit login failure indicators
    for indicator in LOGIN_FAILURE_INDICATORS:
        if indicator in lower_text or (raw_html_lower and indicator in raw_html_lower):
            raise LoginRequiredError(
                f"LOGIN_REQUIRED: eClass session expired or authentication failed ({indicator})"
            )

    # 2. Check for login form or login redirection when no student is logged in
    has_student = ("李悅" in full_text or "李昕" in full_text)
    if not has_student:
        combined_lower = f"{lower_text} {raw_html_lower}"
        is_login_page = (
            "login.php" in combined_lower
            or "/templates/login.php" in combined_lower
            or ("user_name" in combined_lower and "user_password" in combined_lower)
            or ("username" in combined_lower and "password" in combined_lower and "登入" in combined_lower)
            or ('type="password"' in combined_lower or "type='password'" in combined_lower)
            or ('name="user_password"' in combined_lower or 'name="password"' in combined_lower)
            or ("請先登入" in combined_lower or "登入系統" in combined_lower)
        )
        if is_login_page:
            raise LoginRequiredError("LOGIN_REQUIRED: Login page detected. Authentication required.")

    norm_child_id = child_id.lower().replace("_", "-")
    expected_meta = STUDENT_MAPPING.get(norm_child_id)
    if not expected_meta:
        raise ValueError(f"Unknown child_id: {child_id}. Must be 'li-yue' or 'li-xin'.")

    expected_zh = expected_meta["zh"]

    has_target = expected_zh in full_text
    other_zh = "李昕" if expected_zh == "李悅" else "李悅"
    has_other = other_zh in full_text

    if not has_target:
        if has_other:
            raise IdentityMismatchError(
                f"IDENTITY_MISMATCH: Expected student {expected_zh} for {child_id}, but found {other_zh}"
            )
        raise IdentityMismatchError(
            f"IDENTITY_MISMATCH: Student {expected_zh} profile was not found on the page."
        )

    return True, expected_zh


def filter_and_categorize(
    raw_items: List[Dict[str, Any]],
    child_id: str,
    today: Optional[datetime.date] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Apply Abigail/Gloria filtering rules and categorize into 4 canonical sections."""
    if today is None:
        today = get_macau_today()

    norm_child_id = child_id.lower().replace("_", "-")
    is_abigail = norm_child_id in ("li-yue", "abigail")

    filtered_items: List[Dict[str, Any]] = []

    for item in raw_items:
        # Rule 1: Abigail 100% exclusion of subjects containing '進階'
        if is_abigail and "進階" in item["subject"]:
            continue

        # Rule 2: Oral/Quiz full detail extraction
        # If oral/quiz item lacks detail, provide explicit fallback '詳情未取到'
        is_oral_quiz = any(
            kw in item["title"].lower() or kw in item["subject"].lower()
            for kw in TEST_KEYWORDS
        )
        if is_oral_quiz:
            if not item.get("detail"):
                item["detail"] = "詳情未取到"

        filtered_items.append(item)

    # Bucket into 4 sections
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "due_today": [],
        "due_soon": [],
        "tests_this_week": [],
        "other": [],
    }

    for item in filtered_items:
        # Support explicit section hint if present, and remove internal field
        explicit_sec = item.pop("_section", None)
        if explicit_sec in buckets:
            buckets[explicit_sec].append(item)
            continue

        due_date = datetime.date.fromisoformat(item["due"])
        diff_days = (due_date - today).days

        is_test = any(
            kw in item["title"].lower() or kw in item["subject"].lower()
            for kw in TEST_KEYWORDS
        )

        if diff_days <= 0:
            # Overdue or due today -> due_today
            buckets["due_today"].append(item)
        elif is_test and 1 <= diff_days <= 7:
            # Tests/quizzes within 7 days -> tests_this_week
            buckets["tests_this_week"].append(item)
        elif 1 <= diff_days <= 7:
            # Regular items within 1-7 days -> due_soon
            buckets["due_soon"].append(item)
        else:
            # Future items (>7 days) or long term -> other
            buckets["other"].append(item)

    # Sort items chronologically by due date within each section
    for section_name in buckets:
        buckets[section_name].sort(key=lambda x: (x["due"], x["subject"], x["title"]))

    return buckets


def parse_homework_html(
    html_content: str,
    child_id: str,
    today: Optional[datetime.date] = None,
) -> Dict[str, Any]:
    """Parse raw HTML content, verify identity, filter, categorize, and validate schema.

    Returns:
        {
            "child_id": "li-yue" | "li-xin",
            "student_name": str,
            "items": {
                "due_today": [...],
                "due_soon": [...],
                "tests_this_week": [...],
                "other": [...]
            },
            # Top-level section aliases for convenience
            "due_today": [...],
            "due_soon": [...],
            "tests_this_week": [...],
            "other": [...]
        }
    """
    parser = SimpleDOMParser()
    parser.feed(html_content)

    full_text = parser.get_full_text()
    _, verified_name = verify_identity_and_auth(
        full_text, child_id, html_content=html_content
    )

    raw_items = parse_homework_table_rows(parser.tables)
    buckets = filter_and_categorize(raw_items, child_id, today)

    norm_child_id = "li-yue" if child_id.lower() in ("li-yue", "abigail") else "li-xin"

    result = {
        "child_id": norm_child_id,
        "student_name": verified_name,
        "items": buckets,
        "due_today": buckets["due_today"],
        "due_soon": buckets["due_soon"],
        "tests_this_week": buckets["tests_this_week"],
        "other": buckets["other"],
    }
    return result


class EClassScraper:
    """Manages eClass HTTP session, login, and scraping."""

    def __init__(
        self,
        child_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        norm_child = child_id.lower().replace("_", "-")
        self.child_id = "li-yue" if norm_child in ("li-yue", "abigail") else "li-xin"

        # Ingest credentials exclusively from parameters or environment variables
        if self.child_id == "li-yue":
            self.username = (
                username
                or os.environ.get("ECLASS_LI_YUE_USERNAME")
                or os.environ.get("ECLASS_USERNAME")
            )
            self.password = (
                password
                or os.environ.get("ECLASS_LI_YUE_PASSWORD")
                or os.environ.get("ECLASS_PASSWORD")
            )
        else:
            self.username = (
                username
                or os.environ.get("ECLASS_LI_XIN_USERNAME")
                or os.environ.get("ECLASS_USERNAME")
            )
            self.password = (
                password
                or os.environ.get("ECLASS_LI_XIN_PASSWORD")
                or os.environ.get("ECLASS_PASSWORD")
            )

        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.opener.addheaders = [
            (
                "User-Agent",
                (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            ),
            ("Accept-Language", "zh-TW,zh-HK;q=0.9,zh;q=0.8,en;q=0.7"),
        ]

    def login(self) -> None:
        """Authenticate against eClass portal."""
        if not self.username or not self.password:
            raise LoginRequiredError(
                f"LOGIN_REQUIRED: Credentials missing for {self.child_id}. "
                "Set ECLASS_USERNAME/ECLASS_PASSWORD or child-specific environment variables."
            )

        # 1. Fetch initial portal page to acquire cookies and extract CSRF token (securetoken)
        secure_token = ""
        try:
            req_init = urllib.request.Request(ECLASS_BASE_URL, headers={"User-Agent": self.opener.addheaders[0][1]})
            with self.opener.open(req_init, timeout=15) as resp:
                init_html = resp.read().decode("utf-8", errors="replace")
                m = re.search(r'name=["\']securetoken["\']\s+value=["\']([^"\']+)["\']', init_html, re.I)
                if not m:
                    m = re.search(r'value=["\']([^"\']+)["\']\s+name=["\']securetoken["\']', init_html, re.I)
                if m:
                    secure_token = m.group(1)
        except Exception:
            pass

        # 2. Build payload adhering to eClass form requirements
        payload_dict = {
            "UserLogin": self.username,
            "UserPassword": self.password,
            "home_page": "1",
            "url": "/templates/index.php?err=1&DirectLink=",
            "submit": "登入",
            "username": self.username,
            "password": self.password,
        }
        if secure_token:
            payload_dict["securetoken"] = secure_token

        payload = urllib.parse.urlencode(payload_dict).encode("utf-8")

        req = urllib.request.Request(
            ECLASS_LOGIN_URL,
            data=payload,
            method="POST",
            headers={
                "Referer": ECLASS_BASE_URL,
                "Origin": "https://eclass.puiching.edu.mo",
            }
        )
        try:
            with self.opener.open(req, timeout=15) as resp:
                resp_text = resp.read().decode("utf-8", errors="replace")
                final_url = resp.geturl()
                print(f"DEBUG [{self.child_id}]: Login final URL: {final_url}")
                print(f"DEBUG [{self.child_id}]: Cookies: {[c.name for c in self.cookie_jar]}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LoginRequiredError(f"LOGIN_REQUIRED: eClass connection failed ({exc})") from exc

        # Check for authentication failure or error redirect
        if "err=1" in final_url or "err=" in final_url:
            raise LoginRequiredError(
                f"LOGIN_REQUIRED: Authentication failed on portal for {self.child_id} (err=1)"
            )

        for indicator in LOGIN_FAILURE_INDICATORS:
            if indicator in resp_text.lower():
                raise LoginRequiredError(
                    f"LOGIN_REQUIRED: Authentication failed on portal ({indicator})"
                )

    def fetch_homework_page(self) -> str:
        """Fetch the homework list page."""
        candidate_urls = [
            ECLASS_HOMEWORK_URL,
            "https://eclass.puiching.edu.mo/home/eService/homework/",
            "https://eclass.puiching.edu.mo/templates/homework/index.php",
        ]
        last_exc = None
        for url in candidate_urls:
            req = urllib.request.Request(url, method="GET")
            try:
                with self.opener.open(req, timeout=15) as resp:
                    final_url = resp.geturl()
                    # If redirected to login page or root without session
                    body = resp.read().decode("utf-8", errors="replace")
                    print(f"DEBUG [{self.child_id}]: Fetched {final_url} (length: {len(body)})")
                    title_m = re.search(r"<title>(.*?)</title>", body, re.I)
                    print(f"DEBUG [{self.child_id}]: Page title: {title_m.group(1) if title_m else 'No title'}")
                    table_count = len(re.findall(r"<table", body, re.I))
                    print(f"DEBUG [{self.child_id}]: Table tags count: {table_count}")



                    # Check for frames/iframes
                    frames = re.findall(r'<i?frame[^>]+src=["\']([^"\']+)["\']', body, re.I)
                    if frames:
                        print(f"DEBUG [{self.child_id}]: Found frames: {frames}")
                        for f_src in frames:
                            if any(k in f_src.lower() for k in ("homework", "list", "content", "main", "view")):
                                full_frame_url = urllib.parse.urljoin(final_url, f_src)
                                print(f"DEBUG [{self.child_id}]: Fetching frame {full_frame_url}")
                                try:
                                    f_req = urllib.request.Request(full_frame_url, method="GET")
                                    with self.opener.open(f_req, timeout=15) as f_resp:
                                        f_body = f_resp.read().decode("utf-8", errors="replace")
                                        if len(re.findall(r"<table", f_body, re.I)) > 0:
                                            body += "\n" + f_body
                                except Exception as e:
                                    print(f"DEBUG [{self.child_id}]: Frame fetch error: {e}")
                    return body
            except LoginRequiredError:
                raise
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_exc = exc
                continue

        raise LoginRequiredError(
            f"LOGIN_REQUIRED: Failed to fetch homework page ({last_exc})"
        )

    def scrape(self, today: Optional[datetime.date] = None) -> Dict[str, Any]:
        """Perform full scrape workflow: login -> fetch -> parse -> filter -> categorize."""
        self.login()
        html_page = self.fetch_homework_page()
        return parse_homework_html(html_page, self.child_id, today)


def scrape_eclass(
    child_id: str,
    *,
    username: Optional[str] = None,
    password: Optional[str] = None,
    fixture_path: Optional[str] = None,
    today: Optional[datetime.date] = None,
) -> Dict[str, Any]:
    """High-level function to scrape eClass or parse an offline fixture.

    Parameters:
        child_id: 'li-yue' (Abigail) or 'li-xin' (Gloria)
        username: optional override for eClass username
        password: optional override for eClass password
        fixture_path: optional path to local HTML fixture file for offline testing
        today: reference calendar date (defaults to Macau today)

    Returns:
        Structured dictionary conforming to M2/M3 interface contracts.
    """
    if fixture_path:
        with open(fixture_path, "r", encoding="utf-8") as f:
            html_text = f.read()
        return parse_homework_html(html_text, child_id, today)

    scraper = EClassScraper(child_id, username=username, password=password)
    return scraper.scrape(today)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pui Ching eClass Homework Scraper & Rule Filtering Engine"
    )
    parser.add_argument(
        "--child",
        "--child-id",
        dest="child",
        required=True,
        choices=["li-yue", "li-xin", "abigail", "gloria"],
        help="Target child ID (li-yue or li-xin)",
    )
    parser.add_argument(
        "--fixture",
        "--offline-html",
        dest="fixture",
        help="Path to offline HTML fixture file for deterministic testing",
    )
    parser.add_argument(
        "--output",
        default="json",
        help="Output destination ('json' to stdout, or file path)",
    )
    parser.add_argument(
        "--date",
        help="Reference calendar date YYYY-MM-DD (defaults to today in Asia/Macau)",
    )
    parser.add_argument(
        "--username",
        help="eClass username override (defaults to environment variables)",
    )
    parser.add_argument(
        "--password",
        help="eClass password override (defaults to environment variables)",
    )

    args = parser.parse_args()

    ref_date = None
    if args.date:
        try:
            ref_date = datetime.date.fromisoformat(args.date)
        except ValueError:
            print(f"::error::Invalid date format: {args.date!r}. Expected YYYY-MM-DD", file=sys.stderr)
            return 1

    try:
        data = scrape_eclass(
            args.child,
            username=args.username,
            password=args.password,
            fixture_path=args.fixture,
            today=ref_date,
        )
    except LoginRequiredError as exc:
        msg = str(exc)
        if not msg.startswith("LOGIN_REQUIRED:"):
            msg = f"LOGIN_REQUIRED: {msg}"
        print(msg, file=sys.stderr)
        return 1
    except IdentityMismatchError as exc:
        msg = str(exc)
        if not msg.startswith("IDENTITY_MISMATCH:"):
            msg = f"IDENTITY_MISMATCH: {msg}"
        print(msg, file=sys.stderr)
        return 1
    except EClassScrapeError as exc:
        msg = str(exc)
        if not msg.startswith("SCRAPE_ERROR:"):
            msg = f"SCRAPE_ERROR: {msg}"
        print(msg, file=sys.stderr)
        return 1
    except Exception as exc:
        msg = str(exc)
        if not msg.startswith("UNEXPECTED_ERROR:"):
            msg = f"UNEXPECTED_ERROR: {msg}"
        print(msg, file=sys.stderr)
        return 1

    # Output formatting
    formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output == "json":
        print(formatted_json)
    else:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(formatted_json)
            print(f"Successfully wrote output to {args.output}")
        except OSError as exc:
            print(f"::error::Failed to write output to {args.output}: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
