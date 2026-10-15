"""서울 법정동 코드표 만들기 (PC에서 한 번만 실행).  사용: python build_dong_table.py
행정안전부 법정동코드 API(공공데이터포털)를 호출해 legal_dong.json 을 만듭니다.
인증키는 파일에 적지 않고 실행할 때 입력하거나 환경변수 DATA_GO_KEY 로 줍니다."""
import os, sys, json, requests

URL = "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
key = os.environ.get("DATA_GO_KEY") or input("공공데이터포털 인증키: ").strip()

def rows_of(obj):
    """응답 JSON 어디에 있든 region_cd 를 가진 항목들을 찾는다"""
    out = []
    if isinstance(obj, dict):
        if "region_cd" in obj: out.append(obj)
        for v in obj.values(): out += rows_of(v)
    elif isinstance(obj, list):
        for v in obj: out += rows_of(v)
    return out

def call(page):
    r = requests.get(URL, params={"ServiceKey": key, "type": "json", "pageNo": page, "numOfRows": 1000, "flag": "Y", "locatadd_nm": "서울특별시"}, timeout=40)
    try: return r.json(), r.text
    except Exception:
        print("JSON 이 아닌 응답:", r.status_code, r.text[:300]); sys.exit(1)

allrows, page = [], 1
while True:
    j, raw = call(page)
    rs = rows_of(j)
    if page == 1 and not rs:
        print("항목을 찾지 못했습니다. 응답 앞부분:\n", raw[:600]); sys.exit(1)
    allrows += rs
    print("페이지", page, "->", len(rs), "건")
    if len(rs) < 1000: break
    page += 1

table, dropped, diff = {}, 0, []
for r in allrows:
    cd = str(r.get("region_cd", ""))
    nm = str(r.get("locatadd_nm", "")).strip()
    if len(cd) != 10 or not cd.startswith("11") or not nm.startswith("서울"): continue
    jj = str(r.get("locatjijuk_cd", "")).strip()
    if jj and jj != cd: diff.append((nm, cd, jj))
    if cd[5:8] == "000": continue          # 시도/시군구 행
    if cd[8:] != "00": continue            # 리 단위 제외 (서울은 사실상 없음)
    parts = nm.split()                      # 서울특별시 마포구 노고산동
    if len(parts) < 3: continue
    table["%s %s" % (parts[1], " ".join(parts[2:]))] = cd
json.dump(table, open("legal_dong.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
print("서울 법정동", len(table), "개 저장 -> legal_dong.json")
if diff: print("지역코드와 지적코드가 다른 동 %d개 (예: %s)" % (len(diff), diff[:3]))
print("확인:", table.get("마포구 노고산동"), "(1144011000 이어야 함)")
