"""인메모리 Job 저장소 (프로토타입). 정식 단계에서 Redis/DB로 교체."""
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Job:
    id: str
    isbn: str
    region: str
    status: str = "queued"          # queued | running | done | failed
    stage: str = ""                  # 현재 단계(서지조회/대본/TTS/...)
    video_path: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, isbn: str, region: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], isbn=isbn, region=region)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for k, v in fields.items():
                setattr(job, k, v)
            job.updated_at = time.time()

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())


store = JobStore()
