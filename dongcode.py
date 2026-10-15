"""주소 문자열 -> PNU (법정동 코드표 + 지번). 외부 호출 없음."""
import json, os, re, difflib

import threading, time
import requests
import settings as cfg

HERE = os.path.dirname(os.path.abspath(__file__))
API_URL = "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
BUNDLED = os.path.join(HERE, "data", "legal_dong.json")     # API 를 못 쓸 때의 예비본
_lock = threading.Lock()
_state = {"table": {}, "by_dong": {}, "source": None, "updated": None, "error": None, "tried": 0.0}

def _install(table, source, updated):
    by = {}
    for k, v in table.items():
        gu, dong = k.split(" ", 1)
        by.setdefault(dong.replace(" ", ""), []).append((gu, v))
    _state.update(table=table, by_dong=by, source=source, updated=updated)   # 한 번에 교체

def _cache_path(): return os.path.join(cfg.CACHE_DIR, "legal_dong_api.json")

def _rows_of(obj):
    out = []
    if isinstance(obj, dict):
        if "region_cd" in obj: out.append(obj)
        for v in obj.values(): out += _rows_of(v)
    elif isinstance(obj, list):
        for v in obj: out += _rows_of(v)
    return out

def _http_get(params):
    r = requests.get(API_URL, params=params, timeout=40); r.raise_for_status(); return r.json()

def fetch_from_api(key):
    """행정안전부 법정동코드 API -> {"마포구 노고산동": "1144011000"} (서울, 동 단위). 이상하면 예외"""
    rows, page = [], 1
    while True:
        j = _http_get({"ServiceKey": key, "type": "json", "pageNo": page, "numOfRows": 1000, "flag": "Y", "locatadd_nm": "서울특별시"})
        rs = _rows_of(j)
        if page == 1 and not rs: raise RuntimeError("API 응답에 법정동 항목이 없습니다")
        rows += rs
        if len(rs) < 1000 or page >= 20: break
        page += 1
    table = {}
    for r in rows:
        cd, nm = str(r.get("region_cd", "")), str(r.get("locatadd_nm", "")).strip()
        if len(cd) != 10 or not cd.startswith("11") or not nm.startswith("서울"): continue
        if cd[5:8] == "000" or cd[8:] != "00": continue
        p = nm.split()
        if len(p) >= 3: table["%s %s" % (p[1], " ".join(p[2:]))] = cd
    if len(table) < 400 or "마포구 노고산동" not in table:        # 이상한 응답으로 기존 표를 덮어쓰지 않도록
        raise RuntimeError("받은 코드표가 비정상입니다 (%d개)" % len(table))
    return table

def refresh(force=False):
    """API 에서 코드표 갱신. 실패하면 기존 표 유지. 반환: 현재 상태"""
    key = cfg.DATA_GO_KEY
    with _lock:
        now = time.time()
        if not key: return info()
        if not force and _state["source"] == "api" and now - _state["tried"] < cfg.DONG_REFRESH_DAYS * 86400: return info()
        if not force and now - _state["tried"] < 600: return info()       # 실패 시에도 10분에 한 번만 재시도
        _state["tried"] = now
        try:
            t = fetch_from_api(key)
            _install(t, "api", time.strftime("%Y-%m-%d %H:%M"))
            _state["error"] = None
            try:
                os.makedirs(cfg.CACHE_DIR, exist_ok=True)
                json.dump({"updated": _state["updated"], "table": t}, open(_cache_path(), "w", encoding="utf-8"), ensure_ascii=False)
            except Exception: pass
        except Exception as e:
            _state["error"] = "%s: %s" % (type(e).__name__, str(e)[:120])
    return info()

def info():
    return {"source": _state["source"], "count": len(_state["table"]), "updated": _state["updated"], "error": _state["error"], "api_key_set": bool(cfg.DATA_GO_KEY)}

def table(): return _state["table"]

def _startup():
    # 1) 최근 API 결과 캐시  2) 예비본  -> 그 뒤 API 갱신 시도
    try:
        c = json.load(open(_cache_path(), encoding="utf-8"))
        if time.time() - os.path.getmtime(_cache_path()) < cfg.DONG_REFRESH_DAYS * 86400:
            _install(c["table"], "api", c["updated"]); _state["tried"] = os.path.getmtime(_cache_path()); return
    except Exception: pass
    _install(json.load(open(BUNDLED, encoding="utf-8")), "bundled", "2026-10-15")
    refresh()
_startup()

class AddressError(Exception):
    def __init__(self, msg, code="bad_address"): super().__init__(msg); self.code = code

_RE = re.compile(r"^(?:서울특별시|서울시|서울)?\s*(?:(\S+?구)\s*)?(\S+?)\s*(산)?\s*(\d{1,4})(?:\s*-\s*(\d{1,4}))?\s*(?:번지)?$")

def parse(addr):
    """-> dict(gu, dong, san, bon, bu, code, pnu, text). 못 읽으면 AddressError"""
    a = " ".join(addr.replace("　", " ").split())
    m = _RE.match(a)
    if not m: raise AddressError("주소를 읽지 못했습니다: '%s' (예: 마포구 노고산동 57-1)" % addr)
    gu, dong, san, bon, bu = m.groups()
    dong = dong.replace(" ", "")
    cands = _state["by_dong"].get(dong, [])
    if not cands:
        refresh(); cands = _state["by_dong"].get(dong, [])        # 신설 동일 수 있으니 API 로 한 번 더 확인
    if gu: cands = [c for c in cands if c[0] == gu]
    if not cands:
        pool = [k for k in _state["table"] if (not gu or k.startswith(gu + " "))]
        near = difflib.get_close_matches((gu + " " if gu else "") + dong, pool, n=3, cutoff=0.6) or difflib.get_close_matches(dong, [k.split(" ", 1)[1] for k in _state["table"]], n=3, cutoff=0.6)
        raise AddressError("법정동 목록에 없는 동입니다: %s%s. 행정동 이름이 아니라 법정동 이름으로 입력하세요.%s" %
                           ((gu + " ") if gu else "", dong, (" 비슷한 이름: " + ", ".join(near)) if near else ""), "unknown_dong")
    if len(cands) > 1:
        raise AddressError("'%s'은(는) 여러 구에 있습니다. 구 이름을 함께 입력하세요: %s" % (dong, ", ".join("%s %s" % (c[0], dong) for c in cands)), "ambiguous_dong")
    gu, code = cands[0]
    bon_i, bu_i = int(bon), int(bu or 0)
    if bon_i == 0: raise AddressError("본번이 0입니다: " + addr)
    pnu = "%s%s%04d%04d" % (code, "2" if san else "1", bon_i, bu_i)
    jibun = ("산 " if san else "") + str(bon_i) + ("-%d" % bu_i if bu_i else "")
    return {"gu": gu, "dong": dong, "san": bool(san), "bon": bon_i, "bu": bu_i, "code": code, "pnu": pnu,
            "text": "서울특별시 %s %s %s" % (gu, [k.split(" ", 1)[1] for k, v in _state["table"].items() if k.startswith(gu + " ") and v == code][0], jibun),
            "prefix": "%s%s%04d" % (code, "2" if san else "1", bon_i)}
