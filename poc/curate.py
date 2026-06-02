"""
Book-Tik Factory — 회전율 기반 주간 자동 선정 (타입 A/B/C).

정보나루 데이터로 매주 제작 대상을 자동으로 뽑는다. 영상 생성 전 단계의 '선정 로직'이며,
--videos 옵션을 주면 선정된 책들의 트레일러까지 일괄 생성한다(generate.run).

선정 유형(모두 정보나루 실데이터 + 명시적 근거):
  A. 숨은 명저   : 전국 누적대출이 검증된 양서를 우리 지역에 재조명(화제·회전율개선 제외분 중 최상위)
  B. 회전율 개선 : 근사 회전율(전국대출/지역 소장 도서관 수)이 가장 낮은 책 → 노출 강화 대상
  C. 화제 도서   : hotTrend 대출 급상승 — 회전율 무관 포함

근사 회전율 메모: 정보나루는 '도서관별 장서 수'를 직접 주지 않으므로
loanCnt / (지역 소장 도서관 수)를 프록시로 쓴다(정식 단계 사서 CSV로 보강).
"""
import datetime

import enrich


def _last_month_range() -> tuple[str, str]:
    end = datetime.date.today() - datetime.timedelta(days=1)
    start = end - datetime.timedelta(days=30)
    return start.isoformat(), end.isoformat()


def build_candidate_pool(region: str, age: str, start: str, end: str, size: int) -> list[dict]:
    """인기대출 풀을 가져와 각 책의 근사 회전율을 산출한다."""
    pool = enrich.get_popular_books(region, age, start, end, limit=size)
    out = []
    for b in pool:
        if not b.get("isbn"):
            continue
        try:
            t = enrich.estimate_turnover(b["isbn"], region=region)
        except Exception:
            continue
        b.update(national_loan=t["loan_count"],
                 holding_libraries=t["holding_libraries"],
                 turnover=t["turnover"])
        out.append(b)
    return out


def build_weekly_targets(region: str = "11", age: str = "20", search_date: str | None = None,
                         start: str | None = None, end: str | None = None,
                         pool_size: int = 12, per_type: int = 2) -> dict:
    """A/B/C 타입별 제작 대상을 선정한다."""
    if not (start and end):
        start, end = _last_month_range()
    if not search_date:
        search_date = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

    pool = build_candidate_pool(region, age, start, end, pool_size)
    seen: set[str] = set()

    # C. 화제 도서 — hotTrend 급상승
    type_c = []
    for t in enrich.get_trending_books(search_date, limit=per_type * 4):
        if t["isbn"] and t["isbn"] not in seen:
            jump = t.get("rank_jump")
            type_c.append({**t, "reason": f"대출 급상승(전주 대비 {jump}위↑, 현재 {t.get('rank')}위)"})
            seen.add(t["isbn"])
        if len(type_c) >= per_type:
            break

    pool = [b for b in pool if b["isbn"] not in seen]

    # B. 회전율 개선 — 근사 회전율 최저
    type_b = []
    for b in sorted(pool, key=lambda x: x["turnover"])[:per_type]:
        type_b.append({**b,
            "reason": f"근사 회전율 {b['turnover']} (지역 {b['holding_libraries']}곳 소장 대비 대출 저조) → 노출 강화"})
        seen.add(b["isbn"])

    # A. 숨은 명저 — 남은 후보 중 전국 누적대출 최상위(검증된 양서)
    rest = [b for b in pool if b["isbn"] not in seen]
    type_a = []
    for b in sorted(rest, key=lambda x: x["national_loan"], reverse=True)[:per_type]:
        type_a.append({**b,
            "reason": f"전국 누적대출 {b['national_loan']:,}건의 검증된 양서 → 우리 지역 재조명"})

    return {
        "region": region, "age": age, "period": [start, end], "search_date": search_date,
        "A_숨은명저": type_a, "B_회전율개선": type_b, "C_화제도서": type_c,
    }


_LABELS = {"A_숨은명저": "A. 숨은 명저", "B_회전율개선": "B. 회전율 개선", "C_화제도서": "C. 화제 도서"}


def format_report(targets: dict) -> str:
    lines = ["", "=" * 64,
             f"주간 제작 대상 선정  (지역 {targets['region']} / 연령 {targets['age']}대 "
             f"/ 기간 {targets['period'][0]}~{targets['period'][1]})", "=" * 64]
    for key, label in _LABELS.items():
        lines.append(f"\n[{label}]")
        items = targets.get(key, [])
        if not items:
            lines.append("  (선정 없음)")
        for i, b in enumerate(items, 1):
            lines.append(f"  {i}. {b.get('title','?')}  (ISBN {b.get('isbn','')})")
            lines.append(f"     근거: {b.get('reason','')}")
    lines.append("")
    return "\n".join(lines)


def generate_videos(targets: dict, region: str | None = None) -> list[str]:
    """선정된 모든 책의 트레일러를 일괄 생성한다."""
    import generate
    region = region or targets.get("region", "11")
    made = []
    for key in _LABELS:
        for b in targets.get(key, []):
            isbn = b.get("isbn")
            if not isbn:
                continue
            print(f"\n>>> [{_LABELS[key]}] {b.get('title')} ({isbn}) 생성")
            try:
                made.append(generate.run(isbn, region=region))
            except Exception as e:
                print(f"    (생성 실패: {e})")
    return made


if __name__ == "__main__":
    import sys
    targets = build_weekly_targets()
    print(format_report(targets))
    if "--videos" in sys.argv:
        made = generate_videos(targets)
        print(f"\n생성 완료: {len(made)}편")
        for m in made:
            print("  -", m)
