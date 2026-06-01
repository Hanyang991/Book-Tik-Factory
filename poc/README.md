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
| FFmpeg 렌더링 + 한글 자막 + QR overlay | ✅ 동작 | 1080×1920, 글자수 가중 SRT, QR은 마지막 3초 우하단 |
| 정보나루(회전율·hotTrend·locate) | ⚠️ 미검증 | 인증키 **활성화 전**(`vitalizationErr`). 활성화 후 `probe_data4library.py`로 검증 |

> LOD 엔진(ontobase)은 리터럴 끝에 `~`를 덧붙이고 `<subj> ?p ?o` 형태 쿼리에서 오류가 나므로,
> 술어를 명시한 패턴으로 조회하고 값 끝의 `~`를 제거한다(`pipeline._clean`).

## 실행

```bash
cd poc
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# 시스템 의존: ffmpeg, 한글 폰트(예: sudo apt-get install -y fonts-nanum)

export GEMINI_API_KEY=...        # https://aistudio.google.com/apikey
export LIBRARY_API_KEY=...       # 정보나루 인증키(활성화 필요) — LOD/Gemini PoC엔 불필요

python pipeline.py 9788937473135   # 인자 생략 시 기본 ISBN
# -> outputs/<isbn>.mp4
```

## 한계 (의도된 PoC 범위)

- 배경 이미지는 PoC용 그라데이션(Pillow). 정식은 Pexels API 장르 이미지.
- 정보나루 의존 기능(회전율 기반 선정, 화제 도서 hotTrend, 소장 도서관 locate)은
  키 활성화 후 별도 검증.
- 자동화(스케줄러)·Job 큐·API 서버는 프로토타입 단계에서 추가.
