"""인센티브표 원문 쪽 안내. data/incentive_pages.json (결정조서 글자에서 자동 탐색한 쪽 번호)."""
import json, os
_P = os.path.join(os.path.dirname(__file__), "data", "incentive_pages.json")
try: DATA = json.load(open(_P, encoding="utf-8"))
except Exception: DATA = {}

def _rng(pages):
    out = []; 
    for p in pages:
        if out and p == out[-1][1] + 1: out[-1][1] = p
        else: out.append([p, p])
    return out

def for_zone(sn):
    """-> dict(status, docs[{file,url,pages:[[a,b]],year,no}], note)"""
    z = DATA.get(sn)
    if not z: return {"status": "none", "docs": [], "note": "이 구역의 결정조서 목록이 없습니다 (특별계획구역은 상위 지구단위계획구역 문서를 확인하세요)."}
    ok = [d for d in z["docs"] if d.get("pages")]
    ok.sort(key=lambda d: ((d.get("year") or 0), (d.get("no") or 0)), reverse=True)
    docs = [{"file": d["file"], "url": d["url"], "pages": _rng(d["pages"]), "year": d.get("year"), "no": d.get("no")} for d in ok]
    if docs: return {"status": "found", "docs": docs, "note": ""}
    sc = [d["file"] for d in z["docs"] if d.get("status") == "스캔본"]
    if sc: return {"status": "scanned", "docs": [], "note": "결정조서가 스캔본이라 표 위치를 찾지 못했습니다: " + ", ".join(sc[:3])}
    if any(d.get("status") == "ok" for d in z["docs"]): return {"status": "no_table", "docs": [], "note": "결정조서에서 인센티브표를 찾지 못했습니다. 고시문 또는 계획설명서를 확인하세요."}
    return {"status": "none", "docs": [], "note": "받은 결정조서가 없습니다."}
