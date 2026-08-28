"""Attaches the guide's qualitative notes (Target/Avoid/Dart Throw) to players."""

from crosswalk import normalize_name
from ingestion.pdf_parser import load_notes


def build_notes_index(pdf_path):
    entries, _ = load_notes(pdf_path)
    index = {}
    for e in entries:
        key = normalize_name(e["player"])
        index.setdefault(key, []).append(e)
    return index


def tags_for_player(notes_index, player_name):
    """Lightweight tag list for the polling payload - no note text."""
    entries = notes_index.get(normalize_name(player_name), [])
    return [
        {"section": e["section"], "confidence": e["confidence"], "date_added": e["date_added"]}
        for e in entries
    ]


def note_for_player(notes_index, player_name):
    """Full note text, fetched on demand (not included in the polling payload)."""
    return notes_index.get(normalize_name(player_name), [])
