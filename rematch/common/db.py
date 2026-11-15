"""SQLAlchemy JSON repository; one SQLite file per service."""
import json
from pathlib import Path
from threading import RLock
from sqlalchemy import create_engine, text
from sqlalchemy import event


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}", connect_args={"check_same_thread": False, "timeout": 30})
        @event.listens_for(self.engine,"connect")
        def configure_connection(connection,_):
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA busy_timeout=30000")
        with self.engine.begin() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(kind,id))"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS patient_identity_vault (clinic_local_patient_id TEXT PRIMARY KEY, key_id TEXT NOT NULL, nonce_b64 TEXT NOT NULL, ciphertext_b64 TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"))

    def put(self, kind, key, value):
        with self.lock, self.engine.begin() as conn:
            conn.execute(text("INSERT INTO records(kind,id,body) VALUES(:k,:i,:b) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body"),
                         {"k":kind,"i":key,"b":json.dumps(value,separators=(",", ":"),sort_keys=True)})
        return value

    def get(self, kind, key, default=None):
        with self.engine.connect() as conn:
            value = conn.execute(text("SELECT body FROM records WHERE kind=:k AND id=:i"),{"k":kind,"i":key}).scalar()
        return json.loads(value) if value else default

    def all(self, kind):
        with self.engine.connect() as conn:
            values = conn.execute(text("SELECT body FROM records WHERE kind=:k ORDER BY rowid"),{"k":kind}).scalars().all()
        return [json.loads(v) for v in values]

    def delete(self, kind, key):
        with self.lock, self.engine.begin() as conn:
            conn.execute(text("DELETE FROM records WHERE kind=:k AND id=:i"),{"k":kind,"i":key})

    def clear(self):
        with self.lock, self.engine.begin() as conn:
            conn.execute(text("DELETE FROM records"))
            conn.execute(text("DELETE FROM patient_identity_vault"))
