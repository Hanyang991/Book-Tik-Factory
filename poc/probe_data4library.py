"""
정보나루(data4library) 엔드포인트 점검 — 키 활성화 후 응답 형태 확인용.
LIBRARY_API_KEY 환경변수 필요. 라이브 검증 완료(2026-06).

사용: python probe_data4library.py
"""
import datetime
import json
import os

import enrich

ISBN = "9788937473135"  # 82년생 김지영
REGION = "11"           # 서울


def main():
    if not os.environ.get("LIBRARY_API_KEY"):
        raise SystemExit("LIBRARY_API_KEY가 설정되지 않았습니다.")

    print("== usageAnalysisList (서지+소개+키워드+표지+대출) ==")
    print(json.dumps(enrich.get_book_usage(ISBN), ensure_ascii=False, indent=2)[:600])

    print("\n== estimate_turnover (근사 회전율) ==")
    print(enrich.estimate_turnover(ISBN, region=REGION))

    print("\n== libSrchByBook (소장 도서관 locate) ==")
    print(enrich.find_holding_libraries(ISBN, region=REGION, limit=3))

    print("\n== hotTrend (대출 급상승 화제 도서) ==")
    last_sunday = datetime.date.today() - datetime.timedelta(
        days=datetime.date.today().weekday() + 1)
    for b in enrich.get_trending_books(last_sunday.isoformat(), limit=3):
        print(f"  +{b['rank_jump']:>4}  {b['title']}  ({b['isbn']})")

    print("\n== loanItemSrch (지역·연령 인기대출) ==")
    for b in enrich.get_popular_books(REGION, "20", "2026-05-01", "2026-05-31", limit=3):
        print(f"  loan={b['loan_count']:>4}  {b['title']}  ({b['isbn']})")


if __name__ == "__main__":
    main()
