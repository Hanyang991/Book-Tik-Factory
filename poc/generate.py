"""
Book-Tik Factory — 정보나루 연동 강화 생성기 (단일 ISBN).

pipeline.py(검증된 LOD/TTS/렌더 경로) 위에 정보나루(usageAnalysisList)의
책소개·키워드·실제 표지·분류를 입력으로 더해 대본 품질과 배경을 끌어올린다.
또 libSrchByBook으로 '가까운 소장 도서관'을 QR에 연결한다.

자막 싱크: 글자수 추정이 아니라 '문장별 TTS를 따로 만들어 각 문장의 실제 길이를
ffprobe로 측정'해 자막 타이밍을 1:1로 맞춘다(누적 밀림 제거).
QR: 나레이션이 끝난 뒤 무음 아웃트로 구간에서만 화면 중앙에 크게(라벨 포함) 띄워
자막과 절대 겹치지 않게 한다.

정보나루 키가 없거나 미소장이면 LOD 서지만으로 자동 폴백한다.
"""
import io
import os
import asyncio
import subprocess

import edge_tts
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from google.genai import types

import enrich
import pipeline as P

OUT = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT, exist_ok=True)

FONT_FILE = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
TAIL_SEC = 2.6  # 나레이션 뒤 QR 전용 아웃트로 길이

