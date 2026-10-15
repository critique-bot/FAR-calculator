# 서울 전체 지구단위계획 용적률계획/구역 목록 수집 (PC에서 실행). 결과: 용적률계획전체.json, 구역목록.json
import requests, json, time
from urllib.parse import urlencode
PROXY = "https://urban.seoul.go.kr/proxy/proxy.jsp?"
BASE = "http://98.33.2.225:6080/arcgis/rest/services/UPIS/20200526_WFS/MapServer/"

def q(layer, p):
    p = dict(p); p["f"] = "json"
    r = requests.post(PROXY + BASE + "%s/query" % layer, data=p, timeout=90) if False else requests.get(PROXY + BASE + "%s/query?" % layer + urlencode(p), timeout=90)
    return r.json()

def dump(layer, name, idfield="OBJECTID", step=150):
    j = q(layer, {"where": "1=1", "returnIdsOnly": "true"})
    ids = j.get("objectIds") or []
    print(name, "ID 개수", len(ids), j.get("error", ""))
    rows = []
    for i in range(0, len(ids), step):
        part = ids[i:i + step]
        k = q(layer, {"where": "%s IN (%s)" % (idfield, ",".join(map(str, part))), "outFields": "*", "returnGeometry": "false"})
        if "error" in k: print("오류", k["error"]); continue
        rows += [f["attributes"] for f in k.get("features", [])]
        if (i // step) % 10 == 0: print(name, len(rows), "/", len(ids))
        time.sleep(0.3)
    json.dump(rows, open(name + ".json", "w", encoding="utf-8"), ensure_ascii=False)
    return rows

fr = dump(34, "용적률계획전체")
zn = dump(28, "구역목록")
print("용적률계획", len(fr), "구역", len(zn), "구역 PRESENT_SN 종류", len({r.get("PRESENT_SN") for r in zn}))
