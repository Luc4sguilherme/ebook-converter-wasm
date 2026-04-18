"""Stub for calibre_extensions.msdes — stateful DES API matching the C extension."""

EN0 = 0  
DE1 = 1  

_current_key = None
_current_mode = EN0

def deskey(key, mode=EN0):
    """Set up the DES key schedule for subsequent des() calls.

    This is a no-op stub — LIT DRM decryption will NOT work,
    but the API shape matches the C extension so callers don't crash.
    """
    global _current_key, _current_mode
    if isinstance(key, str):
        key = key.encode('latin-1')
    _current_key = (key + b'\x00' * 8)[:8]
    _current_mode = mode

def des(data):
    """Encrypt / decrypt *data* with the key set by the last deskey() call.

    WARNING: This is a no-op stub. DRM-protected LIT files won't decrypt.
    """
    if isinstance(data, str):
        data = data.encode('latin-1')

    return data
