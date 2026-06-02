"""
Book-Tik Factory — 주간 배치 자동화 스케줄러 (APScheduler).

FastAPI 서버 구동 시 백그라운드로 작동을 시작하며, 매주 월요일 오전 00:00에 정보나루 
대출/소장 데이터를 활용하여 타입 A/B/C 주간 숏폼 제작 타깃을 선정하고 생성 대기열에 추가합니다.
"""
import os
import sys
import threading
from apscheduler.schedulers.background import BackgroundScheduler

# 부모 디렉토리 및 poc/ 모듈 참조 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../poc")))

import generate
import curate
from api.jobs import store

scheduler = BackgroundScheduler(timezone="Asia/Seoul")


def _run_scheduled_job(job_id: str, isbn: str, region: str) -> None:
    """스케줄링된 작업의 생성 파이프라인 실행 및 실시간 단계별 진행 기록."""
    store.update(job_id, status="running", stage="시작")
    try:
        path = generate.run(
            isbn, region=region,
            progress=lambda stage: store.update(job_id, stage=stage),
        )
        store.update(job_id, status="done", stage="완료", video_path=path)
        print(f"[Scheduler] 비디오 생성 성공: ISBN={isbn}, JobID={job_id} -> {path}")
    except Exception as e:
        store.update(job_id, status="failed", stage="오류", error=str(e))
        print(f"[Scheduler] 비디오 생성 실패: ISBN={isbn}, JobID={job_id}, Error={e}")


def weekly_curation_job(region: str = "11", age: str = "20") -> None:
    """매주 월요일 00:00에 실행되는 주간 자동화 배치 태스크.
    
    1) 정보나루 API 및 로컬 CSV 교차 분석을 바탕으로 A/B/C타입 제작 도서 선정.
    2) 각 도서별 비동기 생성 파이프라인(Thread) 예약 및 진척 상태 업데이트.
    """
    print(f"[Scheduler] 주간 자동화 대본 선정 배치 작업 시작 (지역: {region}, 연령대: {age})")
    try:
        # 로컬 경로 파악 (api 폴더 내부 또는 루트 디렉토리)
        solomon_path = os.path.join(os.path.dirname(__file__), "solomon.csv")
        curation_path = os.path.join(os.path.dirname(__file__), "curation.csv")
        if not os.path.exists(solomon_path):
            solomon_path = os.path.join(os.path.dirname(__file__), "..", "solomon.csv")
        if not os.path.exists(curation_path):
            curation_path = os.path.join(os.path.dirname(__file__), "..", "curation.csv")
            
        # curate 모듈을 이용하여 이번 주에 타깃으로 할 최적의 숏폼 도서 자동 분석
        report = curate.build_weekly_targets(
            region=region, age=age, search_date=None, pool_size=12, per_type=2,
            solomon_path=solomon_path if os.path.exists(solomon_path) else None,
            curation_path=curation_path if os.path.exists(curation_path) else None
        )
        
        # A_숨은명저, B_회전율개선, C_화제도서 목록들을 합침
        targets = []
        for key in ["A_숨은명저", "B_회전율개선", "C_화제도서"]:
            for b in report.get(key, []):
                b["type"] = key.split("_")[-1] # "숨은명저", "회전율개선", "화제도서"
                targets.append(b)
                
        print(f"[Scheduler] Curation 자동 선정 완료. 주간 제작 대상: {len(targets)}권")
        
        for idx, book in enumerate(targets):
            isbn = book.get("isbn")
            title = book.get("title", "알 수 없는 도서")
            b_type = book.get("type", "Unknown")
            if not isbn:
                continue
            
            # 인메모리 Job Store에 신규 생성 태스크 예약 등록
            job = store.create(isbn, region)
            # 주간 배치는 대량(여러 개)이므로, APScheduler 스레드 루프가 막히지 않도록 각각 백그라운드 스레드로 분할 처리
            t = threading.Thread(
                target=_run_scheduled_job,
                args=(job.id, isbn, region),
                daemon=True
            )
            t.start()
            print(f"  [{idx+1}/{len(targets)}] 태스크 시작 -> 타입 {b_type} | 제목: {title} | ISBN: {isbn} (JobID: {job.id})")
            
    except Exception as e:
        print(f"[Scheduler] 주간 큐레이션 배치 실행 오류: {e}")


# 매주 월요일 오전 00시 00분에 주간 큐레이션 배치 스케줄 등록
scheduler.add_job(
    weekly_curation_job,
    "cron",
    day_of_week="mon",
    hour=0,
    minute=0,
    args=["11", "20"], # 기본값: 서울시(11), 20대(20) 기준 자동 큐레이션
    id="weekly_booktik_curation",
    replace_existing=True
)
