"""지번 -> 구역/용적률 조회. 서버용 (캐시, 재시도, 필지 병렬 조회).
외부 호출은 모두 fetch_json()/portal_query() 두 함수로 모아 테스트에서 교체 가능."""
import json, re, hashlib, time, os, threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from shapely.geometry import Polygon
from shapely.ops import unary_union
import settings as cfg
import dongcode

class LookupError_(Exception):
    """사용자에게 그대로 보여줄 수 있는 조회 오류"""
    def __init__(self, msg, code="lookup_failed"): super().__init__(msg); self.code = code

_sess = requests.Session()
_sess.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=(502, 503, 504))))
_sess.mount("http://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=(502, 503, 504))))

# ---------- 디스크 캐시 ----------
_lock = threading.Lock()
def _cpath(k): return os.path.join(cfg.CACHE_DIR, hashlib.sha1(k.encode()).hexdigest() + ".json")
def cache_get(k):
    p = _cpath(k)
    try:
        if time.time() - os.path.getmtime(p) < cfg.CACHE_TTL_H * 3600:
            return json.load(open(p, encoding="utf-8"))
    except Exception: pass
    return None
def cache_put(k, v):
    try:
        os.makedirs(cfg.CACHE_DIR, exist_ok=True)
        with _lock: json.dump(v, open(_cpath(k), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception: pass

# ---------- 외부 호출 (테스트에서 교체) ----------
def fetch_json(url, params=None, timeout=25):
    try:
        r = _sess.get(url, params=params, timeout=timeout)
    except requests.RequestException as e:
        raise LookupError_("외부 서비스에 연결하지 못했습니다: %s" % type(e).__name__, "upstream_unreachable")
    if r.status_code != 200:
        raise LookupError_("외부 서비스 응답 오류 %s (%s)" % (r.status_code, url.split("/")[2]), "upstream_http_%s" % r.status_code)
    try: return r.json()
    except Exception: raise LookupError_("외부 서비스가 JSON이 아닌 응답을 보냈습니다 (%s)" % url.split("/")[2], "upstream_bad_body")

def portal_query(layer, params):
    url = cfg.PORTAL_PROXY + cfg.PORTAL_BASE + "%s/query?" % layer + urlencode(params)
    j = fetch_json(url, timeout=40)
    if "error" in j: raise LookupError_("도시공간포털 오류: %s" % j["error"], "portal_error")
    return j

# ---------- 지오메트리 ----------
def shape(rings):
    o, h = [], []
    for r in rings:
        s = sum(r[i][0]*r[(i+1) % len(r)][1] - r[(i+1) % len(r)][0]*r[i][1] for i in range(len(r)))
        (o if s < 0 else h).append(Polygon(r).buffer(0))
    g = unary_union(o)
    for x in h: g = g.difference(x)
    return g

def hits(layer, rings, area, th=0.01):
    j = portal_query(layer, {"geometry": json.dumps({"spatialReference": {"latestWkid": 5174, "wkid": 102086}, "rings": rings}),
                             "geometryType": "esriGeometryPolygon", "inSR": 102086, "outSR": 5174,
                             "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true", "f": "json"})
    out, me = [], shape(rings)
    for f in j.get("features") or []:
        try: ov = me.intersection(shape(f["geometry"]["rings"])).area / area
        except Exception: continue
        if ov > th: out.append((ov, f["attributes"]))
    return out

def pct(txt):
    m = re.search(r"(\d[\d,]*\.?\d*)", txt or "")
    return float(m.group(1).replace(",", "")) if m else None

# ---------- 필지 1개 ----------
def lookup(addr):
    addr = " ".join(addr.split())
    ck = "parcel:" + addr
    c = cache_get(ck)
    if c: c["캐시"] = True; return c
    res = {"입력": addr, "경고": []}
    try: a = dongcode.parse(addr)
    except dongcode.AddressError as e: raise LookupError_(str(e), e.code)
    pnu = a["pnu"]; res["정제주소"] = a["text"]; res["PNU"] = pnu
    p = portal_query(1, {"where": "PNU='%s'" % pnu, "outFields": "*", "returnGeometry": "true", "outSR": 5174, "f": "json"})
    if not p.get("features"):
        sug = []
        try:
            q2 = portal_query(1, {"where": "PNU LIKE '%s%%'" % a["prefix"], "outFields": "JIBUN", "returnGeometry": "false", "f": "json"})
            sug = sorted({re.sub(r"[^\d-]", "", f["attributes"]["JIBUN"].replace("산", "")) for f in q2.get("features", [])})[:8]
        except LookupError_: pass
        raise LookupError_("%s 에 해당하는 필지가 없습니다.%s" % (a["text"], (" 같은 번지의 다른 지번: " + ", ".join("%d-%s" % (a["bon"], x.split("-")[-1]) if "-" in x else x for x in sug)) if sug else " 지번을 다시 확인하세요."), "parcel_not_found")
    rings = p["features"][0]["geometry"]["rings"]; area = shape(rings).area; res["필지면적"] = round(area, 1)
    z = hits(28, rings, area)
    res["지구단위계획구역"] = [{"이름": a["DGM_NM"], "PRESENT_SN": a["PRESENT_SN"], "겹침": round(ov, 3)} for ov, a in z]
    if not z: res["경고"].append("지구단위계획구역 아님 -> 용도지역 법정 용적률(조례) 적용")
    if len(z) > 1: res["경고"].append("구역 2개 이상 겹침 - 확인 필요")
    res["특별계획구역"] = [{"이름": a["DGM_NM"], "PRESENT_SN": a["PRESENT_SN"], "겹침": round(ov, 3)} for ov, a in hits(29, rings, area)]
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
    res["조회시각"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    cache_put(ck, res)
    return res

# ---------- 여러 필지 묶음 ----------
def split_group(text):
    """'마포구 노고산동 57-1, 57-2, 57-3' 또는 줄바꿈/슬래시/| 구분. 뒤쪽은 번지만 써도 됨."""
    parts = [x.strip() for x in re.split(r"[,/|;\n]", text) if x.strip()]
    if len(parts) < 2: return parts
    prefix = parts[0].rsplit(" ", 1)[0] if " " in parts[0] else ""
    out = [parts[0]]
    for p in parts[1:]:
        out.append(prefix + " " + p if re.fullmatch(r"\d+(-\d+)?(번지)?", p) and prefix else p)
    return out

def group(addrs):
    if len(addrs) > cfg.MAX_PARCELS: raise LookupError_("한 번에 최대 %d필지까지 조회할 수 있습니다." % cfg.MAX_PARCELS, "too_many")
    with ThreadPoolExecutor(max_workers=min(4, len(addrs))) as ex: ps = list(ex.map(lookup, addrs))
    g = {"입력": addrs, "필지": ps, "합계면적": round(sum(p["필지면적"] for p in ps), 1), "경고": [],
         "캐시": all(p.get("캐시") for p in ps), "조회시각": min(p.get("조회시각", "") for p in ps)}
    for p in ps:
        for w in p["경고"]: g["경고"].append("[%s] %s" % (p["정제주소"].split()[-1], w))
    for key in ("지구단위계획구역", "특별계획구역"):
        n = sorted({x["이름"] for p in ps for x in p[key]}); g[key] = n
        if len(n) > 1 or (n and any(not p[key] for p in ps)):
            g["경고"].append("%s이(가) 필지마다 다름: %s" % (key, n))
    g["구역SN"] = {x["이름"]: x["PRESENT_SN"] for p in ps for key in ("지구단위계획구역", "특별계획구역") for x in p[key]}
    g["정비구역등"] = sorted({x for p in ps for x in p["정비구역등"] if "정비" in x})
    ur = {}
    for p in ps:
        for u in p["용도지역"]: ur[u["이름"]] = ur.get(u["이름"], 0) + u["겹침"] * p["필지면적"]
    tot = g["합계면적"]
    g["용도지역"] = {k: round(v / tot, 3) for k, v in ur.items()}
    if len(ur) > 1: g["경고"].append("용도지역 2개 이상에 걸침 -> 국토계획법 제84조 가중평균 검토")
    acc = {}
    for p in ps:
        for f in p["용적률계획"]:
            k = (f["기호"], f["기준"], f["허용"], f["상한"], f["높이"], f["건폐"], f["인센티브코드"])
            acc[k] = acc.get(k, 0) + f["겹침"] * p["필지면적"]
    g["용적률계획_구성"] = [{"기호": k[0], "기준": k[1], "허용": k[2], "상한": k[3], "높이": k[4], "건폐": k[5], "인센티브": k[6],
                         "면적": round(v, 1), "비율": round(v / tot, 3)} for k, v in acc.items()]
    if len(acc) > 1:
        g["경고"].append("용적률 계획이 둘 이상(기호 %s) - 합필 시 획지계획/지구 통합 가능 여부 고시 확인 필요(자동 평균은 참고용)" % sorted({str(k[0]) for k in acc}))
        for nm, i in (("기준", 1), ("허용", 2)):
            vs = [(pct(k[i]), v) for k, v in acc.items()]
            if all(x[0] is not None for x in vs): g["가중평균_" + nm] = round(sum(a * b for a, b in vs) / sum(b for a, b in vs), 1)
    if sum(acc.values()) < tot * 0.99: g["경고"].append("용적률 계획 폴리곤이 덮지 않는 면적 %.1f㎡" % (tot - sum(acc.values())))
    return g

def lookup_text(text):
    """입력 한 덩어리 -> 단일 필지 결과 또는 묶음 결과"""
    lst = split_group(text)
    if not lst: raise LookupError_("지번을 입력하세요.", "empty")
    return group(lst) if len(lst) > 1 else lookup(lst[0])
