"""Parses LateRoundDraftGuide2026_[date].pdf into structured player notes.

Strategy:
  1. Read the CONTENTS page to find the starting page number of each of the
     three sections we care about (Players to Target / Players to Avoid /
     Late-Round Dart Throws), plus the section that follows Dart Throws
     (Cheat Sheets) to bound its end. This is done dynamically rather than
     hardcoding page numbers, since the guide is re-uploaded weekly and
     page counts shift.
  2. Concatenate the extracted text of every page in a section's range.
  3. Split that text into individual player entries on the recurring
     header pattern: "{Player}, {Pos}, {Team}\nAdded {date} | Confidence
     Level: {n}".

Note: this is regex-driven against prose text, not a stable schema. Spot
check output after each weekly re-run in case the guide's formatting shifts.
"""

import re

import pdfplumber

SECTIONS = ["Players to Target", "Players to Avoid", "Late-Round Dart Throws"]
SECTION_END_MARKER = "Cheat Sheets"

CONTENTS_LINE_RE = re.compile(r"^(.*?)\s*\.{3,}\s*(\d+)\s*$")
ENTRY_HEADER_RE = re.compile(
    r"(?P<player>[A-Z][^\n,]+), (?P<position>QB|RB|WR|TE|DST|K), (?P<team>[^\n]+)\n"
    r"Added (?P<date>[A-Za-z]+ \d{1,2}) \| Confidence Level: (?P<confidence>\d+)\n"
)
FOOTER_RE = re.compile(r"\n?Late-Round Fantasy Football: \d{4} Draft Guide \d+\n?")


def find_contents_page(pdf):
    for i, page in enumerate(pdf.pages[:6]):
        text = page.extract_text() or ""
        if text.strip().upper().startswith("CONTENTS"):
            return i, text
    raise ValueError("Could not locate CONTENTS page in first 6 pages")


def parse_section_bounds(contents_text):
    """Returns {section_name: printed_page_number} for every TOC line."""
    bounds = {}
    for line in contents_text.splitlines():
        m = CONTENTS_LINE_RE.match(line.strip())
        if m:
            name = m.group(1).strip().lstrip(".").strip()
            bounds[name] = int(m.group(2))
    return bounds


def section_page_range(bounds, section_name, next_section_name, page_offset):
    start_printed = bounds[section_name]
    end_printed = bounds[next_section_name] - 1
    start_idx = start_printed - page_offset
    end_idx = end_printed - page_offset
    return start_idx, end_idx


def extract_section_text(pdf, start_idx, end_idx):
    parts = []
    for i in range(start_idx, end_idx + 1):
        parts.append(pdf.pages[i].extract_text() or "")
    return "\n".join(parts)


def parse_entries(section_text, section_name):
    matches = list(ENTRY_HEADER_RE.finditer(section_text))
    entries = []
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(section_text)
        body = FOOTER_RE.sub("\n", section_text[body_start:body_end]).strip()
        entries.append({
            "player": m.group("player").strip(),
            "position": m.group("position"),
            "team": m.group("team").strip(),
            "date_added": m.group("date"),
            "confidence": int(m.group("confidence")),
            "section": section_name,
            "note": body,
        })
    return entries


def load_notes(path):
    with pdfplumber.open(path) as pdf:
        contents_idx, contents_text = find_contents_page(pdf)
        printed_page_at_contents = int(
            (pdf.pages[contents_idx].extract_text() or "").strip().splitlines()[-1]
        )
        page_offset = printed_page_at_contents - (contents_idx + 1)

        bounds = parse_section_bounds(contents_text)

        all_entries = []
        for idx, section_name in enumerate(SECTIONS):
            next_name = SECTIONS[idx + 1] if idx + 1 < len(SECTIONS) else SECTION_END_MARKER
            start_idx, end_idx = section_page_range(bounds, section_name, next_name, page_offset)
            section_text = extract_section_text(pdf, start_idx, end_idx)
            all_entries.extend(parse_entries(section_text, section_name))

        return all_entries, bounds


if __name__ == "__main__":
    import sys
    import json

    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\T991158\Downloads\LateRoundDraftGuide2026_August26.pdf"
    entries, bounds = load_notes(path)
    print(f"section bounds (printed page numbers): {bounds}")
    print(f"parsed {len(entries)} player entries")
    by_section = {}
    for e in entries:
        by_section.setdefault(e["section"], 0)
        by_section[e["section"]] += 1
    print("counts by section:", by_section)
    with open("pdf_entries_sample.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print("full output written to pdf_entries_sample.json")
