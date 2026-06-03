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
from dotenv import load_dotenv
load_dotenv()
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

FONT_FILE = "C:/Windows/Fonts/batang.ttc" if os.name == "nt" else "/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf"
TAIL_SEC = 2.6  # 나레이션 뒤 QR 전용 아웃트로 길이

RICH_SYSTEM = """당신은 대한민국 최고의 숏폼 북트레일러 카피라이터입니다.
도서관 사서가 제공한 책 정보를 바탕으로, 시청자가 스크롤을 멈추고 끝까지 보게 만드는
숏폼 나레이션 대본을 작성합니다.

## ⚠️ 절대적 대원칙: 팩트 기반 작성 (날조 및 왜곡 절대 금지)
1. **스토리 및 설정 날조 금지**: 제공된 '책 소개', '키워드', '제목' 정보에 없는 캐릭터, 줄거리, 구체적 사건, 자극적인 에피소드를 절대 지어내지 마세요.
   - *나쁜 예시*: 『82년생 김지영』 책 정보에 기반해 "어느 날 갑자기 아내가 다른 사람의 목소리로 말을 건넸다" 같은 자극적이고 공포/판타지 영화 같은 설정을 무단으로 지어내는 행위.
   - *좋은 예시*: 제공된 책 정보에 충실하게 "평범해 보이는 일상 뒤에 숨겨진 차별과 아픔, 누군가의 딸이자 아내인 지영의 이야기" 등 실제 도서의 감정과 주제 의식을 중심으로 서술.
2. **장르 왜곡 금지**: 평범한 현대 소설, 에세이, 자기계발서를 스릴러, 호러, 판타지, 미스터리 장르인 것처럼 속이는 낚시성 문구를 쓰지 마세요. 도서 고유의 장르와 분위기를 반드시 유지하세요.
3. **정확한 정보 활용**: 훅(Hook)을 만들 때도 책의 핵심 주제, 실존하는 핵심 문장, 혹은 실제 수록된 고민을 활용하여 긴장감을 높여야 하며, 가짜 사실이나 낚시성 미스터리를 만들어 내지 마세요.

## 장르별 톤 (분류를 보고 자동 판단)
- 소설/문학 → 시네마틱. 영화 예고편처럼 장면을 그려 보여주되, 실제 책에 있는 감정선과 배경을 훼손하지 말 것
- 자기계발/경영 → 동기부여. 청자의 현실 문제를 짚고, 책 속의 통찰을 던질 것
- 에세이/인문 → 감성적 독백. 혼잣말처럼, 담담하지만 울림 있게
- 시/예술 → 시적 리듬. 여백과 호흡을 살릴 것
- 역사/과학/사회 → 다큐멘터리 내레이터. 놀라운 사실로 지적 호기심 자극
- 판타지/SF → 세계관 몰입. 낯선 세계의 문을 여는 느낌
- 그 외 → 위 톤 중 가장 어울리는 것을 자율 선택

## 구조 (4단, 반드시 이 순서)
1. 훅 (1문장): 시청자가 1초 만에 멈출 질문·충격·역설·감각 이미지. (※ 단, 없는 사실을 날조한 낚시는 절대 금지)
2. 상황 (1~2문장): 주인공 또는 핵심 전제를 선명하게 제시.
3. 긴장 (1~2문장): 갈등·반전·의외의 사실로 몰입을 끌어올림.
4. 열린 결말 (1문장): 답을 주지 않는 질문, 또는 여운 있는 한 줄로 마무리.
   ※ "도서관에서 빌려보세요" 같은 CTA는 절대 쓰지 마세요(QR이 대신 처리).

## 문체 규칙
- 감각적 표현: 비유·대비·오감 묘사를 적극 활용. 추상적 설명 금지.
  · 나쁜 예: "이 책은 사랑에 대한 이야기이다"
  · 좋은 예: "사랑이란 단어가 입안에서 녹기도 전에, 그녀는 떠났다"
- 리듬: 짧은 문장과 긴 문장을 의도적으로 교차하여 TTS 호흡감을 만들 것.
  · 예: "그날 밤. / 서른두 해를 살아온 그의 인생이 단 한 문장으로 뒤집혔다."
- 제목·저자: 대본 안에 자연스럽게 녹일 것.
  · 나쁜 예: "『82년생 김지영』이라는 책은..."
  · 좋은 예: "82년생 김지영, 그녀의 인생에 무슨 일이 일어난 걸까?"
- 스포일러: 결말·핵심 반전 절대 금지.
- 키워드: 제공된 키워드를 1~3개 자연스럽게 녹일 것(억지 삽입 금지).

## 형식
- 한 문장씩 줄바꿈 (자막 단위)
- 대본만 출력. 제목·설명·메모·번호 등 부가 텍스트 일체 금지
- 마크다운 서식(*, #, - 등) 사용 금지
"""

