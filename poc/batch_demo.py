"""
발표용 데모 — 여러 권을 일괄 생성하고 하나의 릴(reel)로 이어붙인다.

각 권은 generate.run(isbn)으로 정보나루(소개·키워드·표지) + locate를 반영해 만든다.
"""
import os
import subprocess

import generate

OUT = os.path.join(os.path.dirname(__file__), "outputs")

# (제목, ISBN) — 정보나루 usageAnalysisList 데이터 보유 확인됨
DEMO = [
    ("82년생 김지영", "9788937473135"),
    ("불편한 편의점", "9791161571188"),
    ("아몬드", "9788936434267"),
    ("채식주의자", "9788936433598"),
]


def concat(mp4s: list[str], out_path: str) -> str:
    listfile = os.path.join(OUT, "_concat.txt")
    with open(listfile, "w") as f:
        for m in mp4s:
            f.write(f"file '{m}'\n")
    # 코덱/해상도 동일하므로 무재인코딩 concat
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                    "-c", "copy", out_path], check=True, capture_output=True)
    return out_path


def main():
    made = []
    for title, isbn in DEMO:
        print(f"\n===== {title} ({isbn}) =====")
        try:
            made.append(generate.run(isbn))
        except Exception as e:
            print("  FAILED:", e)
    if len(made) > 1:
        reel = concat(made, os.path.join(OUT, "demo_reel.mp4"))
        print(f"\nREEL -> {reel} ({os.path.getsize(reel)} bytes)")
    print(f"\n완료: {len(made)}/{len(DEMO)}편 생성")


if __name__ == "__main__":
    main()
