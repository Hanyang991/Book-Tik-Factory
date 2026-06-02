"""
정보나루(data4library) 연동 모듈 — 라이브 검증 완료(2026-06).

검증된 엔드포인트(모두 GET, authKey+format=json):
  - usageAnalysisList : 도서별 이용분석. 서지 + 책소개(description) + 가중 키워드 +
                        표지 URL + 분류(class_nm) + 총대출(loanCnt) + 월별 추이.
  - hotTrend          : 대출 급상승(화제) 도서 — Type C 큐레이션 신호.
  - libSrchByBook     : 특정 ISBN을 소장한 도서관 목록 — locate(가까운 도서관 안내).
  - bookExist         : 특정 도서관의 소장/대출가능 여부(Y/N).
  - loanItemSrch      : 지역·연령별 인기대출 — 후보 도서 풀.

회전율(turnover) 메모: 정보나루는 임의 도서의 '도서관별 장서 수'를 직접 주지 않는다.
대신 (a) loanCnt(대출량) + (b) libSrchByBook numFound(소장 도서관 수)를 소장 규모 프록시로
사용해 '대출/소장' 근사 회전율을 산출한다(정식 단계에서 사서 CSV로 보강).
"""
import os
import requests

BASE = "https://data4library.kr/api"
_KEY = os.environ.get("LIBRARY_API_KEY", "")


def _get(endpoint: str, **params) -> dict:
    params.update({"authKey": _KEY, "format": "json"})
    r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=40)
    r.raise_for_status()
    return r.json().get("response", {})


def get_book_usage(isbn: str) -> dict:
    """usageAnalysisList → 대본 생성에 풍부한 입력(소개·키워드·표지·분류·대출)을 반환."""
    j = _get("usageAnalysisList", isbn13=isbn)
    book = j.get("book") or {}
    keywords = [k["keyword"]["word"] for k in j.get("keywords", [])][:8]
    return {
        "isbn": isbn,
        "title": (book.get("bookname") or "").split(":")[0].strip(),
        "author": (book.get("authors") or "").replace("지은이:", "").strip(),
        "publisher": book.get("publisher", ""),
        "genre": book.get("class_nm", ""),
        "description": book.get("description", ""),
        "cover_url": book.get("bookImageURL", ""),
        "loan_count": int(book.get("loanCnt", 0) or 0),
        "keywords": keywords,
    }


def find_holding_libraries(isbn: str, region: str = "11", limit: int = 5) -> dict:
    """libSrchByBook → 해당 ISBN을 소장한 도서관(가까운 곳 안내용) + 소장 도서관 수.

    region(법정동 지역코드, 예: 11=서울)은 필수다. 미지정 시 '지역코드를 확인' 오류.
    """
    j = _get("libSrchByBook", isbn=isbn, region=region, pageSize=str(limit))
    libs = [
        {"name": d["lib"].get("libName", ""), "address": d["lib"].get("address", ""),
         "code": d["lib"].get("libCode", "")}
        for d in j.get("libs", [])
    ]
    return {"total": int(j.get("numFound", 0) or 0), "libraries": libs}


def get_trending_books(search_date: str, limit: int = 10) -> list[dict]:
    """hotTrend → 대출 급상승(화제) 도서. Type C 큐레이션 입력."""
    j = _get("hotTrend", searchDt=search_date)
    results = j.get("results", [])
    docs = results[0]["result"]["docs"] if results else []
    out = []
    for d in docs[:limit]:
        b = d["doc"]
        out.append({
            "isbn": b.get("isbn13", ""),
            "title": b.get("bookname", ""),
            "author": b.get("authors", ""),
            "rank": b.get("baseWeekRank"),
            "prev_rank": b.get("pastWeekRank"),
            "rank_jump": b.get("difference"),
            "cover_url": b.get("bookImageURL", ""),
        })
    return out


def get_popular_books(region: str, age: str, start: str, end: str,
                      limit: int = 10, page: int = 1) -> list[dict]:
    """loanItemSrch → 지역·연령별 인기대출 도서(후보 풀).

    page를 키우면 순위가 낮은(대출 적은) 도서까지 후보로 끌어올 수 있다.
    """
    j = _get("loanItemSrch", region=region, age=age, startDt=start, endDt=end,
             pageNo=str(page), pageSize=str(limit))
    return [
        {"isbn": d["doc"].get("isbn13", ""), "title": d["doc"].get("bookname", ""),
         "loan_count": int(d["doc"].get("loan_count", 0) or 0)}
        for d in j.get("docs", [])
    ]


def estimate_turnover(isbn: str, region: str = "11") -> dict:
    """근사 회전율 = 총대출 / 소장 도서관 수(지역 프록시). 값이 낮을수록 '숨은 명저' 후보."""
    usage = get_book_usage(isbn)
    holding = find_holding_libraries(isbn, region=region)
    stock = max(holding["total"], 1)
    return {
        "isbn": isbn,
        "region": region,
        "loan_count": usage["loan_count"],
        "holding_libraries": holding["total"],
        "turnover": round(usage["loan_count"] / stock, 2),
    }
