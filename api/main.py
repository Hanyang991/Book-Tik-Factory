"""
Book-Tik Factory — 프로토타입 API 서버 (FastAPI + BackgroundTasks).

PoC에서 검증한 생성 파이프라인(poc/generate.py)을 비동기 Job으로 감싼다.
  POST /api/generate    {isbn, region} -> {job_id}
  GET  /api/job/{id}    -> 진행 상태/결과 경로
  GET  /api/jobs        -> 전체 Job 목록
  GET  /api/trending    -> hotTrend 화제 도서(타입 C)
  GET  /api/locate/{isbn} -> 소장 도서관(가까운 곳 안내)
  GET  /api/curation    -> 회전율 기반 주간 제작 대상(타입 A/B/C 자동 선정)
  GET  /video/{job_id}  -> 완성 MP4 다운로드

정식 단계 교체 지점: 인메모리 JobStore -> Redis/DB, BackgroundTasks -> Celery,
APScheduler로 매주 자동 배치(build_weekly_targets).
"""
import os
import sys

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# poc/ 모듈 재사용
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "poc"))
import generate  # noqa: E402
import enrich     # noqa: E402
import curate     # noqa: E402
from jobs import store  # noqa: E402

app = FastAPI(title="Book-Tik Factory API (prototype)")


class GenerateRequest(BaseModel):
    isbn: str
    region: str = "11"   # 법정동 지역코드 (11=서울)


def _run_job(job_id: str, isbn: str, region: str) -> None:
    """BackgroundTasks 워커: 생성 파이프라인 실행하며 단계별 상태 갱신."""
    store.update(job_id, status="running", stage="시작")
    try:
        # generate.run은 동기 파이프라인(LOD/정보나루 -> Gemini -> TTS -> 렌더).
        # progress 콜백으로 단계별 상태를 Job에 반영한다.
        path = generate.run(
            isbn, region=region,
            progress=lambda stage: store.update(job_id, stage=stage),
        )
        store.update(job_id, status="done", stage="완료", video_path=path)
    except Exception as e:
        store.update(job_id, status="failed", stage="오류", error=str(e))


@app.post("/api/generate")
def create_job(req: GenerateRequest, bg: BackgroundTasks):
    if not (req.isbn.isdigit() and len(req.isbn) == 13):
        raise HTTPException(400, "isbn은 하이픈 없는 13자리 ISBN-13이어야 합니다")
    job = store.create(req.isbn, req.region)
    bg.add_task(_run_job, job.id, req.isbn, req.region)
    return {"job_id": job.id, "status": job.status}


@app.get("/api/job/{job_id}")
def get_job(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job을 찾을 수 없습니다")
    return job.to_dict()


@app.get("/api/jobs")
def list_jobs():
    return [j.to_dict() for j in store.all()]


@app.get("/api/trending")
def trending(search_date: str, limit: int = 10):
    """hotTrend 화제 도서(타입 C). search_date=YYYY-MM-DD."""
    return enrich.get_trending_books(search_date, limit=limit)


@app.get("/api/locate/{isbn}")
def locate(isbn: str, region: str = "11", limit: int = 5):
    """해당 ISBN을 소장한 도서관(가까운 곳 안내용)."""
    return enrich.find_holding_libraries(isbn, region=region, limit=limit)


@app.get("/api/curation")
def curation(region: str = "11", age: str = "20", search_date: str | None = None,
             pool_size: int = 12, per_type: int = 2):
    """회전율 기반 주간 제작 대상 자동 선정(타입 A/B/C). 영상 생성은 하지 않는다."""
    return curate.build_weekly_targets(
        region=region, age=age, search_date=search_date,
        pool_size=pool_size, per_type=per_type)


@app.get("/video/{job_id}")
def video(job_id: str):
    job = store.get(job_id)
    if not job or job.status != "done" or not job.video_path:
        raise HTTPException(404, "완성된 영상이 없습니다")
    return FileResponse(job.video_path, media_type="video/mp4",
                        filename=os.path.basename(job.video_path))


@app.get("/health")
def health():
    return {"ok": True, "naru_key": bool(os.environ.get("LIBRARY_API_KEY")),
            "gemini_key": bool(os.environ.get("GEMINI_API_KEY"))}
