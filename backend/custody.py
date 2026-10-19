"""SHA-256 sealing, custody log and previous-case hashes (local SQLite only)."""
import hashlib, sqlite3, time
from pathlib import Path

DB = Path("data/pramaanlens.db")


def _conn():
    DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS custody(id INTEGER PRIMARY KEY, case_id TEXT, ts TEXT, event TEXT, detail TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS cases(case_id TEXT PRIMARY KEY, sha256 TEXT, phash TEXT, filename TEXT, ts TEXT)")
    return c


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def log(case_id, event, detail=""):
    with _conn() as c:
        c.execute("INSERT INTO custody(case_id, ts, event, detail) VALUES (?,?,?,?)", (case_id, now(), event, detail))


def register(case_id, digest, phash, filename):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO cases VALUES (?,?,?,?,?)", (case_id, digest, phash, filename, now()))


def previous(exclude):
    with _conn() as c:
        return c.execute("SELECT case_id, phash FROM cases WHERE case_id != ?", (exclude,)).fetchall()


def trail(case_id):
    with _conn() as c:
        return c.execute("SELECT ts, event, detail FROM custody WHERE case_id = ? ORDER BY id", (case_id,)).fetchall()
