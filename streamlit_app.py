"""지구단위계획 용적률 계산기 (Streamlit).  실행: streamlit run streamlit_app.py
법정동 코드표는 공공데이터포털 API(DATA_GO_KEY)로 자동 갱신하고, 키가 없거나 실패하면 data/legal_dong.json 예비본을 쓴다."""
import os
import streamlit as st

for _k in ("DATA_GO_KEY",):
    try:
        if _k in st.secrets: os.environ[_k] = str(st.secrets[_k])
    except Exception:
        pass

os.environ.setdefault("CACHE_DIR", "/tmp/far_cache")

import settings as cfg
import lookup_core as lc
import engine
from siteview import site_view, REGISTRY

st.set_page_config(page_title="지구단위계획 용적률", layout="wide")
st.markdown("<style>[data-testid=stMetricValue]{font-size:1.6rem}[data-testid=stMetricLabel]{font-size:.85rem}</style>", unsafe_allow_html=True)

def f(n, d=1):
    return "-" if n is None else f"{n:,.{d}f}"

TAG = {"warn": "해석 필요", "info": "사용자입력"}
SS = st.session_state
SS.setdefault("site", None); SS.setdefault("n", 0); SS.setdefault("msg", "")

# ---------------------------------------------------------------- 조회
st.title("지구단위계획 용적률")
st.caption("지번을 입력하면 구역과 용적률 계획을 조회하고, 인센티브와 기부채납을 반영해 용적률과 연면적을 계산합니다.")

with st.form("lookup"):
    text = st.text_input("지번 (여러 필지는 쉼표로 구분, 뒤쪽은 번지만 써도 됩니다)", placeholder="마포구 노고산동 57-1, 57-2, 57-3")
    go = st.form_submit_button("조회")
if go:
    if not text.strip():
        SS.msg = "지번을 입력하세요."
    else:
        try:
            with st.spinner("조회 중..."):
                raw = lc.lookup_text(text)
            SS.site = site_view(raw); SS.raw = raw; SS.n += 1
            SS.msg = ("저장된 조회 결과를 불러왔습니다. " if raw.get("캐시") else "조회했습니다. ") + f"({raw.get('조회시각', '')})"
        except lc.LookupError_ as e:
            SS.msg = f"조회하지 못했습니다: {e}"
        except Exception as e:
            SS.msg = f"조회하지 못했습니다: {type(e).__name__}"
if SS.msg:
    st.caption(SS.msg)

with st.expander("접속 진단"):
    st.caption("이 서버에서 서울 도시공간포털에 닿는지 확인합니다.")
    if st.button("진단 실행"):
        try:
            j = lc.portal_query(1, {"where": "PNU='1144011000100570001'", "outFields": "PNU", "returnGeometry": "false", "f": "json"})
            st.success("도시공간포털 필지 레이어: 정상") if j.get("features") else st.error("도시공간포털 응답은 왔으나 필지가 비어 있습니다.")
        except Exception as e:
            st.error(f"도시공간포털: {e}")
        import dongcode
        d = dongcode.refresh(force=True)
        if d["source"] == "api": st.success(f"법정동 코드표: API 에서 {d['count']}개 갱신됨 ({d['updated']})")
        elif not d["api_key_set"]: st.warning(f"법정동 코드표: 예비본 {d['count']}개 사용 중 (DATA_GO_KEY 미설정 -> 자동 갱신 안 됨)")
        else: st.error(f"법정동 코드표 API 갱신 실패, 예비본 사용 중: {d['error']}")

site = SS.site
if not site:
    st.info("지번을 조회하면 계산 화면이 나타납니다.")
    st.stop()

K = f"{SS.n}_"           # 새 조회마다 입력 위젯 초기화
reg = site["registry"]; ps = site["portal_standard"]
st.header(site["label"] + " 용적률")
st.caption(" · ".join([x for x in [", ".join(site["zones"]), ", ".join(site["special"]), reg["label"] if reg else "", ", ".join(site["use_zones"]), "업무시설"] if x]))
if site["redevelopment"]: st.caption("정비구역 등: " + ", ".join(site["redevelopment"]))

left, right = st.columns([3, 2], gap="large")

