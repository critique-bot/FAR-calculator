# 서울 전역 지번 -> 구역/용적률 조회 (PC에서 실행)  사용: python lookup.py "광진구 군자동 478-5" "마포구 노고산동 57-1"
import requests, json, sys, os
from urllib.parse import urlencode
from shapely.geometry import Polygon
from shapely.ops import unary_union

KEY = os.environ.get("VWORLD_KEY", "YOUR_VWORLD_KEY")
DOMAIN = "www.test.com"
PROXY = "https://urban.seoul.go.kr/proxy/proxy.jsp?"
BASE = "http://98.33.2.225:6080/arcgis/rest/services/UPIS/20200526_WFS/MapServer/"

def q(layer, params):
    r = requests.get(PROXY + BASE + "%s/query?" % layer + urlencode(params), timeout=30)
    try: return r.json()
    except Exception: return {}

def shape(rings):
    o, h = [], []
    for r in rings:
        s = sum(r[i][0]*r[(i+1)%len(r)][1] - r[(i+1)%len(r)][0]*r[i][1] for i in range(len(r)))
        (o if s < 0 else h).append(Polygon(r).buffer(0))
    g = unary_union(o)
    for x in h: g = g.difference(x)
    return g

def pnu_of(addr):
    if not addr.startswith("서울"): addr = "서울특별시 " + addr
    g = requests.get("https://api.vworld.kr/req/address", params={
        "service":"address","request":"getcoord","version":"2.0","crs":"epsg:4326","address":addr,
        "refine":"true","simple":"false","format":"json","type":"parcel","key":KEY,"domain":DOMAIN}, timeout=30).json()
    return g["response"]["refined"]["structure"]["level4LC"], g["response"]["refined"]["text"]

def hits(layer, rings, area, th=0.01):
    j = q(layer, {"geometry": json.dumps({"spatialReference":{"latestWkid":5174,"wkid":102086},"rings":rings}),
                  "geometryType":"esriGeometryPolygon","inSR":102086,"outSR":5174,
                  "spatialRel":"esriSpatialRelIntersects","outFields":"*","returnGeometry":"true","f":"json"})
    out = []
    for f in j.get("features") or []:
        try: ov = shape(rings).intersection(shape(f["geometry"]["rings"])).area / area
        except Exception: continue
        if ov > th: out.append((ov, f["attributes"]))
    return out

def lookup(addr):
    res = {"입력": addr, "경고": []}
    pnu, res["정제주소"] = pnu_of(addr); res["PNU"] = pnu
    if addr.split()[-1].replace("번지", "") != res["정제주소"].split()[-1]:
        res["경고"].append("입력 지번과 조회된 지번이 다름: %s -> %s" % (addr.split()[-1], res["정제주소"].split()[-1]))
    p = q(1, {"where": "PNU='%s'" % pnu, "outFields": "*", "returnGeometry": "true", "outSR": 5174, "f": "json"})
    rings = p["features"][0]["geometry"]["rings"]; area = shape(rings).area; res["필지면적"] = round(area, 1)
    z = hits(28, rings, area)
    res["지구단위계획구역"] = [{"이름": a["DGM_NM"], "PRESENT_SN": a["PRESENT_SN"], "겹침": round(ov, 3)} for ov, a in z]
    if not z: res["경고"].append("지구단위계획구역 아님 -> 용도지역 법정 용적률(조례 제55조) 적용")
    if len(z) > 1: res["경고"].append("구역 2개 이상 겹침 - 확인 필요")
    sp = hits(29, rings, area)
    res["특별계획구역"] = [{"이름": a["DGM_NM"], "PRESENT_SN": a["PRESENT_SN"], "겹침": round(ov, 3)} for ov, a in sp]
    fr = hits(34, rings, area)
    res["용적률계획"] = [{"기호": a.get("NONUSE"), "기준": a.get("STANFARA"), "허용": a.get("PERMITFARA"), "상한": a.get("MAXFARA"),
                         "건폐": a.get("BDTLDR"), "높이": a.get("TOP"), "인센티브코드": a.get("INCENTIVE"), "겹침": round(ov, 3)} for ov, a in fr]
    if z and not fr: res["경고"].append("지단 구역이나 용적률 계획 폴리곤 없음 - 고시 확인 필요")
    if len(fr) > 1: res["경고"].append("용적률 계획 2개 이상 겹침(필지가 획지 경계에 걸침) - 가중평균/개별 확인 필요")
    ur = {}
    for ov, a in hits(63, rings, area):
        k = a["DGM_NM"]
        if k not in ur or a["CREATE_DAT"] > ur[k][1]["CREATE_DAT"]: ur[k] = (ov, a)
    res["용도지역"] = [{"이름": k, "겹침": round(v[0], 3)} for k, v in ur.items()]
    res["정비구역등"] = [a["DGM_NM"] for ov, a in hits(64, rings, area)]
    res["토지거래허가"] = bool(hits(61, rings, area))
    return res