# 분량 프리셋 (초 → 한국어 TTS 기준 대략적 글자수)
DURATION_PRESETS = {
    30: (90, 130),
    45: (140, 180),
    60: (200, 250),
}


_book_cache: dict[str, tuple[float, dict]] = {}
_BOOK_CACHE_TTL = 1800  # 30분


def fetch_cover_fallback(isbn: str) -> str | None:
    """정보나루에 표지가 없을 때 알라딘과 YES24에서 긁어서 표지 이미지 URL을 반환."""
    import requests
    from bs4 import BeautifulSoup
    import re

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 1) 알라딘 시도 (가장 빠르고 정확함)
    try:
        url = f"https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget=Book&SearchWord={isbn}"
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # 검색 결과의 ss_book_box 중 첫 번째 책
            book_boxes = soup.find_all('div', class_='ss_book_box')
            if book_boxes:
                first_box = book_boxes[0]
                img = first_box.find('img', class_='front_cover') or first_box.find('img')
                if img and img.get('src'):
                    src = img.get('src')
                    if 'SpineShelf' not in src:
                        # 알라딘은 보통 cover200/ 이나 cover150/ 처럼 작은 이미지를 주는데,
                        # cover500/ 으로 주소를 치환하면 더 선명한 표지를 얻을 수 있음!
                        high_res = src.replace('cover200', 'cover500').replace('cover150', 'cover500')
                        return high_res.split('?')[0]
            
            # 차선책: 그냥 front_cover 클래스 매칭
            covers = soup.find_all('img', class_='front_cover')
            if covers and covers[0].get('src'):
                src = covers[0].get('src')
                high_res = src.replace('cover200', 'cover500').replace('cover150', 'cover500')
                return high_res.split('?')[0]
    except Exception as e:
        print(f"     (알라딘 표지 크롤링 실패): {e}")

    # 2) YES24 시도 (알라딘 실패 시 폴백)
    try:
        url = f"https://www.yes24.com/Product/Search?domain=BOOK&query={isbn}"
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # 광고 영역 등을 배제하고 진짜 상품 목록 ul.yesSchList 내부 첫 번째 상품 찾기
            sch_list = soup.find('ul', class_='yesSchList') or soup.find(id='yesSchList')
            if sch_list:
                first_item = sch_list.find('li')
                if first_item:
                    img = first_item.find('img')
                    if img:
                        src = img.get('data-original') or img.get('src')
                        if src:
                            return src.split('?')[0]
            
            # 차선책: 상품 이미지 클래스 'img_bdr'의 첫 번째 것 가져오기
            img_bdr = soup.find('img', class_='img_bdr')
            if img_bdr:
                src = img_bdr.get('data-original') or img_bdr.get('src')
                if src:
                    return src.split('?')[0]

            # 최종 수단: 정규식으로 대소문자 고려해 Goods/ 와 goods/ 매칭
            urls = re.findall(r'https://image\.yes24\.com/[Gg]oods/\d+/[^"\'\s>]+', r.text)
            for u in urls:
                if any(x in u for x in ['XL', 'L', 'M', 'normal']):
                    return u.split('?')[0].split('"')[0].split("'")[0]
            if urls:
                return urls[0].split('?')[0].split('"')[0].split("'")[0]
    except Exception as e:
        print(f"     (YES24 표지 크롤링 실패): {e}")

    return None


def build_book(isbn: str) -> dict:
    """정보나루 우선, 실패 시 LOD 폴백. 결과를 30분간 캐시."""
    import time as _time
    if isbn in _book_cache:
        cached_at, cached = _book_cache[isbn]
        if _time.time() - cached_at < _BOOK_CACHE_TTL:
            print(f"  [Cache HIT] build_book {isbn}")
            return cached

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

    # 표지가 누락되었거나 빈 값인 경우 크롤링 기반 Fallback 적용
    if not book.get("cover_url"):
        fallback_cover = fetch_cover_fallback(isbn)
        if fallback_cover:
            book["cover_url"] = fallback_cover
            print(f"  [Cover Fallback 성공] {isbn} -> {fallback_cover}")

    _book_cache[isbn] = (_time.time(), book)
    return book


