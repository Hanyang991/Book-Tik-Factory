# PoC 검증 결과 (라이브 실측, 2026-06)

단일 ISBN 수직 슬라이스로 "되는지"를 확인한 결과. 모든 외부 의존을 실제 호출로 검증했다.

## 한눈에

| 리스크 | 결과 | 근거 |
|--------|------|------|
| 국가서지 LOD SPARQL 술어 | ✅ 해소 | `bibo:isbn`/`dcterms:title`/`dc:creator`/`dcterms:subject`→`rdfs:label` |
| Gemini 2.5 Flash (`google-genai`) | ✅ 동작 | 503 고수요 간헐 → 재시도 6회 |
| Edge TTS (한국어) | ✅ 동작 | `ko-KR-SunHiNeural`, rate/pitch 부호 필수 |
| FFmpeg 자막 + QR overlay | ✅ 동작 | 1080×1920, 글자수 가중 SRT, QR 마지막 3초 |
| 정보나루 회전율/화제/소장 | ✅ 동작 | 키 활성화 후 5개 엔드포인트 전부 검증 |

## 정보나루(data4library) 검증된 엔드포인트

모두 GET, 공통 파라미터 `authKey`, `format=json`.

| 엔드포인트 | 용도 | 핵심 응답 |
|-----------|------|-----------|
| `usageAnalysisList` | 도서별 이용분석 | `book.description`(책소개), `bookImageURL`(표지), `class_nm`(분류), `loanCnt`(총대출), `keywords`(가중 50개), `loanHistory`(월별) |
| `hotTrend` | 대출 급상승(타입 C) | `results[0].result.docs[].doc`: `bookname`, `isbn13`, `baseWeekRank`, `pastWeekRank`, `difference`(상승폭) |
| `libSrchByBook` | 소장 도서관(locate) | `numFound`(소장 도서관 수), `libs[].lib`: `libName`, `address` — **region 필수** |
| `bookExist` | 특정 도서관 소장/대출가능 | `result.hasBook`(Y/N), `loanAvailable`(Y/N) |
| `loanItemSrch` | 지역·연령 인기대출 | `docs[].doc`: `bookname`, `isbn13`, `loan_count` |

주의:
- `itemSrchByLib`는 **존재하지 않는 엔드포인트**(404). 회전율은 아래 프록시로 산출.
- `libSrchByBook`는 `region`(법정동 코드, 11=서울) 미지정 시 "지역코드를 확인" 오류.

### 회전율(turnover) 산출 방식
정보나루는 임의 도서의 '도서관별 장서 수'를 직접 주지 않는다. 따라서
**근사 회전율 = `usageAnalysisList.loanCnt` / `libSrchByBook.numFound`(지역 소장 도서관 수)**
로 산출한다(`enrich.estimate_turnover`). 정식 단계에서 사서 CSV(솔로몬)로 보강.

## 발견 — 대본 입력이 크게 풍부해짐
`usageAnalysisList`가 **책소개·가중 키워드·실제 표지**를 주므로, LOD(제목/저자/주제)만
쓸 때보다 대본 품질과 영상 배경(실제 표지)이 확연히 좋아졌다. 그래서 본 PoC의 생성
경로는 정보나루를 1차 소스로, LOD를 폴백으로 둔다(`generate.build_book`).

## 엔진 특이점 (LOD ontobase)
- 리터럴 끝에 `~`를 덧붙임 → `_clean()`으로 제거.
- `<subject> ?p ?o` 형태의 광범위 스캔/FILTER는 타임아웃/오류 → 술어를 명시해 조회.

## 산출물
- `pipeline.py` : LOD 전용 최소 경로(키 없이 검증 가능)
- `enrich.py`   : 정보나루 5개 함수(이용분석·화제·소장·인기·회전율)
- `generate.py` : 정보나루+LOD 통합 생성기(표지 배경, locate, 단계 콜백)
- `batch_demo.py` : 여러 권 일괄 생성 + 릴 concat (발표용)
- `probe_data4library.py` : 정보나루 엔드포인트 점검 스크립트

## 다음 단계
- 회전율 기반 선정(타입 A/B) 배치: `loanItemSrch` 후보 풀 → `estimate_turnover` 정렬.
- 주간 자동화(APScheduler) + Job 큐(Celery)로 프로토타입 확장(`api/` 참고).
