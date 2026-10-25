"""SQLite persistence and transactional job ownership.

Connections are short lived. No transaction spans PDF parsing or a provider call.
"""
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from config import Settings


def timestamp():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(settings: Settings):
    db = sqlite3.connect(settings.database, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(settings: Settings):
    settings.uploads.mkdir(parents=True, exist_ok=True)
    with connect(settings) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS worker_heartbeats (
            id TEXT PRIMARY KEY, last_seen REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, storage_key TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL, page_count INTEGER NOT NULL,
            ai_project_id TEXT, ai_project_name TEXT, project_id TEXT, project_name TEXT,
            warning TEXT, revision INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS extraction_jobs (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL UNIQUE REFERENCES documents(id),
            status TEXT NOT NULL CHECK(status IN ('queued','processing','completed','failed')),
            phase TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            completed_chunks INTEGER NOT NULL DEFAULT 0, total_chunks INTEGER NOT NULL DEFAULT 0,
            error TEXT, claim_token TEXT, lease_until REAL, available_at REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS jobs_queue ON extraction_jobs(status, available_at, created_at);
        CREATE TABLE IF NOT EXISTS comments (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
            text TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS comments_document ON comments(document_id, created_at);
        """)


def document(db, document_id):
    if not db.in_transaction:
        db.execute("BEGIN")
    row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result.pop("storage_key")
    job = db.execute("SELECT status,phase,attempts,completed_chunks,total_chunks,error,updated_at FROM extraction_jobs WHERE document_id=?", (document_id,)).fetchone()
    result["job"] = dict(job)
    return result


def detail(db, document_id):
    result = document(db, document_id)
    if result is not None:
        result["comments"] = [dict(row) for row in db.execute(
            "SELECT id,text,created_at FROM comments WHERE document_id=? ORDER BY created_at,id", (document_id,))]
    return result


def claim(settings: Settings):
    now = time.time()
    with connect(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""UPDATE extraction_jobs SET
            status=CASE WHEN attempts>=? THEN 'failed' ELSE 'queued' END,
            phase=CASE WHEN attempts>=? THEN 'failed' ELSE 'recovering' END,
            error='Processing was interrupted. The worker lease expired.',
            claim_token=NULL, lease_until=NULL, updated_at=?
            WHERE status='processing' AND lease_until<=?""",
            (settings.max_attempts, settings.max_attempts, timestamp(), now))
        row = db.execute("""SELECT j.*,d.storage_key FROM extraction_jobs j JOIN documents d ON d.id=j.document_id
            WHERE j.status='queued' AND j.available_at<=? ORDER BY j.created_at,j.id LIMIT 1""", (now,)).fetchone()
        if row is None:
            return None
        token = str(uuid4())
        db.execute("""UPDATE extraction_jobs SET status='processing', phase='preparing',
            attempts=attempts+1, claim_token=?,lease_until=?,completed_chunks=0,total_chunks=0,error=NULL,updated_at=? WHERE id=?""",
            (token, now + settings.lease_seconds, timestamp(), row["id"]))
        return dict(row) | {"claim_token": token, "attempts": row["attempts"] + 1}


class LostClaim(Exception):
    pass


def owned(db, job):
    if not db.execute("SELECT 1 FROM extraction_jobs WHERE id=? AND claim_token=? AND status='processing' AND lease_until>?",
                      (job["id"], job["claim_token"], time.time())).fetchone():
        raise LostClaim("Job ownership expired")


def progress(settings, job, phase, completed=None, total=None):
    with connect(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        owned(db, job)
        db.execute("""UPDATE extraction_jobs SET phase=?,completed_chunks=COALESCE(?,completed_chunks),
            total_chunks=COALESCE(?,total_chunks),lease_until=?,updated_at=? WHERE id=?""",
            (phase, completed, total, time.time() + settings.lease_seconds, timestamp(), job["id"]))


def finish(settings, job, metadata, warning=None):
    with connect(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        owned(db, job)
        db.execute("""UPDATE documents SET ai_project_id=?,ai_project_name=?,
            project_id=CASE WHEN revision=0 THEN ? ELSE project_id END,
            project_name=CASE WHEN revision=0 THEN ? ELSE project_name END,
            warning=?,updated_at=? WHERE id=?""",
            (metadata.project_id, metadata.project_name, metadata.project_id, metadata.project_name,
             warning, timestamp(), job["document_id"]))
        db.execute("""UPDATE extraction_jobs SET status='completed',phase='completed',
            completed_chunks=total_chunks,claim_token=NULL,lease_until=NULL,error=NULL,updated_at=? WHERE id=?""",
            (timestamp(), job["id"]))


def fail(settings, job, message, transient=False):
    retry = transient and job["attempts"] < settings.max_attempts
    with connect(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        owned(db, job)
        db.execute("""UPDATE extraction_jobs SET status=?,phase=?,error=?,claim_token=NULL,lease_until=NULL,
            available_at=?,updated_at=? WHERE id=?""",
            ("queued" if retry else "failed", "retry_wait" if retry else "failed", message,
             time.time() + min(60, 2 ** job["attempts"]) if retry else 0, timestamp(), job["id"]))


def renew(settings, job):
    with connect(settings) as conn:
        conn.execute("BEGIN IMMEDIATE")
        owned(conn, job)
        conn.execute("UPDATE extraction_jobs SET lease_until=? WHERE id=?", (time.time() + settings.lease_seconds, job['id']))


def delete_document(settings, document_id):
    """Remove one document atomically, invalidating outstanding worker claims."""
    with connect(settings) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT storage_key FROM documents WHERE id=?", (document_id,)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM comments WHERE document_id=?", (document_id,))
        conn.execute("DELETE FROM extraction_jobs WHERE document_id=?", (document_id,))
        conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
    # Filesystem cleanup follows the commit: a stale extraction cannot restore
    # deleted records. An interrupted/failed unlink may leave an orphaned file.
    return row['storage_key']


def register_worker(settings, worker_id):
    with connect(settings) as conn:
        conn.execute("INSERT INTO worker_heartbeats(id,last_seen) VALUES(?,?)", (worker_id, time.time()))
        conn.execute("DELETE FROM worker_heartbeats WHERE last_seen<?", (time.time() - 86400,))


def pulse_worker(settings, worker_id):
    with connect(settings) as conn:
        # Never reinsert a registration removed during shutdown.
        conn.execute("UPDATE worker_heartbeats SET last_seen=? WHERE id=?", (time.time(), worker_id))


def unregister_worker(settings, worker_id):
    with connect(settings) as conn:
        conn.execute("DELETE FROM worker_heartbeats WHERE id=?", (worker_id,))


def worker_availability(settings):
    with connect(settings) as conn:
        last_seen = conn.execute("SELECT MAX(last_seen) FROM worker_heartbeats").fetchone()[0]
    return {
        'available': last_seen is not None and last_seen >= time.time() - settings.worker_stale_seconds,
        'last_seen_at': datetime.fromtimestamp(last_seen, timezone.utc).isoformat() if last_seen is not None else None,
    }