def rich_script(book: dict, duration_sec: int = 30) -> str:
    char_min, char_max = DURATION_PRESETS.get(duration_sec, DURATION_PRESETS[30])
    length_guide = f"약 {duration_sec}초 분량({char_min}~{char_max}자)"

    user = f"""책 제목: {book.get('title','')}
저자: {book.get('author','')}
분류: {book.get('genre','')}
키워드: {', '.join(book.get('keywords', [])) or '없음'}
책 소개: {(book.get('description') or '정보 없음')[:600]}

{length_guide}의 숏폼 북트레일러 나레이션 대본을 작성해줘."""
    import time
    last = None
    for _ in range(6):
        try:
            r = P._genai.models.generate_content(
                model="gemini-3.5-flash",
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
    line = re.sub(r"[*_`#<>~]", "", line)        # *강조*, `코드`, #, <>, ~ 제거(TTS가 기호를 읽지 않게)
    line = re.sub(r"^\s*[-•]\s*", "", line)       # 불릿 제거
    return re.sub(r"\s{2,}", " ", line).strip()


def split_sentences(script: str) -> list[str]:
    return [c for c in (_sanitize(s) for s in script.split("\n")) if c]


def tts_per_sentence(sentences: list[str], base: str, book_title: str = "", tail: float = TAIL_SEC):
    """문장별로 TTS를 만들어 각 문장의 실제 길이를 측정한 뒤 하나로 이어붙인다.

    반환: (audio_path, durations[문장별], narration_dur, total_dur)
    - durations는 각 문장의 실측 길이(초) → 자막 싱크의 근거.
    - 끝에 tail초 무음을 붙여 QR 전용 아웃트로 구간을 만든다.

    싱크 보장: MP3 인코더 딜레이(프레임 패딩)가 문장마다 누적되어 자막이
    밀리는 문제를 방지하기 위해 WAV(PCM)로 중간 처리한다.
      1) 문장별 TTS MP3 → WAV(PCM 48kHz mono) 변환
      2) WAV 기준으로 정확한 sample-level duration 측정
      3) WAV들을 무손실 concat
      4) 최종 concat WAV → MP3 한 번만 인코딩
    """
    wav_parts, durations = [], []

    async def _save(text: str, path: str):
        c = edge_tts.Communicate(text, "ko-KR-SunHiNeural", rate="+0%", pitch="+0Hz")
        await c.save(path)

    for i, s in enumerate(sentences):
        mp3_tmp = f"{base}_s{i}.mp3"
        wav_tmp = f"{base}_s{i}.wav"
        asyncio.run(_save(s, mp3_tmp))
        # MP3 → WAV 변환 (인코더 딜레이 제거, 48kHz mono 통일)
        subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-i", mp3_tmp,
             "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", wav_tmp],
            check=True, capture_output=True)
        durations.append(P.get_audio_duration(wav_tmp))
        wav_parts.append(wav_tmp)

    # 을/를 조사 자동 선택 헬퍼 함수
    def get_josa(word: str) -> str:
        if not word:
            return "을"
        last_char = word[-1]
        if '가' <= last_char <= '힣':
            if (ord(last_char) - 0xAC00) % 28 > 0:
                return "을"
            else:
                return "를"
        return "을"

    outro_text = "가까운 도서관에서 만나보세요."
    if book_title:
        # 부제목이나 정규형 지저분한 타이틀 접미사 제거
        clean_title = book_title.split(":")[0].split("=")[0].split("(")[0].strip()
        josa = get_josa(clean_title)
        outro_text = f"{clean_title}{josa} 가까운 도서관에서 만나보세요."

    # 아웃트로 QR용 음성 안내 생성
    outro_mp3 = f"{base}_outro.mp3"
    outro_wav = f"{base}_outro.wav"
    asyncio.run(_save(outro_text, outro_mp3))
    # MP3 → WAV 변환 (48kHz mono PCM 통일)
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-i", outro_mp3,
         "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", outro_wav],
        check=True, capture_output=True)
    wav_parts.append(outro_wav)

    # 음성 안내 종료 후 화면 여운용 짧은 무음 추가 (1.0초)
    silence = f"{base}_sil.wav"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-f", "lavfi", "-i",
         "anullsrc=channel_layout=mono:sample_rate=48000",
         "-t", "1.0", "-c:a", "pcm_s16le", silence],
        check=True, capture_output=True)
    wav_parts.append(silence)

    # WAV concat (PCM이므로 sample-level 정확도, 인코더 딜레이 없음)
    listfile = f"{base}_concat.txt"
    with open(listfile, "w", encoding="utf-8") as f:
        for p in wav_parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    wav_joined = f"{base}_joined.wav"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c:a", "copy", wav_joined],
        check=True, capture_output=True)

    # 최종 WAV → MP3 변환 (인코딩은 여기서 한 번만)
    audio = f"{base}.mp3"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-i", wav_joined,
         "-c:a", "libmp3lame", "-b:a", "192k", audio],
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


