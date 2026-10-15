"""용적률 계산 (서버 기준 구현). 외부 호출 없음.
허용 = 기준 + min(인센티브 합, 허용-기준)
상한 = (기준 또는 허용) × (1 + c토지×가중치×α토지 + c건축물×α건축물 + c현금×α현금), 한도 = 법적용적률 × 배수
α = 제공면적 / (대지면적 - 부지 제공면적)
라벨: 고시확정 / 조문계산 / 사용자입력 / 해석필요
"""
from typing import Optional

def _pos(x): 
    try: x = float(x)
    except (TypeError, ValueError): return 0.0
    return x if x > 0 else 0.0

def compute(p: dict) -> dict:
    A = _pos(p.get("area")); alt = _pos(p.get("alt_area"))
    use_alt = bool(alt) and p.get("basis") == "alt"
    Ac = alt if use_alt else A
    base, permit_max = _pos(p.get("base")), _pos(p.get("permit"))
    notes = []; rows = []; total = 0.0
    for it in p.get("items", []):
        k = it.get("kind"); v = 0.0
        if k == "fixed":
            if it.get("on"): v = _pos(it.get("val"))
        elif k == "biz":
            if it.get("on"):
                r = min(100.0, _pos(it.get("ratio", 100)))
                v = _pos(it.get("max")) * r / 100 if r >= 50 else 0.0
                if 0 < r < 50: notes.append(("bad", "업무전용빌딩: 업무시설 비율 50% 미만은 대상이 아니라 0으로 계산했습니다."))
        elif k == "rate":
            a = _pos(it.get("area"))
            if a > 0 and Ac > 0:
                v = base * (a / Ac) * _pos(it.get("coef"))
                if it.get("max") is not None and _pos(it.get("max")) > 0: v = min(v, _pos(it["max"]))
        if v: rows.append({"name": it.get("name"), "pct_p": round(v, 2), "label": it.get("label", "사용자입력")})
        total += v
    room = max(0.0, permit_max - base)
    applied = min(total, room)
    permit = base + applied
    out = {"area_used": Ac, "base": base, "permit_max": permit_max, "incentive_rows": rows,
           "incentive_input": round(total, 2), "incentive_room": round(room, 2), "incentive_applied": round(applied, 2),
           "permit": round(permit, 2)}
    if permit_max and total > room: notes.append(("", "인센티브 입력 합계 %.1f%%p가 한도 %.1f%%p를 넘어 한도까지만 적용했습니다." % (total, room)))
    if permit_max and 0 < total < room: notes.append(("", "허용용적률 %.0f%%까지 %.1f%%p 부족합니다." % (permit_max, room - applied)))

    legal, mult = _pos(p.get("legal")), _pos(p.get("mult"))
    cap = legal * mult if legal and mult else 0.0
    gL, gB, gC, w = _pos(p.get("land")), _pos(p.get("bldg")), _pos(p.get("cash")), _pos(p.get("weight") or 1) or 1.0
    cL, cB, cC = _pos(p.get("c_land", 1.3)), _pos(p.get("c_bldg", 1.0)), _pos(p.get("c_cash", 1.0))
    bv = base if p.get("base_of") == "base" else permit
    upper = upper_raw = None; capped = False
    if gL > 0 or gB > 0 or gC > 0:
        after = Ac - gL
        if after <= 0:
            notes.append(("bad", "부지 기부채납 면적이 대지면적 이상입니다."))
        else:
            upper_raw = bv * (1 + cL * w * (gL / after) + cB * (gB / after) + cC * (gC / after))
            upper = min(upper_raw, cap) if cap else upper_raw
            capped = bool(cap) and upper_raw > cap
            out.update({"alpha_land": round(gL / after, 4), "alpha_bldg": round(gB / after, 4), "alpha_cash": round(gC / after, 4)})
            notes.append(("", "상한은 정비계획 또는 지구단위계획 변경에서 결정됩니다. 여기 값은 산식에 따른 참고값입니다."))
            if capped: notes.append(("bad", "산식 값 %.1f%%가 한도 %.0f%%를 넘어 한도로 제한했습니다." % (upper_raw, cap)))
            if not cap: notes.append(("", "상한 한도(법적용적률 × 배수)가 입력되지 않아 한도를 적용하지 않았습니다."))
            notes.append(("", "산식 계수(토지 %g, 건축물 %g, 현금 %g)는 해당 고시 문구와 맞는지 확인이 필요합니다." % (cL, cB, cC)))
    else:
        notes.append(("ok", "상한 비대상: 공공기여 입력이 모두 0입니다."))
    out.update({"cap": cap or None, "upper_raw": None if upper_raw is None else round(upper_raw, 2),
                "upper": None if upper is None else round(upper, 2), "capped": capped})
    # 연면적
    def fa(site, pct_, sub):
        return round((site - (gL if sub else 0)) * pct_ / 100, 1)
    areas = {"base": {"pct": base, "main": fa(A, base, False)}, "permit": {"pct": round(permit, 2), "main": fa(A, permit, False)}}
    if upper is not None: areas["upper"] = {"pct": round(upper, 2), "main": fa(A, upper, True)}
    if alt:
        for k, v in areas.items(): v["alt"] = fa(alt, v["pct"], k == "upper")
    out["floor_area"] = areas
    out["notes"] = [{"level": l, "text": t} for l, t in notes]
    return out
