"""Applications persisted as JSON documents in SQLite, plus a masked audit log."""
import json
import os
import sqlite3
import threading
import time

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "app.db")
_lock = threading.Lock()


def _conn():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS applications (id TEXT PRIMARY KEY, doc TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS audit (at REAL, application TEXT, event TEXT)")
    return c


def save(app):
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO applications VALUES (?, ?)", (app["id"], json.dumps(app)))


def load(app_id):
    with _lock, _conn() as c:
        row = c.execute("SELECT doc FROM applications WHERE id = ?", (app_id,)).fetchone()
    return json.loads(row[0]) if row else None


def next_id():
    with _lock, _conn() as c:
        n = c.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    return "A%05d" % (n + 1)


def audit(app_id, event):
    """event must already be masked - never log raw identifiers or document text."""
    with _lock, _conn() as c:
        c.execute("INSERT INTO audit VALUES (?, ?, ?)", (time.time(), app_id, event))


def audit_log(app_id):
    with _lock, _conn() as c:
        rows = c.execute("SELECT at, event FROM audit WHERE application = ? ORDER BY at", (app_id,)).fetchall()
    return [{"at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(a)), "event": e} for a, e in rows]
