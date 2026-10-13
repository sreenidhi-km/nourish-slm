"""
formatting.py
=============
Formatting utility for recipe metadata: ISO-8601 durations and servings.
Examples:
- "PT25M" -> "25 mins"
- "PT1H30M" -> "1 hr 30 mins"
- "PT40M" -> "40 mins"
- 4.0 -> "4"
- 0.0 -> "Servings not specified"
"""

import re

def format_duration(duration_str: str) -> str:
    """Converts ISO-8601 duration string (e.g. PT1H30M, PT25M) to human-readable string."""
    if not duration_str or not isinstance(duration_str, str):
        return "15 mins"
    
    s = duration_str.upper().strip()
    if not s.startswith("PT") and not any(c in s for c in ['H', 'M']):
        return duration_str if duration_str.strip() else "15 mins"

    hours = 0
    minutes = 0

    h_match = re.search(r'(\d+)H', s)
    if h_match:
        hours = int(h_match.group(1))

    m_match = re.search(r'(\d+)M', s)
    if m_match:
        minutes = int(m_match.group(1))

    parts = []
    if hours > 0:
        parts.append(f"{hours} hr" + ("s" if hours > 1 else ""))
    if minutes > 0:
        parts.append(f"{minutes} min" + ("s" if minutes > 1 else ""))

    if not parts:
        return "15 mins"
    return " ".join(parts)

def format_servings(servings_val) -> str:
    """Converts numeric or string servings to clean human-readable representation."""
    if servings_val is None:
        return "Servings not specified"
    try:
        val = float(servings_val)
        if val <= 0:
            return "Servings not specified"
        if val.is_integer():
            return str(int(val))
        return str(val)
    except (ValueError, TypeError):
        s = str(servings_val).strip()
        return s if s and s != "0" and s != "0.0" else "Servings not specified"