def fetch_pexels_image(genre: str) -> Image.Image | None:
    """Pexels API를 호출하여 장르 키워드에 해당하는 프리미엄 세로형(9:16) 이미지를 조회해 다운로드합니다."""
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        return None
        
    # 한국어 장르명을 Pexels에 어울리는 영문 키워드로 변환
    keywords_map = {
        "소설": "cinematic dark book mystery",
        "문학": "library classic books aesthetic",
        "시": "poetic beautiful soft light nature",
        "에세이": "cozy warm coffee reading book",
        "수필": "cozy warm coffee reading book",
        "인문": "old history study library books",
        "과학": "technology abstract digital space science",
        "역사": "ancient history museum scroll vintage",
        "경제": "finance dynamic city office abstract",
        "경영": "modern business chart design dark",
        "자기계발": "inspiring sunset focus achievement light",
        "예술": "art artistic brush canvas colorful",
        "default": "open book dramatic atmospheric light"
    }
    
    query = keywords_map.get("default")
    for k, v in keywords_map.items():
        if k in (genre or ""):
            query = v
            break
            
    print(f"     [Pexels Background] 검색 키워드: '{query}'")
    try:
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": api_key}
        params = {
            "query": query,
            "orientation": "portrait",
            "per_page": 3
        }
        r = requests.get(url, headers=headers, params=params, timeout=12)
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            return None
        
        # 첫 번째 검색결과의 portrait 이미지 URL에서 다운로드
        img_url = photos[0]["src"]["portrait"]
        raw = requests.get(img_url, timeout=12).content
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        print(f"     (Pexels 이미지 조회 실패): {e}")
        return None


