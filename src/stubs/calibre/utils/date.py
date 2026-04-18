import re
import datetime
import time
import functools

UNDEFINED_DATE = datetime.datetime(101, 1, 1, tzinfo=datetime.timezone.utc)
utc_tz = datetime.timezone.utc
local_tz = datetime.timezone.utc

EPOCH = datetime.datetime(1970, 1, 1, tzinfo=utc_tz)
DEFAULT_DATE = datetime.datetime(2000, 1, 1, tzinfo=utc_tz)

_lcdata = {
    'abday': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    'day': ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
    'abmon': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    'mon': ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'],
}

def now():
    return datetime.datetime.now(datetime.timezone.utc)

def utcnow():
    return now()

def isoformat(dt, as_utc=True, assume_utc=False, sep='T'):
    if dt is None:
        dt = now()
    if hasattr(dt, 'tzinfo'):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=utc_tz if assume_utc else local_tz)
        dt = dt.astimezone(utc_tz if as_utc else local_tz)
    if isinstance(dt, datetime.datetime):
        return str(dt.isoformat(sep))
    return str(dt.isoformat())

def internal_iso_format_string():
    return 'yyyy-MM-ddThh:mm:ss'

def _fd_format_hour(dt, ampm, hr):
    h = dt.hour
    if ampm:
        h = h % 12
    if len(hr) == 1:
        return '%d' % h
    return '%02d' % h

def _fd_format_minute(dt, ampm, m):
    if len(m) == 1:
        return '%d' % dt.minute
    return '%02d' % dt.minute

def _fd_format_second(dt, ampm, s):
    if len(s) == 1:
        return '%d' % dt.second
    return '%02d' % dt.second

def _fd_format_ampm(dt, ampm, ap):
    res = 'AM' if dt.hour < 12 else 'PM'
    if ap == 'AP':
        return res
    return res.lower()

def _fd_format_day(dt, ampm, dy):
    length = len(dy)
    if length == 1:
        return '%d' % dt.day
    if length == 2:
        return '%02d' % dt.day
    return _lcdata['abday' if length == 3 else 'day'][(dt.weekday() + 1) % 7]

def _fd_format_month(dt, ampm, mo):
    length = len(mo)
    if length == 1:
        return '%d' % dt.month
    if length == 2:
        return '%02d' % dt.month
    return _lcdata['abmon' if length == 3 else 'mon'][dt.month - 1]

def _fd_format_year(dt, ampm, yr):
    if len(yr) == 2:
        return '%02d' % (dt.year % 100)
    return '%04d' % dt.year

_fd_function_index = {
    'd': _fd_format_day,
    'M': _fd_format_month,
    'y': _fd_format_year,
    'h': _fd_format_hour,
    'm': _fd_format_minute,
    's': _fd_format_second,
    'a': _fd_format_ampm,
    'A': _fd_format_ampm,
}

def _fd_repl_func(dt, ampm, mo):
    s = mo.group(0)
    if not s:
        return ''
    return _fd_function_index[s[0]](dt, ampm, s)

def format_date(dt, format='dd MMM yyyy', assume_utc=False, as_utc=False):
    """Return a date formatted as a string using a subset of Qt's formatting codes."""
    if not format:
        format = 'dd MMM yyyy'

    if not isinstance(dt, datetime.datetime):
        dt = datetime.datetime.combine(dt, datetime.time())

    if hasattr(dt, 'tzinfo'):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=utc_tz if assume_utc else local_tz)
        dt = dt.astimezone(utc_tz if as_utc else local_tz)

    if format == 'iso':
        return isoformat(dt, assume_utc=assume_utc, as_utc=as_utc)

    if is_date_undefined(dt):
        return ''

    repl_func = functools.partial(_fd_repl_func, dt, 'ap' in format.lower())
    return re.sub(
        '(s{1,2})|(m{1,2})|(h{1,2})|(ap)|(AP)|(d{1,4}|M{1,4}|(?:yyyy|yy))',
        repl_func, format)

def is_date_undefined(dt):
    if dt is None:
        return True
    return dt.year < UNDEFINED_DATE.year or (
        dt.year == UNDEFINED_DATE.year and
        dt.month == UNDEFINED_DATE.month and
        dt.day == UNDEFINED_DATE.day)

def as_local_time(dt, assume_utc=True):
    if not hasattr(dt, 'tzinfo'):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc_tz if assume_utc else local_tz)
    return dt.astimezone(local_tz)

def as_utc(dt, assume_utc=True):
    if dt is None:
        return UNDEFINED_DATE
    if not hasattr(dt, 'tzinfo'):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc_tz if assume_utc else local_tz)
    return dt.astimezone(utc_tz)

def parse_date(date_string, assume_utc=False, as_utc=True, default=None):
    if not date_string:
        return default or UNDEFINED_DATE
    if isinstance(date_string, bytes):
        date_string = date_string.decode('utf-8', 'replace')
    try:
        from dateutil.parser import parse
        if default is None:
            func = (datetime.datetime.utcnow if assume_utc
                    else datetime.datetime.now)
            default = func().replace(day=15, hour=0, minute=0, second=0,
                                     microsecond=0,
                                     tzinfo=utc_tz if assume_utc else local_tz)
        dt = parse(date_string, default=default)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=utc_tz if assume_utc else local_tz)
        return dt.astimezone(utc_tz if as_utc else local_tz)
    except Exception:
        pass
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.datetime.strptime(date_string[:len(fmt)+2], fmt).replace(
                tzinfo=datetime.timezone.utc)
        except (ValueError, TypeError):
            continue
    return default or UNDEFINED_DATE

def parse_only_date(raw, assume_utc=True, as_utc=True):
    f = utcnow if assume_utc else now
    default = f().replace(hour=0, minute=0, second=0, microsecond=0, day=15)
    return parse_date(raw, default=default, assume_utc=assume_utc, as_utc=as_utc)

def strptime(val, fmt, assume_utc=False, as_utc=True):
    dt = datetime.datetime.strptime(val, fmt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc_tz if assume_utc else local_tz)
    return dt.astimezone(utc_tz if as_utc else local_tz)

def w3cdtf(date_time, assume_utc=False):
    if hasattr(date_time, 'tzinfo'):
        if date_time.tzinfo is None:
            date_time = date_time.replace(tzinfo=utc_tz if assume_utc else local_tz)
        date_time = date_time.astimezone(utc_tz)
    return str(date_time.strftime('%Y-%m-%dT%H:%M:%SZ'))

def utcfromtimestamp(stamp):
    try:
        return datetime.datetime.fromtimestamp(stamp, tz=utc_tz)
    except (ValueError, OverflowError):
        try:
            return EPOCH + datetime.timedelta(seconds=stamp)
        except (ValueError, OverflowError):
            pass
    return utcnow()

def fromtimestamp(ctime, as_utc=True):
    dt = datetime.datetime.fromtimestamp(ctime, tz=utc_tz)
    if not as_utc:
        dt = dt.astimezone(local_tz)
    return dt

def timestampfromdt(dt, assume_utc=True):
    return (as_utc(dt, assume_utc=assume_utc) - EPOCH).total_seconds()

def clean_date_for_sort(dt, default=None):
    if dt is None or is_date_undefined(dt):
        return default or UNDEFINED_DATE
    return as_utc(dt)

def dt_factory(time_t, assume_utc=False, as_utc=True):
    dt = datetime.datetime(*(time_t[0:6]))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc_tz if assume_utc else local_tz)
    return dt.astimezone(utc_tz if as_utc else local_tz)

def fix_only_date(val):
    return val

def qt_from_dt(dt, as_utc=True):
    return dt
