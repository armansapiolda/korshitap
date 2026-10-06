"""Move-in date parsing for the cold search.

`move_in_date` is stored as free text: onboarding button labels
("В течение недели", "Бір ай ішінде"), seed strings ("с 10 сентября",
"свободно сейчас") or anything a user typed. This module turns such text into
a window of days counted from today so two people can be compared.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Tuple

# Window = (earliest_day, latest_day) counted from today. None = flexible.
Window = Tuple[int, int]

# How far apart two windows may be and still be considered compatible.
DATE_TOLERANCE_DAYS = 14

_MONTHS = [
    (r"январ|қаңтар", 1),
    (r"феврал|ақпан", 2),
    (r"март|наурыз", 3),
    (r"апрел|сәуір", 4),
    (r"ма[йя]\b|мамыр", 5),
    (r"июн|маусым", 6),
    (r"июл|шілде", 7),
    (r"август|тамыз", 8),
    (r"сентябр|қыркүйек", 9),
    (r"октябр|қазан", 10),
    (r"ноябр|қараша", 11),
    (r"декабр|желтоқсан", 12),
]

# Order matters: more specific phrases first.
_RELATIVE = [
    (r"просто ищу|жай іздеп|не спешу|асықпаймын|не важно|маңызды емес", None),
    (r"1\s*[–-]\s*2\s*(мес|ай)", (30, 60)),
    (r"2\s*[–-]\s*3\s*(мес|ай)", (60, 90)),
    (r"(в течение|в ближайш\w*)\s*месяц|ай ішінде|бір ай", (0, 30)),
    (r"недел|апта", (0, 7)),
    (r"ближайшие\s*\d+\s*(дн|день)|скорее|тезірек|сейчас|қазір|срочно|шұғыл|бос\b", (0, 7)),
    (r"ближайшее время|жақын арада", (0, 14)),
]


def _parse_specific_date(text: str, today: date) -> Optional[date]:
    m = re.search(r"(\d{1,2})\s*[-–]?\s*([^\d\s]+)", text)
    if not m:
        return None
    day = int(m.group(1))
    word = m.group(2)
    for pattern, month in _MONTHS:
        if re.match(pattern, word):
            try:
                candidate = date(today.year, month, day)
            except ValueError:
                return None
            # A date far in the past most likely means next year.
            if (today - candidate).days > 180:
                candidate = date(today.year + 1, month, day)
            return candidate
    return None


def parse_move_in_window(
    text: Optional[str],
    stated_at: Optional[datetime] = None,
    today: Optional[date] = None,
) -> Optional[Window]:
    """Return (earliest, latest) days from today, or None when flexible/unknown.

    Relative phrases ("в течение недели") are counted from `stated_at`
    (when the profile was saved), so an old answer does not drift forward.
    """
    if not text:
        return None
    today = today or date.today()
    low = text.lower().strip()

    specific = _parse_specific_date(low, today)
    if specific is not None:
        start = (specific - today).days
        return (max(0, start), max(0, start) + DATE_TOLERANCE_DAYS)

    for pattern, window in _RELATIVE:
        if re.search(pattern, low):
            if window is None:
                return None
            shift = (today - stated_at.date()).days if stated_at else 0
            start = max(0, window[0] - shift)
            end = max(0, window[1] - shift)
            return (start, end)
    return None


def windows_compatible(a: Optional[Window], b: Optional[Window], tolerance: int = DATE_TOLERANCE_DAYS) -> bool:
    """Two move-in windows are compatible when they overlap within tolerance."""
    if a is None or b is None:
        return True
    gap = max(a[0], b[0]) - min(a[1], b[1])
    return gap <= tolerance