def cover_background(cover_url: str, genre: str, path: str, size=(1080, 1920)) -> str:
    """도서 표지 카드를 상단 중앙에 얹고, 흐린 배경을 구성합니다.
    
    표지가 존재하면 표지 자체를 블러하여 깔고, 
    표지가 없는 경우 Pexels API를 호출해 장르에 어울리는 백그라운드 이미지를 사용하며,
    최종 실패 시 기존 파이프라인 그라데이션으로 안전하게 Fallback 처리합니다.
    """
    bg_img = None
    cover = None
    
    # 1) 표지가 있으면 다운로드 받아 배경 원본으로 확보
    if cover_url:
        try:
            raw = requests.get(cover_url, timeout=20).content
            cover = Image.open(io.BytesIO(raw)).convert("RGB")
            bg_img = cover
        except Exception as e:
            print(f"     (표지 다운로드 실패, 백업 수집 진행): {e}")
            
    # 2) 표지가 없거나 다운로드에 실패한 경우 Pexels API 백업 구동
    if not bg_img:
        bg_img = fetch_pexels_image(genre)
        
    # 3) Pexels 조차 확보되지 않은 경우 그라데이션으로 최종 Fallback
    if not bg_img:
        print("     [Background Fallback] 그라데이션 자동 생성 처리")
        return P.make_background(path, size)

    w, h = size
    bg = bg_img.resize((w, int(w * bg_img.height / bg_img.width)))
    if bg.height < h:
        bg = bg_img.resize((int(h * bg_img.width / bg_img.height), h))
    bg = bg.crop(((bg.width - w) // 2, (bg.height - h) // 2,
                  (bg.width - w) // 2 + w, (bg.height - h) // 2 + h))
    bg = bg.filter(ImageFilter.GaussianBlur(28))
    bg = Image.blend(bg, Image.new("RGB", size, (10, 10, 20)), 0.45)
    
    # 표지가 실재하는 상태였다면, 중앙 상단에 책 표지 원본 카드 오버레이 얹기
    if cover:
        card_w = int(w * 0.5)
        card = cover.resize((card_w, int(card_w * cover.height / cover.width)))
        bg.paste(card, ((w - card.width) // 2, int(h * 0.16)))
        
    bg.save(path)
    return path


def render(audio, image, srt, qr, out_path, narration_dur: float) -> str:
    """자막은 나레이션 구간에만, QR(라벨 카드)은 아웃트로 구간에만 중앙에 크게.
    두 요소의 표시 구간이 분리되어 겹치지 않는다."""
    # FFmpeg subtitles 필터는 Windows 드라이브 경로(C:\...)의 ':'를 옵션 구분자로
    # 오인한다. cwd를 SRT 디렉토리로 맞추고 basename만 넘겨 회피한다.
    srt_dir = os.path.dirname(os.path.abspath(srt))
    srt_name = os.path.basename(srt)
    font = "Batang" if os.name == "nt" else "NanumMyeongjo"
    style = (f"subtitles={srt_name}:force_style='FontName={font},Bold=0,FontSize=19,"
             "PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=3,Shadow=1,"
             "Alignment=2,MarginV=40'")
    base_vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{style}"
    # 나머지 입출력은 절대경로로 전달
    image = os.path.abspath(image)
    audio = os.path.abspath(audio)
    qr = os.path.abspath(qr)
    out_path = os.path.abspath(out_path)
    cmd = ["ffmpeg", "-nostdin", "-y", "-loop", "1", "-i", image, "-i", audio, "-i", qr,
           "-filter_complex",
           f"[0:v]{base_vf}[bg];[2:v]scale=720:-1[q];"
           f"[bg][q]overlay=(W-w)/2:(H-h)/2:enable='gte(t,{narration_dur:.2f})'[v]",
           "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
           "-pix_fmt", "yuv420p", "-shortest", out_path]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=srt_dir)
    if result.returncode != 0:
        print("FFmpeg STDERR:", result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
        raise RuntimeError(f"FFmpeg render failed (exit {result.returncode})")
    return out_path


def run(isbn: str, region: str = "11", progress=None, custom_description: str | None = None, custom_keywords: list[str] | None = None) -> str:
    def step(label: str):
        print(label)
        if progress:
            progress(label.split("]")[-1].strip() if "]" in label else label)

    step(f"[1/6] 서지/이용분석 isbn={isbn}")
    book = build_book(isbn)
    
    # 사서가 기입한 커스텀 한 줄 설명 및 키워드를 수동 오버라이드 병합
    if custom_description:
        book["description"] = custom_description
    if custom_keywords:
        book["keywords"] = custom_keywords
        
    print("     ->", book.get("title"), "/", book.get("author"),
          "/ 키워드", book.get("keywords", [])[:5])

    step("[2/6] Gemini 대본(소개+키워드 반영)")
    script = rich_script(book)
    sentences = split_sentences(script)
    print("     ->", " / ".join(sentences)[:160])

    base = os.path.join(OUT, isbn)
    step("[3/6] 문장별 Edge TTS + 실측 길이 측정")
    audio, durations, narration, total = tts_per_sentence(sentences, base, book.get("title", ""))
    print(f"     -> 나레이션 {round(narration,1)}s + 아웃트로 {round(total - narration, 1)}s = {round(total,1)}s")

    step("[4/6] 표지 배경 + locate(QR 라벨)")
    image = cover_background(book.get("cover_url", ""), book.get("genre", "book"), base + ".jpg")
    locate = {"total": 0, "libraries": []}
    try:
        if os.environ.get("LIBRARY_API_KEY"):
            locate = enrich.find_holding_libraries(isbn, region=region, limit=5)
            print(f"     -> 소장 도서관 {locate['total']}곳 (지역 {region})")
    except Exception as e:
        print("     (locate 실패):", e)
    hint = f"우리 지역 {locate['total']}곳 소장" if locate["total"] else "QR 스캔 → 소장 도서관 안내"
    qr = qr_with_caption(
        f"http://localhost:8000/locate?isbn={isbn}",
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
