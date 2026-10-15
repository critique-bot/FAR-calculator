"""포털 용적률계획 레코드 -> 법정 기준(건폐율/기준/허용/상한/높이) 구조화. 해석 못하면 비워두고 flags."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_far import parse_pct, parse_formula

LEGAL_FAR = {"일반상업지역": 800}   # 서울특별시 도시계획 조례로 확인된 값만. 나머지는 입력 필요.

def derive(fr: dict, use_zone: str = None) -> dict:
    """fr: 용적률계획 한 건(기준/허용/상한/건폐/높이 문자열). use_zone: 용도지역명"""
    b, p, u = parse_pct(fr.get("기준")), parse_pct(fr.get("허용")), parse_pct(fr.get("상한"))
    bc, h = parse_pct(fr.get("건폐")), parse_pct(fr.get("높이"))
    fm = parse_formula(fr.get("상한") or "")
    legal = LEGAL_FAR.get(use_zone)
    mult = u.get("mult_legal")
    flags = []
    if u["value"] is not None and not mult: legal, mult = u["value"], 1.0   # 숫자 상한(예: 800%이하)
    s = {"건폐율": bc["value"], "기준": b["value"], "허용": p["value"], "법적용적률": legal, "상한배수": mult,
         "상한한도": legal * mult if legal and mult else None, "높이": h["value"],
         "상한표기": (fr.get("상한") or "").strip() or None,
         "산식": None, "출처": "포털값, 고시 확인 필요"}
    if fm:
        s["산식"] = {"기준": "base" if fm["base"] == "기준" else "permit", "c_land": fm["c_land"], "c_bldg": fm["c_bldg"], "c_cash": fm["c_cash"]}
    if p["ref"]: flags.append("허용용적률이 조례 위임으로 표기됨: 직접 입력 필요")
    if p["value"] is None and not p["ref"]: flags.append("허용용적률 미기재: 직접 입력 필요")
    if p["alt"] or u["alt"]: flags.append("조건부 값 있음(용도지역 상향 등): 기본값만 불러옴")
    if legal is None and mult: flags.append("법적용적률(조례) 값이 없어 상한 한도를 계산하지 못함: 직접 입력 필요")
    s["flags"] = flags
    return s
