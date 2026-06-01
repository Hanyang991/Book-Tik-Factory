"""
Book-Tik Factory — PoC pipeline (single ISBN vertical slice).

Verifies the risky path end-to-end with REAL services:
  LOD SPARQL (verified predicates) -> Gemini 2.5 Flash -> Edge TTS
  -> background image -> char-weighted SRT -> FFmpeg render (subtitles + QR overlay)

Not covered here (blocked on 정보나루 key activation): 회전율 산출, hotTrend, locate.
Background uses a generated gradient (Pexels API is the production source).
"""
import os
import time
import asyncio
import subprocess

import edge_tts
import qrcode
from PIL import Image
from SPARQLWrapper import SPARQLWrapper, JSON
from google import genai
from google.genai import types

LOD_ENDPOINT = "https://lod.nl.go.kr/sparql"
FONT = "NanumGothic"
OUT = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT, exist_ok=True)

_genai = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SYSTEM_PROMPT = """당신은 유튜브 쇼츠/인스타 릴스 전문 카피라이터입니다.
도서관 사서가 제공한 책 정보로 1분 분량(약 150~180자)의 숏폼 북트레일러 대본을 씁니다.
규칙:
1. 첫 문장은 시청자가 멈춰서 볼 질문/충격적 상황으로 시작
2. 결말·핵심 반전은 스포일러 금지
3. 마지막 문장은 "뒷이야기가 궁금하다면 지금 도서관에서 빌려보세요"로 마무리
4. 한 문장씩 줄바꿈하여 출력하고, 대본 외 부가설명은 쓰지 않음"""


def _clean(v: str) -> str:
    # NLK ontobase 엔진이 리터럴 끝에 '~'를 덧붙임 -> 제거
    return v.rstrip("~").strip() if v else v


def fetch_bibliographic_data(isbn: str) -> dict:
    """국가서지 LOD에서 서지정보 조회 (라이브 검증된 술어: bibo:isbn / dcterms:title / dc:creator / dcterms:subject->rdfs:label)."""
    q = f"""
    PREFIX bibo: <http://purl.org/ontology/bibo/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?title ?author ?subjectLabel WHERE {{
      ?work bibo:isbn "{isbn}" .
      OPTIONAL {{ ?work dcterms:title ?title }}
      OPTIONAL {{ ?work dc:creator ?author }}
      OPTIONAL {{ ?work dcterms:subject ?s . ?s rdfs:label ?subjectLabel }}
    }} LIMIT 1
    """
    s = SPARQLWrapper(LOD_ENDPOINT)
    s.setQuery(q)
    s.setReturnFormat(JSON)
    s.setTimeout(40)
    rows = s.query().convert()["results"]["bindings"]
    if not rows:
        return {"isbn": isbn, "title": "", "author": "", "subject": ""}
    r = rows[0]
    return {
        "isbn": isbn,
        "title": _clean(r.get("title", {}).get("value", "")),
        "author": _clean(r.get("author", {}).get("value", "")),
        "subject": _clean(r.get("subjectLabel", {}).get("value", "")),
    }


def generate_script(book: dict, retries: int = 6) -> str:
    user = f"""책 제목: {book.get('title','')}
저자: {book.get('author','')}
주제 분류: {book.get('subject','')}

위 정보로 숏폼 북트레일러 대본을 작성해줘."""
    last = None
    for i in range(retries):
        try:
            r = _genai.models.generate_content(
                model="gemini-2.5-flash",
                contents=user,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            return r.text.strip()
        except Exception as e:  # 503 high-demand 등 일시 오류 재시도
            last = e
            time.sleep(6)
    raise RuntimeError(f"Gemini failed after {retries} tries: {last}")


def generate_tts(script: str, path: str) -> str:
    async def _run():
        c = edge_tts.Communicate(script, "ko-KR-SunHiNeural", rate="+0%", pitch="+0Hz")
        await c.save(path)
    asyncio.run(_run())
    return path


def make_background(path: str, size=(1080, 1920)) -> str:
    # PoC용 세로형 그라데이션 배경 (정식 서비스는 Pexels API 장르 이미지)
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    top, bot = (24, 26, 54), (90, 40, 70)
    for y in range(h):
        t = y / h
        px_row = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = px_row
    img.save(path)
    return path


def generate_qr(url: str, path: str) -> str:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(url)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(path)
    return path


def get_audio_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def fmt_time(sec: float) -> str:
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60); ms = int((sec % 1) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def generate_srt(script: str, audio_path: str, srt_path: str) -> str:
    sents = [s.strip() for s in script.split("\n") if s.strip()]
    dur = get_audio_duration(audio_path)
    total = sum(len(s) for s in sents) or 1
    lines, cur = [], 0.0
    for i, s in enumerate(sents):
        seg = dur * (len(s) / total)
        lines += [str(i + 1), f"{fmt_time(cur)} --> {fmt_time(cur + seg)}", s, ""]
        cur += seg
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return srt_path


def render_video(audio, image, srt, out_path, qr=None) -> str:
    dur = get_audio_duration(audio)
    style = (f"subtitles={srt}:force_style='FontName={FONT},Bold=1,FontSize=22,"
             "PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2'")
    base_vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{style}"
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", image, "-i", audio]
    if qr:
        cmd += ["-i", qr]
        cmd += ["-filter_complex",
                f"[0:v]{base_vf}[bg];[2:v]scale=240:240[q];"
                f"[bg][q]overlay=W-w-60:H-h-200:enable='gte(t,{dur-3:.2f})'[v]",
                "-map", "[v]", "-map", "1:a"]
    else:
        cmd += ["-vf", base_vf]
    cmd += ["-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def run(isbn: str):
    print(f"[1/6] LOD 서지조회 isbn={isbn}")
    book = fetch_bibliographic_data(isbn)
    print("     ->", book)
    print("[2/6] Gemini 대본 생성")
    script = generate_script(book)
    print("     ->", script.replace("\n", " / ")[:200])
    base = os.path.join(OUT, isbn)
    print("[3/6] Edge TTS")
    audio = generate_tts(script, base + ".mp3")
    print("     -> audio", round(get_audio_duration(audio), 1), "s")
    print("[4/6] 배경 이미지 + QR")
    image = make_background(base + ".jpg")
    qr = generate_qr(f"https://booktik.example/locate?isbn={isbn}", base + "_qr.png")
    print("[5/6] SRT 자막 (글자수 가중)")
    srt = generate_srt(script, audio, base + ".srt")
    print("[6/6] FFmpeg 렌더링 (자막 + QR overlay)")
    video = render_video(audio, image, srt, base + ".mp4", qr=qr)
    size = os.path.getsize(video)
    vdur = get_audio_duration(video)
    print(f"DONE -> {video} ({size} bytes, {round(vdur,1)}s)")
    return video


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "9788937473135")
