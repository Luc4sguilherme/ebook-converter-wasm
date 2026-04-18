"""WASM stub for calibre.utils.iso8601 — no tzlocal dependency."""
from datetime import UTC as utc_tz
from datetime import datetime, timedelta, timezone

local_tz = utc_tz
UNDEFINED_DATE = datetime(101, 1, 1, tzinfo=utc_tz)

def parse_iso8601(date_string, assume_utc=False, as_utc=True, require_aware=False):
    if not date_string:
        return UNDEFINED_DATE

    import re

    date_string = date_string.strip()

    try:
        import dateutil.parser
        dt = dateutil.parser.isoparse(date_string)
        tz = utc_tz if assume_utc else local_tz
        if not dt.tzinfo:
            if require_aware:
                raise ValueError(f'{date_string} does not specify a time zone')
            dt = dt.replace(tzinfo=tz)
        if as_utc:
            return dt.astimezone(utc_tz)
        return dt.astimezone(local_tz)
    except ImportError:
        pass

    try:

        tz = utc_tz
        s = date_string
        if s.endswith('Z'):
            s = s[:-1]
            tz = utc_tz
        elif '+' in s[10:] or (s.count('-') > 2):

            m = re.search(r'([+-]\d{2}):?(\d{2})$', s)
            if m:
                hours, mins = int(m.group(1)), int(m.group(2))
                tz = timezone(timedelta(hours=hours, minutes=mins))
                s = s[:m.start()]

        if 'T' in s:
            dt = datetime.fromisoformat(s)
        else:
            dt = datetime.fromisoformat(s)

        if not dt.tzinfo:
            if assume_utc:
                tz = utc_tz
            if require_aware:
                raise ValueError(f'{date_string} does not specify a time zone')
            dt = dt.replace(tzinfo=tz)

        if as_utc:
            return dt.astimezone(utc_tz)
        return dt
    except Exception:
        return UNDEFINED_DATE
