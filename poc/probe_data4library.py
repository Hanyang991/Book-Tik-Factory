"""Probe 정보나루(data4library) Open API endpoints to verify real response shapes."""
import os
import json
import requests

KEY = os.environ["LIBRARY_API_KEY"]
BASE = "https://data4library.kr/api"


def call(name, params):
    params = {"authKey": KEY, "format": "json", **params}
    print("=" * 70)
    print(f"### {name}  params={ {k: v for k, v in params.items() if k != 'authKey'} }")
    try:
        r = requests.get(f"{BASE}/{name}", params=params, timeout=30)
        print("HTTP", r.status_code, "ct=", r.headers.get("content-type"))
        try:
            data = r.json()
        except Exception:
            print("NON-JSON body (first 400):", r.text[:400])
            return None
        # print top-level structure
        resp = data.get("response", data)
        if isinstance(resp, dict):
            print("response keys:", list(resp.keys()))
            for k, v in resp.items():
                if isinstance(v, list) and v:
                    print(f"  [{k}] list len={len(v)}; sample item:")
                    print("   ", json.dumps(v[0], ensure_ascii=False)[:500])
                elif isinstance(v, dict):
                    print(f"  [{k}] dict keys:", list(v.keys()))
                else:
                    print(f"  [{k}] = {str(v)[:120]}")
        else:
            print("raw:", json.dumps(data, ensure_ascii=False)[:500])
        return data
    except Exception as e:
        print("ERROR:", repr(e))
        return None


if __name__ == "__main__":
    # 1) 인기 대출 도서 (지역=서울 11, 20대=20)
    call("loanItemSrch", {"startDt": "2026-05-01", "endDt": "2026-05-31", "region": "11", "age": "20", "pageSize": "5"})
    # 2) 대출 급상승 도서 (hotTrend)
    call("hotTrend", {"searchDt": "2026-05-25"})
    # 3) 도서 소장 도서관 조회 (libSrchByBook) — ISBN 예시
    call("libSrchByBook", {"isbn": "9788937473135", "region": "11", "pageSize": "5"})
    # 4) 도서 소장/대출 가능 여부 (bookExist) — 특정 도서관
    call("bookExist", {"libCode": "111003", "isbn13": "9788937473135"})
    # 5) 도서관별 장서/대출 (usageAnalysisList) — 회전율 후보
    call("usageAnalysisList", {"isbn13": "9788937473135"})