with left:
    # ---- 대지
    st.subheader("대지")
    A = float(site["area"]); alt = reg.get("altArea") if reg else None
    c1, c2 = st.columns(2)
    c1.metric("대지면적(지적)", f"{f(A)} ㎡")
    if alt: c2.metric(f"대지면적({reg['altName']})", f"{f(alt)} ㎡")
    basis = "main"
    if alt:
        basis = "alt" if st.radio("연면적 산정 기준 면적", ["지적", reg["altName"]], horizontal=True, key=K + "basis") != "지적" else "main"
    Ac = alt if basis == "alt" else A

    # ---- 법정 기준
    st.subheader("법정 기준")
    if reg:
        s = reg["std"]; std = dict(bcr=s["bcr"], base=s["base"], permit=s["permit"], legal=s["legal"], mult=s["mult"], h=s["h"],
                                   cL=s["cL"], cB=s["cB"], cC=s["cC"], baseOf=s["baseOf"]); tag = None; refs = reg["refs"]; upper_note = s["upperText"]
    elif ps:
        fm = ps["산식"] or {}
        std = dict(bcr=ps["건폐율"], base=ps["기준"], permit=ps["허용"], legal=ps["법적용적률"], mult=ps["상한배수"], h=ps["높이"],
                   cL=fm.get("c_land") or 1.3, cB=fm.get("c_bldg") if fm.get("c_bldg") is not None else 1.0,
                   cC=fm.get("c_cash") if fm.get("c_cash") is not None else 1.0, baseOf=fm.get("기준", "permit"))
        tag = "포털값, 고시 확인 필요"; refs = ["서울특별시 도시계획 조례"] if ps["법적용적률"] else []
        upper_note = "포털 표기: " + (ps["상한표기"] or "미기재")
    else:
        std = dict(bcr=None, base=None, permit=None, legal=None, mult=None, h=None, cL=1.3, cB=1.0, cC=1.0, baseOf="permit")
        tag = "직접 입력"; refs = []; upper_note = "지구단위계획 용적률 없음"
    if tag: st.caption(tag)

    def fld(col, label, key, unit, d=0):
        v = std[key]
        if v is None:
            x = col.number_input(label + f" ({unit})", min_value=0.0, value=0.0, step=1.0, key=K + "std_" + key)
            return x or None
        col.metric(label, f"{f(v, d)} {unit}")
        return v
    r1 = st.columns(3)
    bcr = fld(r1[0], "건폐율", "bcr", "% 이하"); base = fld(r1[1], "기준용적률", "base", "% 이하"); permit = fld(r1[2], "허용용적률", "permit", "% 이하")
    r2 = st.columns(2)
    legal = fld(r2[0], "법적용적률", "legal", "%"); mult = fld(r2[1], "상한 배수", "mult", "배", 1)
    cap = legal * mult if legal and mult else None
    h = fld(st.columns(1)[0], "최고높이", "h", "m 이하")
    if cap:
        st.metric("상한용적률", f"{f(cap, 0)} % 이하"); st.caption("(법적용적률의 %g배 이하)" % mult if mult != 1 else "")
    else:
        st.metric("상한용적률", "미결정"); st.caption(upper_note)
    if refs:
        st.caption("참고"); [st.caption(f"{i + 1}. {r}") for i, r in enumerate(refs)]

    # ---- 허용용적률 인센티브
    st.subheader("허용용적률 인센티브")
    items = []
    if reg:
        for d in reg["items"]:
            lab = TAG.get(d.get("tag", "info"), "사용자입력")
            if d["kind"] == "fixed":
                on = st.checkbox(f"{d['name']}  +{d['val']}%p  [{lab}]", value=bool(d.get("on")), key=K + d["id"], help=d["req"])
                items.append(dict(d, on=on, label=lab))
            elif d["kind"] == "biz":
                a, b = st.columns([3, 2])
                on = a.checkbox(f"{d['name']}  최대 {d['max']}%p  [{lab}]", value=bool(d.get("on")), key=K + "c_biz", help=d["req"])
                ratio = b.number_input("업무 비율 (%)", 0.0, 100.0, 100.0, 1.0, key=K + "i_biz")
                items.append(dict(d, on=on, ratio=ratio, label=lab))
            else:
                a = st.number_input(f"{d['name']}  도입면적 (㎡)  [계수 {d['coef']}, 최대 {d['max']}%p]", 0.0, value=0.0, step=1.0, key=K + "r_" + d["id"], help=d["req"])
                items.append(dict(d, on=a > 0, area=a, label="사용자입력"))
        st.caption(reg["incSrc"])
    else:
        st.caption("고시의 인센티브표를 보고 항목을 직접 입력합니다. 정량은 가산 %p, 정률은 기준용적률 × (도입면적 ÷ 대지면적) × 계수로 계산하고 최대치를 넘지 않습니다.")
        import pandas as pd
        df = st.data_editor(pd.DataFrame([{"항목": "", "구분": "정량", "값": 0.0, "계수": 0.0, "최대(%p)": 0.0}]), num_rows="dynamic", key=K + "cust",
                            column_config={"구분": st.column_config.SelectboxColumn("구분", options=["정량", "정률"], required=True),
                                           "값": st.column_config.NumberColumn("가산 %p 또는 도입면적 ㎡", min_value=0.0)},
                            width="stretch")
        for _, r in df.iterrows():
            if (r["값"] or 0) > 0:
                if r["구분"] == "정량": items.append(dict(name=r["항목"], kind="fixed", on=True, val=float(r["값"]), max=float(r["최대(%p)"] or 0) or None, label="사용자입력"))
                else: items.append(dict(name=r["항목"], kind="rate", on=True, area=float(r["값"]), coef=float(r["계수"] or 0), max=float(r["최대(%p)"] or 0) or None, label="사용자입력"))
    # fixed 의 최대치 처리: 엔진은 fixed 에 max 를 적용하지 않으므로 여기서 val 을 제한
    for it in items:
        if it["kind"] == "fixed" and it.get("max") and not reg: it["val"] = min(it["val"], it["max"])

    # ---- 상한용적률
    st.subheader("상한용적률")
    st.caption("0이면 상한 비대상입니다. α = 제공면적 ÷ 제공 후 대지면적.")
    g1 = st.columns(3)
    land = g1[0].number_input("부지 제공 (㎡)", 0.0, value=0.0, step=1.0, key=K + "land")
    bldg = g1[1].number_input("건축물 설치 환산 (㎡)", 0.0, value=0.0, step=1.0, key=K + "bldg")
    cash = g1[2].number_input("현금 환산 부지 (㎡)", 0.0, value=0.0, step=1.0, key=K + "cash")
    weight = st.number_input("가중치 (제공부지 용적률 ÷ 사업부지 용적률)", 0.0, value=1.0, step=0.1, key=K + "w")
    with st.expander("산식 계수"):
        k1 = st.columns(4)
        cL = k1[0].number_input("토지", 0.0, value=float(std["cL"]), step=0.1, key=K + "cL")
        cB = k1[1].number_input("건축물", 0.0, value=float(std["cB"]), step=0.1, key=K + "cB")
        cC = k1[2].number_input("현금", 0.0, value=float(std["cC"]), step=0.1, key=K + "cC")
        base_of = k1[3].selectbox("곱하는 기준", ["permit", "base"], index=0 if std["baseOf"] == "permit" else 1, format_func=lambda x: "허용용적률" if x == "permit" else "기준용적률", key=K + "bo")
        st.caption(reg["gSrc"] if reg and reg.get("gSrc") else "산식 계수는 구역마다 다릅니다.")

