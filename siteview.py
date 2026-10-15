"""조회 결과 -> 화면용 요약 (API·Streamlit 공용)"""
import json, os
import standard

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = json.load(open(os.path.join(HERE, "data", "registry.json"), encoding="utf-8"))

def site_view(r: dict) -> dict:
    """조회 결과(단일/묶음) -> 화면용 요약. 숫자는 포털값이며 등록구역이면 registry 값이 우선."""
    if "필지" in r:
        area = r["합계면적"]; zones = r["지구단위계획구역"]; sps = r["특별계획구역"]
        urs = list(r["용도지역"].keys()); frs = [dict(x, 비율=x["비율"]) for x in r["용적률계획_구성"]]
        label = ", ".join([r["입력"][0]] + [a.split()[-1] for a in r["입력"][1:]])
        judge = [x for x in r["정비구역등"]]
    else:
        area = r["필지면적"]; zones = [z["이름"] for z in r["지구단위계획구역"]]; sps = [z["이름"] for z in r["특별계획구역"]]
        urs = [u["이름"] for u in r["용도지역"]]; frs = [dict(x, 비율=x["겹침"], 인센티브=x["인센티브코드"]) for x in r["용적률계획"]]
        label = r["정제주소"]; judge = [x for x in r["정비구역등"] if "정비" in x]
    key = "%s|%s" % (zones[0] if zones else "", sps[0] if sps else "")
    reg = REGISTRY.get(key)
    main = max(frs, key=lambda x: x.get("비율") or 0) if frs else None
    std = standard.derive(main, urs[0] if urs else None) if main else None
    notes = []
    if len(frs) > 1: notes.append("용적률 계획이 %d개 겹침. 면적이 가장 큰 기호 %s 값을 기준으로 함." % (len(frs), main.get("기호")))
    return {"label": label, "area": area, "zones": zones, "special": sps, "use_zones": urs, "redevelopment": judge,
            "plans": frs, "portal_standard": std, "registry_key": key if reg else None,
            "registry": reg, "warnings": r.get("경고", []), "notes": notes}

