"""포털 용적률계획(레이어34) 문자열 -> 구조화. 해석 못하면 raw 유지 + flags."""
import re, json

NUM = r"(\d[\d,]*\.?\d*)"

def _first_num(s):
    m = re.search(NUM + r"\s*(?:%|m)", s or "")
    return float(m.group(1).replace(",", "")) if m else None

def parse_pct(s):
    """'880% 이하(중심상업지역 상향 시 930% 이하)' -> {value:880, alt:[{cond,value}], ref:None}"""
    out = {"raw": s, "value": None, "alt": [], "ref": None}
    if not s or not s.strip(): return out
    t = s.strip()
    if "조례" in t and "따" in t: out["ref"] = "조례"
    m = re.search(r"법\s*적용\s*(?:용)?적률(?:의)?\s*(\d+(?:\.\d+)?)\s*배", t)
    if m: out["mult_legal"] = float(m.group(1))
    mm = re.match(r"\s*(\d+)\s*[(（]\s*(\d+)\s*[)）]\s*m", t)   # 25(35)m
    if mm:
        out["value"] = float(mm.group(1)); out["alt"].append({"cond": "완화시", "value": float(mm.group(2))}); return out
    prev = 0
    for m in re.finditer(NUM + r"\s*(?:%|m)", t):
        pre = t[prev:m.start()]
        v = float(m.group(1).replace(",", ""))
        if re.search(r"상향|\s시[\s(（,]*$|시$", pre) and out["value"] is not None or ("상향" in pre):
            cond = re.sub(r"[()（）,]", " ", pre.split("이하")[-1]).strip()
            out["alt"].append({"cond": re.sub(r"\s*시$", "", cond).strip(), "value": v})
        elif out["value"] is None:
            out["value"] = v
        prev = m.end()
    return out

def parse_formula(s):
    """'기준용적률X(1+1.3X가중치Xα토지+0.7Xα건축물)' -> {base:'기준'|'허용', c_land, c_bldg, c_cash}"""
    if not s or "α" not in s: return None
    base = "허용" if s.replace(" ", "").startswith("허용") else ("기준" if "기준용적률" in s[:8] else None)
    def coef(word):
        m = re.search(NUM + r"\s*[Xx×\*]?\s*(?:가중치\s*[Xx×\*]?\s*)?α\s*" + word, s)
        return float(m.group(1)) if m else None
    return {"base": base, "c_land": coef("토지"), "c_bldg": coef("건축물"), "c_cash": coef("현금"),
            "c_bldg_cash": coef("현금.?건축물") or coef("건축물.?현금"), "raw": s}

def parse_incentive_code(s):
    """'2;IN001' -> (type 2, code IN001).  의미는 미확정(가설: 1=세부개발계획 위임, 2=고시 인센티브표)"""
    if not s: return None
    a, _, b = s.partition(";")
    return {"type": a.strip() or None, "code": b.strip() or None}

def parse_record(a):
    r = {"기호": a.get("기호") or a.get("NONUSE")}
    for k, f in (("기준", "STANFARA"), ("허용", "PERMITFARA"), ("상한", "MAXFARA")):
        r[k] = parse_pct(a.get(k) or a.get(f))
    r["상한식"] = parse_formula(a.get("상한") or a.get("MAXFARA") or "")
    r["건폐"] = parse_pct(a.get("건폐") or a.get("BDTLDR"))
    r["높이"] = parse_pct(a.get("높이") or a.get("TOP"))
    r["인센티브"] = parse_incentive_code(a.get("인센티브코드") or a.get("INCENTIVE"))
    fl = []
    if r["허용"]["ref"]: fl.append("허용용적률 조례 위임")
    if r["허용"]["alt"] or r["상한"]["alt"]: fl.append("조건부 값 있음(용도지역 상향 등)")
    if r["상한"]["value"] is None and not r["상한"].get("mult_legal") and not r["상한식"]: fl.append("상한 미기재")
    if r["상한식"] and r["상한식"]["c_land"] is None: fl.append("상한 산식 계수 해석 실패")
    r["flags"] = fl
    return r

if __name__ == "__main__":
    for rec in json.load(open("조회결과.json", encoding="utf-8")):
        for fr in rec.get("용적률계획", []):
            print(rec["입력"], json.dumps(parse_record(fr), ensure_ascii=False))
