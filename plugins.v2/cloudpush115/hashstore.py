"""Optional bounded SQLite SHA1 cache; failures fall back to reading the file."""
from __future__ import annotations
import json
import logging
import re
import sqlite3
import threading
from pathlib import Path

_local = threading.local()
_LOG = logging.getLogger(__name__)


def configure_cache(directory):
    """Scope the persistent store to the calling plugin worker thread."""
    _local.path = str(Path(directory) / 'sha1-cache-v1.sqlite3') if directory else None


def _key(path):
    st = path.stat()
    return json.dumps([str(path.resolve()), st.st_dev, st.st_ino, st.st_size,
                       st.st_mtime_ns, st.st_ctime_ns], separators=(',', ':'))


def _connect():
    target = getattr(_local, 'path', None)
    if not target:
        return None
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(target, timeout=2)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS hashes (identity TEXT PRIMARY KEY, digest TEXT NOT NULL, touched REAL NOT NULL)')
    except Exception:
        db.close()
        raise
    return db


def lookup(path):
    db = None
    try:
        before = _key(path)
        db = _connect()
        if db is None:
            return None
        row = db.execute('SELECT digest FROM hashes WHERE identity=?', (before,)).fetchone()
        if row and re.fullmatch('[0-9A-F]{40}', row[0]) and before == _key(path):
            return row[0]
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        _LOG.debug('SHA1 cache lookup skipped: %s', type(exc).__name__)
    finally:
        if db is not None:
            db.close()
    return None


def identity(path):
    return _key(path)


def store(path, digest, expected):
    db = None
    try:
        if expected != _key(path) or not re.fullmatch('[0-9A-F]{40}', digest):
            return
        db = _connect()
        if db is None:
            return
        with db:
            db.execute("INSERT OR REPLACE INTO hashes VALUES (?, ?, julianday('now'))", (expected, digest))
            db.execute('DELETE FROM hashes WHERE identity IN (SELECT identity FROM hashes ORDER BY touched DESC LIMIT -1 OFFSET 2048)')
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        _LOG.debug('SHA1 cache write skipped: %s', type(exc).__name__)
    finally:
        if db is not None:
            db.close()
