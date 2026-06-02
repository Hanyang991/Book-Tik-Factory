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
import math
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# poc/ 모듈 및 scheduler 임포트 참조 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../poc")))

import generate  # noqa: E402
import enrich     # noqa: E402
import curate     # noqa: E402
from api.jobs import store  # noqa: E402
from api.scheduler import scheduler  # noqa: E402

app = FastAPI(title="Book-Tik Factory API (prototype)")


# -------------------------------------------------------------
# 스케줄러 구동 및 종료 수명주기 연동
# -------------------------------------------------------------
@app.on_event("startup")
def startup_event():
    print("[main] Starting weekly curation scheduler...")
    # 스케줄러가 이미 구동 중이지 않으면 시작
    if not scheduler.running:
        scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    print("[main] Stopping weekly curation scheduler...")
    if scheduler.running:
        scheduler.shutdown()


# -------------------------------------------------------------
# 하버사인 거리 실측 거리 정렬 공식
# -------------------------------------------------------------
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위도/경도 좌표 간의 대원 거리(km)를 구함."""
    R = 6371.0  # 지구 반지름 (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


class GenerateRequest(BaseModel):
    isbn: str
    region: str = "11"   # 법정동 지역코드 (11=서울)
    custom_description: str | None = None
    custom_keywords: str | None = None  # 쉼표 구분 텍스트 형식 수용


def _run_job(job_id: str, isbn: str, region: str, custom_description: str | None = None, custom_keywords_str: str | None = None) -> None:
    """BackgroundTasks 워커: 생성 파이프라인 실행하며 단계별 상태 갱신."""
    store.update(job_id, status="running", stage="시작")
    try:
        # 서지 조회로 제목/저자를 Job에 즉시 반영 (프론트 실시간 표시용)
        book = generate.build_book(isbn)
        store.update(job_id, title=book.get("title", ""), author=book.get("author", ""))

        # 쉼표 구분 텍스트를 리스트로 분할 파싱
        custom_keywords = [k.strip() for k in custom_keywords_str.split(",") if k.strip()] if custom_keywords_str else None

        # generate.run은 동기 파이프라인(LOD/정보나루 -> Gemini -> TTS -> 렌더).
        # progress 콜백으로 단계별 상태를 Job에 반영한다.
        path = generate.run(
            isbn, region=region,
            progress=lambda stage: store.update(job_id, stage=stage),
            custom_description=custom_description,
            custom_keywords=custom_keywords
        )
        store.update(job_id, status="done", stage="완료", video_path=path)
    except Exception as e:
        store.update(job_id, status="failed", stage="오류", error=str(e))


@app.post("/api/generate")
def create_job(req: GenerateRequest, bg: BackgroundTasks):
    if not (req.isbn.isdigit() and len(req.isbn) == 13):
        raise HTTPException(400, "isbn은 하이픈 없는 13자리 ISBN-13이어야 합니다")
    job = store.create(req.isbn, req.region)
    bg.add_task(_run_job, job.id, req.isbn, req.region, req.custom_description, req.custom_keywords)
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
def locate(isbn: str, region: str = "11", limit: int = 10, lat: float | None = None, lng: float | None = None):
    """해당 ISBN을 소장한 도서관 목록 및 사용자 GPS 좌표 수신 시 최단거리 기준 실측 정렬 제공."""
    res = enrich.find_holding_libraries(isbn, region=region, limit=limit)
    libraries = res.get("libraries", [])
    
    if lat is not None and lng is not None:
        for lib in libraries:
            lib_lat = lib.get("lat", 0.0)
            lib_lng = lib.get("lng", 0.0)
            if lib_lat != 0.0 and lib_lng != 0.0:
                lib["distance_km"] = haversine(lat, lng, lib_lat, lib_lng)
            else:
                lib["distance_km"] = 9999.0
        # 실측 거리 순 정렬
        libraries = sorted(libraries, key=lambda x: x.get("distance_km", 9999.0))
        res["libraries"] = libraries
        
    return res


@app.get("/api/book/{isbn}")
def get_book_metadata(isbn: str):
    """도서관 정보나루에서 특정 ISBN의 서지 메타데이터(제목, 저자 등)를 조회합니다."""
    try:
        return enrich.get_book_usage(isbn)
    except Exception as e:
        raise HTTPException(500, f"도서 정보 조회 실패: {e}")


@app.get("/api/curation")
def curation(region: str = "11", age: str = "20", search_date: str | None = None,
             pool_size: int = 12, per_type: int = 2):
    """회전율 기반 주간 제작 대상 자동 선정(타입 A/B/C). 
    
    로컬 디렉토리에 solomon.csv 또는 curation.csv가 있을 경우 분석에 교차 연동함.
    """
    solomon_path = os.path.join(os.path.dirname(__file__), "solomon.csv")
    curation_path = os.path.join(os.path.dirname(__file__), "curation.csv")
    if not os.path.exists(solomon_path):
        solomon_path = os.path.join(os.path.dirname(__file__), "..", "solomon.csv")
    if not os.path.exists(curation_path):
        curation_path = os.path.join(os.path.dirname(__file__), "..", "curation.csv")

    return curate.build_weekly_targets(
        region=region, age=age, search_date=search_date,
        pool_size=pool_size, per_type=per_type,
        solomon_path=solomon_path if os.path.exists(solomon_path) else None,
        curation_path=curation_path if os.path.exists(curation_path) else None
    )


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


# -------------------------------------------------------------
# 웹 UI 페이지 서빙 라우트 (React SPA 및 정적 에셋 서빙)
# -------------------------------------------------------------
@app.get("/")
@app.get("/locate")
@app.get("/dashboard")
def get_spa_page():
    """Vite로 빌드된 React SPA index.html을 서빙하고, 없으면 기존 레거시 템플릿으로 폴백합니다."""
    dist_index = os.path.abspath(os.path.join(os.path.dirname(__file__), "../figma_extracted/dist/index.html"))
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
        
    # 레거시 폴백 (아직 React 빌드가 수행되지 않은 시점용)
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    if os.path.exists(template_path):
        with open(template_path, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    raise HTTPException(500, "서버에 서빙할 페이지나 템플릿이 존재하지 않습니다. React 빌드가 필요합니다.")


# 1. outputs 디렉토리 마운트 (동영상, 표지, QR코드 이미지 서빙)
outputs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../poc/outputs"))
os.makedirs(outputs_dir, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=outputs_dir), name="outputs")

# 2. React 빌드 결과물 정적 파일 마운트 (JS, CSS, assets 등)
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../figma_extracted/dist"))
os.makedirs(dist_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")
