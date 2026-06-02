# 프로토타입 API 서버 (FastAPI + BackgroundTasks)

PoC에서 검증한 생성 파이프라인(`poc/generate.py`)을 비동기 Job API로 감쌌다.
`poc/` 모듈(LOD/정보나루 → Gemini → TTS → 렌더)을 그대로 재사용한다.

## 실행
```bash
cd api
# poc 가상환경 재사용 (poc/.venv) 또는 새로 생성
../poc/.venv/bin/pip install -r requirements.txt
export GEMINI_API_KEY=...    LIBRARY_API_KEY=...
../poc/.venv/bin/python -m uvicorn main:app --reload --port 8000
```

## 엔드포인트
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/generate` | `{isbn, region}` → `{job_id}` (백그라운드 생성 시작) |
| GET | `/api/job/{id}` | Job 상태/단계/결과 경로 (`queued`→`running`→`done`/`failed`) |
| GET | `/api/jobs` | 전체 Job 목록 |
| GET | `/api/trending?search_date=YYYY-MM-DD` | hotTrend 화제 도서(타입 C) |
| GET | `/api/locate/{isbn}?region=11` | 소장 도서관(가까운 곳 안내) |
| GET | `/video/{job_id}` | 완성 MP4 다운로드 |
| GET | `/health` | 헬스체크 + 키 주입 여부 |

생성 중에도 단계가 실시간 반영된다: `서지/이용분석 → Gemini 대본 → Edge TTS →
표지 배경+locate → SRT 자막 → FFmpeg 렌더 → 완료`.

```bash
curl -X POST localhost:8000/api/generate -H 'Content-Type: application/json' \
     -d '{"isbn":"9788937473135","region":"11"}'
# {"job_id":"...","status":"queued"}
curl localhost:8000/api/job/<job_id>
```

## 정식 단계 교체 지점
- 인메모리 `JobStore` → Redis/DB (재시작 내구성, 다중 워커 공유)
- `BackgroundTasks` → Celery/RQ (CPU 무거운 FFmpeg 렌더를 워커 프로세스로 분리)
- APScheduler로 매주 월요일 `build_weekly_targets`(A·B·C) 자동 배치
- 배경 이미지: PoC 그라데이션/표지 → Pexels 장르 이미지

## 운영 메모
- FFmpeg 렌더는 CPU 무거운 동기 작업이라 정식에서는 별도 워커로 분리 권장.
  현재 스켈레톤은 BackgroundTasks(스레드풀)에서 실행해도 이벤트 루프를 막지 않음(검증).