def pct(txt):
    import re
    m = re.search(r"(\d[\d,]*\.?\d*)", txt or "")
    return float(m.group(1).replace(",", "")) if m else None

def group(addrs):
    """여러 필지(합필/공동개발) 한 묶음. 필지별 결과 + 면적가중 합산 + 불일치 경고"""
    ps = [lookup(a) for a in addrs]
    g = {"입력": addrs, "필지": ps, "합계면적": round(sum(p["필지면적"] for p in ps), 1), "경고": []}
    for p in ps:
        for w in p["경고"]: g["경고"].append("[%s] %s" % (p["정제주소"].split()[-1], w))
    def names(key, sub=None):
        return sorted({(x[sub] if sub else x) for p in ps for x in p[key]})
    for key, sub in (("지구단위계획구역", "이름"), ("특별계획구역", "이름")):
        n = names(key, sub); g[key] = n
        if len(n) > 1 or any(not p[key] for p in ps) and n:
            g["경고"].append("%s이(가) 필지마다 다름: %s" % (key, n))
    g["정비구역등"] = sorted({x for p in ps for x in p["정비구역등"] if "정비" in x})
    # 용도지역 면적합
    ur = {}
    for p in ps:
        for u in p["용도지역"]: ur[u["이름"]] = ur.get(u["이름"], 0) + u["겹침"] * p["필지면적"]
    tot = g["합계면적"]
    g["용도지역"] = {k: round(v / tot, 3) for k, v in ur.items()}
    if len(ur) > 1: g["경고"].append("용도지역 2개 이상에 걸침 -> 국토계획법 제84조 가중평균 검토")
    # 용적률계획 면적가중
    acc = {}
    for p in ps:
        for f in p["용적률계획"]:
            k = (f["기호"], f["기준"], f["허용"], f["상한"], f["높이"], f["건폐"], f["인센티브코드"])
            acc[k] = acc.get(k, 0) + f["겹침"] * p["필지면적"]
    g["용적률계획_구성"] = [{"기호": k[0], "기준": k[1], "허용": k[2], "상한": k[3], "높이": k[4], "건폐": k[5], "인센티브": k[6],
                         "면적": round(v, 1), "비율": round(v / tot, 3)} for k, v in acc.items()]
    if len(acc) > 1:
        g["경고"].append("용적률 계획이 둘 이상(기호 %s) - 합필 시 획지계획/지구 통합 가능 여부 고시 확인 필요(자동 평균은 참고용)"
                         % sorted({k[0] for k in acc}))
        for nm, i in (("기준", 1), ("허용", 2)):
            vs = [(pct(k[i]), v) for k, v in acc.items()]
            if all(x[0] is not None for x in vs):
                g["가중평균_" + nm] = round(sum(a * b for a, b in vs) / sum(b for a, b in vs), 1)
    covered = sum(acc.values())
    if covered < tot * 0.99: g["경고"].append("용적률 계획 폴리곤이 덮지 않는 면적 %.1f㎡" % (tot - covered))
    return g

import re
def split_group(text):
    """'마포구 노고산동 57-1, 57-2, 57-3' 또는 '57-1/57-2' -> 전체 주소 리스트. '|'도 허용."""
    parts = [x.strip() for x in re.split(r"[,/|;]", text) if x.strip()]
    if len(parts) < 2: return parts
    prefix = parts[0].rsplit(" ", 1)[0] if " " in parts[0] else ""
    out = [parts[0]]
    for p in parts[1:]:
        out.append(prefix + " " + p if re.fullmatch(r"\d+(-\d+)?(번지)?", p) and prefix else p)
    return out

if __name__ == "__main__":
    addrs = sys.argv[1:] or [input("주소: ")]
    allr = []
    for a in addrs:
        try:
            lst = split_group(a)
            r = group(lst) if len(lst) > 1 else lookup(lst[0])
        except Exception as e: r = {"입력": a, "오류": repr(e)}
        allr.append(r); print(json.dumps(r, ensure_ascii=False, indent=1))
    open("조회결과.json", "w", encoding="utf-8").write(json.dumps(allr, ensure_ascii=False, indent=1))
