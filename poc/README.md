# PoC — 단일 ISBN 수직 슬라이스

프로토타입(전체 자동화)으로 가기 전에 **가장 리스크 큰 데이터·AI 경로가 실제로 되는지**만
얇게 검증하는 PoC다. ISBN 1개로 `LOD 서지조회 → 대본 → TTS → 배경 → 자막 → MP4(자막+QR)`까지
실행한다.

## 검증 결과 (라이브 실측)

| 항목 | 상태 | 비고 |
|------|------|------|
| 국가서지 LOD SPARQL | ✅ 동작 | 실제 술어 확인: `bibo:isbn`(하이픈 없는 ISBN-13), `dcterms:title`, `dc:creator`(저자명), `dcterms:subject`→`rdfs:label`(주제어). `schema.org`/`isbn13`은 0건. |
| Gemini 2.5 Flash (`google-genai`) | ✅ 동작 | 503(고수요) 간헐 발생 → 재시도 로직 포함 |
| Edge TTS | ✅ 동작 | `ko-KR-SunHiNeural`, rate/pitch 부호 필수(`+0%`/`+0Hz`) |
| FFmpeg 렌더링 + 한글 자막 + QR overlay | ✅ 동작 | 1080×1920. 자막은 **문장별 TTS 실측 길이**로 싱크(누적 밀림 제거), QR(라벨 카드)은 나레이션 뒤 무음 아웃트로에 중앙 표시 → 자막과 미겹침 |
| 정보나루(회전율·hotTrend·locate) | ✅ 동작 | 키 활성화 후 5개 엔드포인트 검증. `usageAnalysisList`/`hotTrend`/`libSrchByBook`/`bookExist`/`loanItemSrch`. 상세는 [`RESULTS.md`](RESULTS.md) |

> LOD 엔진(ontobase)은 리터럴 끝에 `~`를 덧붙이고 `<subj> ?p ?o` 형태 쿼리에서 오류가 나므로,
> 술어를 명시한 패턴으로 조회하고 값 끝의 `~`를 제거한다(`pipeline._clean`).
>
> 정보나루 `usageAnalysisList`가 책소개·키워드·실제 표지를 주므로, 대본 품질과 배경이
> LOD만 쓸 때보다 좋다. `generate.py`는 정보나루를 1차 소스, LOD를 폴백으로 둔다.

## 실행

```bash
cd poc
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# 시스템 의존: ffmpeg, 한글 폰트(예: sudo apt-get install -y fonts-nanum)

export GEMINI_API_KEY=...        # https://aistudio.google.com/apikey
export LIBRARY_API_KEY=...       # 정보나루 인증키(활성화 필요) — LOD/Gemini PoC엔 불필요

python pipeline.py 9788937473135   # LOD 전용 최소 경로(키 없이 검증 가능)
python generate.py 9788937473135  # 정보나루+LOD 통합(표지 배경·locate, LIBRARY_API_KEY 필요)
python curate.py                  # 회전율 기반 주간 자동 선정(타입 A/B/C) 리포트
python curate.py --videos         # 선정 + 선정된 책 트레일러 일괄 생성
python batch_demo.py              # 여러 권 일괄 생성 + 릴 concat(발표용)
python probe_data4library.py      # 정보나루 5개 엔드포인트 점검
# -> outputs/<isbn>.mp4 , outputs/demo_reel.mp4
```

## 파일

| 파일 | 설명 |
|------|------|
| `pipeline.py` | LOD 전용 최소 경로(서지→대본→TTS→배경→자막→렌더) |
| `enrich.py` | 정보나루 5개 함수(이용분석·화제·소장·인기·근사 회전율) |
| `generate.py` | 정보나루+LOD 통합 생성기(표지 배경, locate, 문장별 실측 싱크, QR 아웃트로) |
| `curate.py` | 회전율 기반 주간 자동 선정(타입 A/B/C) + `--videos` 일괄 생성 |
| `batch_demo.py` | 여러 권 일괄 생성 + 릴 concat |
| `probe_data4library.py` | 정보나루 응답 형태 점검 |
| `RESULTS.md` | 검증 결과 요약 |

## 한계 (의도된 PoC 범위)

- 배경: 표지가 있으면 실제 표지(흐림 배경+카드), 없으면 그라데이션 폴백. 정식은 Pexels 보강 가능.
- 근사 회전율은 `loanCnt / 지역 소장 도서관 수` 프록시. 정식은 사서 CSV(솔로몬)로 보강.
- 회전율 기반 선정(타입 A/B/C)은 `curate.py`로 구현, API는 `GET /api/curation`. 정식은 APScheduler 주간 배치로 확장.
- 무료 티어 한도: Gemini 무료 등급은 모델당 **일 20요청** 제한이 있어 대량 일괄 생성 시 분산/유료 등급 필요.
- 자동화(APScheduler)·Job 큐(Celery)는 프로토타입 단계에서 추가(`api/README.md` 참고).
