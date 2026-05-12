from datetime import datetime

def parse_iso_timestamp(ts_str: str) -> datetime:
    """Safely parse ISO timestamp strings, handling 'Z' suffix for compatibility.

    In Python versions < 3.11, fromisoformat does not support 'Z' automatically.
    """
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
