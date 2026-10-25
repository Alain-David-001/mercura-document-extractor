"""Environment configuration shared by the API and worker."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_upload_bytes: int = 100 * 1024 * 1024
    max_pages: int = 5000
    chunk_pages: int = 40
    chunk_bytes: int = 18 * 1024 * 1024
    concurrency: int = 1
    lease_seconds: int = 90
    max_attempts: int = 3
    poll_seconds: float = 1.0
    worker_heartbeat_seconds: float = 5.0
    worker_stale_seconds: float = 20.0
    model: str = "gemini-2.5-flash-lite"

    @property
    def database(self) -> Path:
        return self.data_dir / "mercura.sqlite3"

    @property
    def uploads(self) -> Path:
        return self.data_dir / "uploads"

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", str(Path(__file__).parent / "data"))).resolve(),
            concurrency=max(1, min(8, int(os.getenv("WORKER_CONCURRENCY", "1")))),
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        )