RICH_SYSTEM = """당신은 유튜브 쇼츠/인스타 릴스 전문 북트레일러 카피라이터입니다.
사서가 제공한 책 정보(소개·키워드)로 약 45초(약 130~160자) 숏폼 대본을 씁니다.
규칙:
1. 첫 문장은 시청자가 멈춰서 볼 질문/충격적 상황으로 시작
2. 결말·핵심 반전 스포일러 금지
3. 제공된 키워드를 자연스럽게 녹일 것
4. 마지막 문장은 책에 대한 '후킹(궁금증 유발)'으로 끝낼 것. "도서관에서 빌려보세요"
   같은 안내·호출(CTA) 문구는 절대 쓰지 말 것(그 안내는 영상이 QR로 따로 처리함)
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


def _sanitize(line: str) -> str:
    """대본 한 줄에서 마크다운 강조/불릿을 제거(자막·TTS에 그대로 노출되지 않게)."""
    import re
    line = re.sub(r"[*_`#]", "", line)          # *강조*, `코드`, # 헤더 제거
    line = re.sub(r"^\s*[-•]\s*", "", line)       # 불릿 제거
    return line.strip()


def split_sentences(script: str) -> list[str]:
    return [c for c in (_sanitize(s) for s in script.split("\n")) if c]


def tts_per_sentence(sentences: list[str], base: str, tail: float = TAIL_SEC):
    """문장별로 TTS를 만들어 각 문장의 실제 길이를 측정한 뒤 하나로 이어붙인다.

    반환: (audio_path, durations[문장별], narration_dur, total_dur)
    - durations는 각 문장의 실측 길이(초) → 자막 싱크의 근거.
    - 끝에 tail초 무음을 붙여 QR 전용 아웃트로 구간을 만든다.
    """
    parts, durations = [], []

    async def _save(text: str, path: str):
        c = edge_tts.Communicate(text, "ko-KR-SunHiNeural", rate="+0%", pitch="+0Hz")
        await c.save(path)

    for i, s in enumerate(sentences):
        p = f"{base}_s{i}.mp3"
        asyncio.run(_save(s, p))
        durations.append(P.get_audio_duration(p))
        parts.append(p)

    # 무음 아웃트로(QR 전용)
    silence = f"{base}_sil.mp3"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-f", "lavfi", "-i",
         "anullsrc=channel_layout=mono:sample_rate=24000",
         "-t", f"{tail}", "-c:a", "libmp3lame", silence],
        check=True, capture_output=True)
    parts.append(silence)

    # concat (재인코딩으로 헤더/타임스탬프 차이 흡수)
    listfile = f"{base}_concat.txt"
    with open(listfile, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    audio = f"{base}.mp3"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c:a", "libmp3lame", audio],
        check=True, capture_output=True)

    narration = sum(durations)
    total = P.get_audio_duration(audio)
    return audio, durations, narration, total


def build_srt(sentences: list[str], durations: list[float], srt_path: str) -> str:
    """문장별 실측 길이로 자막 타이밍을 만든다(누적 밀림 없음)."""
    lines, cur = [], 0.0
    for i, (s, d) in enumerate(zip(sentences, durations)):
        lines += [str(i + 1), f"{P.fmt_time(cur)} --> {P.fmt_time(cur + d)}", s, ""]
        cur += d
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return srt_path


def qr_with_caption(url: str, path: str, lib_hint: str = "") -> str:
    """QR 아래에 용도 라벨을 박은 카드 이미지를 만든다.
    '가까운 도서관 정보를 나타내는 QR'임을 시각적으로 표시."""
    import qrcode
    qr_img = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr_img.add_data(url)
    qr_img.make(fit=True)
    qr = qr_img.make_image(fill_color="black", back_color="white").convert("RGB")
    qr = qr.resize((460, 460))

    title = "가까운 도서관에서 만나보세요"
    sub = lib_hint or "QR 스캔 → 소장 도서관 안내"
    pad, gap = 40, 18
    try:
        f_title = ImageFont.truetype(FONT_FILE, 34)
        f_sub = ImageFont.truetype(FONT_FILE, 26)
    except Exception:
        f_title = f_sub = ImageFont.load_default()

    card_w = qr.width + pad * 2
    card_h = qr.height + pad * 2 + 96
    card = Image.new("RGB", (card_w, card_h), (255, 255, 255))
    d = ImageDraw.Draw(card)
    card.paste(qr, (pad, pad))

    def _center(text, font, y, fill):
        bbox = d.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        d.text(((card_w - w) // 2, y), text, font=font, fill=fill)

    y0 = pad + qr.height + gap
    _center(title, f_title, y0, (20, 20, 30))
    _center(sub, f_sub, y0 + 42, (120, 60, 90))
    card.save(path)
    return path


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
    bg = cover.resize((w, int(w * cover.height / cover.width)))
    if bg.height < h:
        bg = cover.resize((int(h * cover.width / cover.height), h))
    bg = bg.crop(((bg.width - w) // 2, (bg.height - h) // 2,
                  (bg.width - w) // 2 + w, (bg.height - h) // 2 + h))
    bg = bg.filter(ImageFilter.GaussianBlur(28))
    bg = Image.blend(bg, Image.new("RGB", size, (10, 10, 20)), 0.45)
    card_w = int(w * 0.5)
    card = cover.resize((card_w, int(card_w * cover.height / cover.width)))
    bg.paste(card, ((w - card.width) // 2, int(h * 0.16)))
    bg.save(path)
    return path


def render(audio, image, srt, qr, out_path, narration_dur: float) -> str:
    """자막은 나레이션 구간에만, QR(라벨 카드)은 아웃트로 구간에만 중앙에 크게.
    두 요소의 표시 구간이 분리되어 겹치지 않는다."""
    style = (f"subtitles={srt}:force_style='FontName={P.FONT},Bold=1,FontSize=19,"
             "PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=3,Shadow=1,"
             "Alignment=2,MarginV=40'")
    base_vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{style}"
    cmd = ["ffmpeg", "-nostdin", "-y", "-loop", "1", "-i", image, "-i", audio, "-i", qr,
           "-filter_complex",
           f"[0:v]{base_vf}[bg];[2:v]scale=720:-1[q];"
           f"[bg][q]overlay=(W-w)/2:(H-h)/2:enable='gte(t,{narration_dur:.2f})'[v]",
           "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
           "-pix_fmt", "yuv420p", "-shortest", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


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
    sentences = split_sentences(script)
    print("     ->", " / ".join(sentences)[:160])

    base = os.path.join(OUT, isbn)
    step("[3/6] 문장별 Edge TTS + 실측 길이 측정")
    audio, durations, narration, total = tts_per_sentence(sentences, base)
    print(f"     -> 나레이션 {round(narration,1)}s + 아웃트로 {TAIL_SEC}s = {round(total,1)}s")

    step("[4/6] 표지 배경 + locate(QR 라벨)")
    image = cover_background(book.get("cover_url", ""), base + ".jpg")
    locate = {"total": 0, "libraries": []}
    try:
        if os.environ.get("LIBRARY_API_KEY"):
            locate = enrich.find_holding_libraries(isbn, region=region, limit=5)
            print(f"     -> 소장 도서관 {locate['total']}곳 (지역 {region})")
    except Exception as e:
        print("     (locate 실패):", e)
    hint = f"우리 지역 {locate['total']}곳 소장" if locate["total"] else "QR 스캔 → 소장 도서관 안내"
    qr = qr_with_caption(
        f"https://booktik.example/locate?isbn={isbn}&region={region}",
        base + "_qr.png", lib_hint=hint)

    step("[5/6] 실측 자막(문장별 길이 기반)")
    srt = build_srt(sentences, durations, base + ".srt")

    step("[6/6] FFmpeg 렌더(자막 구간 + QR 아웃트로 분리)")
    video = render(audio, image, srt, qr, base + ".mp4", narration)
    print(f"DONE -> {video} ({os.path.getsize(video)} bytes, "
          f"{round(P.get_audio_duration(video),1)}s)")
    return video


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "9788937473135")
