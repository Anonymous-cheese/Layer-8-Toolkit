"""Offline 12-hour and 24-hour clock notation conversion."""

import re


def convert_clock_time(value):
    """Return ``(24-hour, 12-hour)`` strings for a clock time.

    AM/PM input is 12-hour notation. Unsuffixed input is 24-hour notation.
    Both colon-separated and four-digit 24-hour forms are accepted.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter a time such as 2:30 PM, 14:30, or 1430.")

    text = value.strip()
    twelve_hour = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", text, re.IGNORECASE)
    if twelve_hour:
        hour = int(twelve_hour.group(1))
        minute = int(twelve_hour.group(2) or "0")
        if not 1 <= hour <= 12 or minute > 59:
            raise ValueError("Use an hour from 1 to 12 and minutes from 00 to 59 with AM or PM.")
        hour = hour % 12 + (12 if twelve_hour.group(3).upper() == "PM" else 0)
    else:
        separated = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
        compact = re.fullmatch(r"(\d{2})(\d{2})", text)
        hour_only = re.fullmatch(r"\d{1,2}", text)
        if separated:
            hour, minute = int(separated.group(1)), int(separated.group(2))
        elif compact:
            hour, minute = int(compact.group(1)), int(compact.group(2))
        elif hour_only:
            hour, minute = int(text), 0
        else:
            raise ValueError("Enter 24-hour time as 14:30 or 1430, or 12-hour time as 2:30 PM.")
        if hour > 23 or minute > 59:
            raise ValueError("Use an hour from 00 to 23 and minutes from 00 to 59.")

    period = "AM" if hour < 12 else "PM"
    twelve_hour_number = hour % 12 or 12
    return f"{hour:02d}:{minute:02d}", f"{twelve_hour_number}:{minute:02d} {period}"


def clock_reference_rows():
    """Return paired midnight-to-noon and noon-to-midnight hour rows."""
    return [(*convert_clock_time(f"{hour:02d}:00"),
             *convert_clock_time(f"{hour + 12:02d}:00"))
            for hour in range(12)]