# ---------------------------------------------------------------- 결과
with right:
    st.subheader("결과")
    if not base or not permit:
        st.warning("기준용적률과 허용용적률을 입력하세요.")
    else:
        res = engine.compute(dict(area=A, alt_area=alt, basis=basis, base=base, permit=permit, legal=legal, mult=mult,
                                  c_land=cL, c_bldg=cB, c_cash=cC, base_of=base_of, land=land, bldg=bldg, cash=cash, weight=weight, items=items))
        st.metric("허용용적률 (인센티브 반영)", f"{f(res['permit'])} %")
        room = res["incentive_room"]
        st.progress(min(1.0, res["incentive_applied"] / room) if room else 0.0,
                    text=f"인센티브 {f(res['incentive_input'])}%p 입력, {f(res['incentive_applied'])}%p 적용 (한도 {f(room)}%p)")
        fa = res["floor_area"]; rows = []
        for k, nm in (("base", "기준"), ("permit", "허용"), ("upper", "상한")):
            if k in fa:
                row = {"구분": nm, "용적률": f"{f(fa[k]['pct'])}%", "연면적(대지)" if alt else "연면적(㎡)": f(fa[k]["main"])}
                if alt: row[f"연면적({reg['altName'].split()[0]})"] = f(fa[k].get("alt"))
                rows.append(row)
            elif k == "upper":
                rows.append({"구분": "상한", "용적률": "비대상", **{c: "-" for c in (["연면적(대지)", f"연면적({reg['altName'].split()[0]})"] if alt else ["연면적(㎡)"])}})
        st.dataframe(rows, hide_index=True, width="stretch")
        notes = [("", t) for t in site["warnings"] + site["notes"]] + [("", t) for t in (ps["flags"] if ps and not reg else [])]
        notes += [(n["level"], n["text"]) for n in res["notes"]]
        for it in items:
            if it.get("on") and it.get("tag") == "warn":
                notes.append(("", it["name"] + ": 해석 필요. " + ("비례 환산식이 문서에 없어 업무 100%를 최대치로 적용." if it["id"] == "biz" else "조성 세부기준은 향후 가이드라인에 따름.")))
        seen = set()
        for lv, t in notes:
            if t in seen: continue
            seen.add(t)
            (st.error if lv == "bad" else st.success if lv == "ok" else st.markdown)(t if lv in ("bad", "ok") else "- " + t)
