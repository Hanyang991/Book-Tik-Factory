"""
Book-Tik Factory — 정보나루 연동 강화 생성기 (단일 ISBN).

pipeline.py(검증된 LOD/TTS/SRT/렌더 경로) 위에 정보나루(usageAnalysisList)의
책소개·키워드·실제 표지·분류를 입력으로 더해 대본 품질과 배경을 끌어올린다.
또 libSrchByBook으로 '가까운 소장 도서관'을 자막/QR에 연결한다.

정보나루 키가 없거나 미소장이면 LOD 서지만으로 자동 폴백한다.
"""
import io
import os
import textwrap

import requests
from PIL import Image, ImageFilter
from google.genai import types

import enrich
import pipeline as P

OUT = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT, exist_ok=True)

RICH_SYSTEM = """당신은 유튜브 쇼츠/인스타 릴스 전문 북트레일러 카피라이터입니다.
사서가 제공한 책 정보(소개·키워드)로 1분(약 150~180자) 숏폼 대본을 씁니다.
규칙:
1. 첫 문장은 시청자가 멈춰서 볼 질문/충격적 상황으로 시작
2. 결말·핵심 반전 스포일러 금지
3. 제공된 키워드를 자연스럽게 녹일 것
4. 마지막 문장은 "지금 가까운 도서관에서 만나보세요"로 마무리
5. 한 문장씩 줄바꿈, 대본 외 부가설명 금지"""


def build_book(isbn: str) -> dict:
    """정보나루 우선, 실패 시 LOD 폴백."""
    book = {}
    try:
        if os.environ.get("LIBRARY_API_KEY"):
            u = enrich.get_book_usage(isbn)
            if u.get("title"):
                book = u
    except Exception as e:
        print("  (정보나루 조회 실패, LOD로 폴백):", e)
    if not book.get("title"):
        book = P.fetch_bibliographic_data(isbn)
        book.setdefault("keywords", [])
        book.setdefault("description", "")
        book.setdefault("cover_url", "")
        book.setdefault("genre", book.get("subject", ""))
    return book


def rich_script(book: dict) -> str:
    user = f"""책 제목: {book.get('title','')}
저자: {book.get('author','')}
분류: {book.get('genre','')}
키워드: {', '.join(book.get('keywords', [])) or '없음'}
책 소개: {(book.get('description') or '정보 없음')[:600]}

위 정보로 숏폼 북트레일러 대본을 작성해줘."""
    import time
    last = None
    for _ in range(6):
        try:
            r = P._genai.models.generate_content(
                model="gemini-2.5-flash",
                contents=user,
                config=types.GenerateContentConfig(system_instruction=RICH_SYSTEM),
            )
            return r.text.strip()
        except Exception as e:
            last = e
            time.sleep(6)
    raise RuntimeError(f"Gemini 실패: {last}")


def cover_background(cover_url: str, path: str, size=(1080, 1920)) -> str:
    """실제 표지를 흐림 처리해 배경으로 깔고, 표지 카드를 상단 중앙에 얹는다.
    표지가 없으면 pipeline의 그라데이션으로 폴백."""
    if not cover_url:
        return P.make_background(path, size)
    try:
        raw = requests.get(cover_url, timeout=20).content
        cover = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return P.make_background(path, size)

    w, h = size
    # 1) 배경: 표지를 화면 가득 채우도록 확대 후 블러 + 어둡게
    bg = cover.resize((w, int(w * cover.height / cover.width)))
    if bg.height < h:
        bg = cover.resize((int(h * cover.width / cover.height), h))
    bg = bg.crop(((bg.width - w) // 2, (bg.height - h) // 2,
                  (bg.width - w) // 2 + w, (bg.height - h) // 2 + h))
    bg = bg.filter(ImageFilter.GaussianBlur(28))
    bg = Image.blend(bg, Image.new("RGB", size, (10, 10, 20)), 0.45)
    # 2) 표지 카드(상단 1/3 지점에 중앙 배치)
    card_w = int(w * 0.5)
    card = cover.resize((card_w, int(card_w * cover.height / cover.width)))
    bg.paste(card, ((w - card.width) // 2, int(h * 0.16)))
    bg.save(path)
    return path


def run(isbn: str, region: str = "11", progress=None) -> str:
    def step(label: str):
        print(label)
        if progress:
            progress(label.split("]")[-1].strip() if "]" in label else label)

    step(f"[1/6] 서지/이용분석 isbn={isbn}")
    book = build_book(isbn)
    print("     ->", book.get("title"), "/", book.get("author"),
          "/ 키워드", book.get("keywords", [])[:5])

    step("[2/6] Gemini 대본(소개+키워드 반영)")
    script = rich_script(book)
    print("     ->", script.replace("\n", " / ")[:160])

    base = os.path.join(OUT, isbn)
    step("[3/6] Edge TTS")
    audio = P.generate_tts(script, base + ".mp3")

    step("[4/6] 표지 배경 + locate(QR)")
    image = cover_background(book.get("cover_url", ""), base + ".jpg")
    locate = {"total": 0, "libraries": []}
    try:
        if os.environ.get("LIBRARY_API_KEY"):
            locate = enrich.find_holding_libraries(isbn, region=region, limit=5)
            print(f"     -> 소장 도서관 {locate['total']}곳 (지역 {region})")
    except Exception as e:
        print("     (locate 실패):", e)
    qr = P.generate_qr(f"https://booktik.example/locate?isbn={isbn}&region={region}", base + "_qr.png")

    step("[5/6] SRT 자막(글자수 가중)")
    srt = P.generate_srt(script, audio, base + ".srt")

    step("[6/6] FFmpeg 렌더(자막 + QR overlay)")
    video = P.render_video(audio, image, srt, base + ".mp4", qr=qr)
    print(f"DONE -> {video} ({os.path.getsize(video)} bytes, "
          f"{round(P.get_audio_duration(video),1)}s)")
    return video


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "9788937473135")
