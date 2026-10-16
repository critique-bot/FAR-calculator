"""지구단위계획 용적률 계산기 (Streamlit).  실행: streamlit run streamlit_app.py
법정동 코드표는 공공데이터포털 API(DATA_GO_KEY)로 자동 갱신하고, 키가 없거나 실패하면 data/legal_dong.json 예비본을 쓴다."""
import os
import streamlit as st
import streamlit.components.v1 as components

for _k in ("DATA_GO_KEY",):
    try:
        if _k in st.secrets: os.environ[_k] = str(st.secrets[_k])
    except Exception:
        pass
os.environ.setdefault("CACHE_DIR", "/tmp/far_cache")

import lookup_core as lc
import dongcode
import incdocs
from embed import build_html

st.set_page_config(page_title="지구단위계획 용적률", layout="wide")
st.markdown("<style>.block-container{padding-top:1.2rem;max-width:1280px}</style>", unsafe_allow_html=True)
SS = st.session_state
SS.setdefault("raw", None); SS.setdefault("msg", "")

with st.form("lookup", border=False):
    c1, c2 = st.columns([6, 1], vertical_alignment="bottom")
    text = c1.text_input("지번 조회", placeholder="마포구 노고산동 57-1, 57-2, 57-3", help="여러 필지는 쉼표로 구분하고, 뒤쪽은 번지만 써도 됩니다.")
    go = c2.form_submit_button("조회", use_container_width=True)
if go:
    if not text.strip():
        SS.msg = "지번을 입력하세요."
    else:
        try:
            with st.spinner("조회 중..."):
                SS.raw = lc.lookup_text(text)
            SS.msg = ("저장된 조회 결과를 불러왔습니다. " if SS.raw.get("캐시") else "조회했습니다. ") + f"({SS.raw.get('조회시각', '')})"
        except lc.LookupError_ as e:
            SS.msg = f"조회하지 못했습니다: {e}"
        except Exception as e:
            SS.msg = f"조회하지 못했습니다: {type(e).__name__}"
if SS.msg:
    st.caption(SS.msg)

with st.expander("접속 진단"):
    st.caption("이 서버에서 서울 도시공간포털과 법정동코드 API에 닿는지 확인합니다.")
    if st.button("진단 실행"):
        try:
            j = lc.portal_query(1, {"where": "PNU='1144011000100570001'", "outFields": "PNU", "returnGeometry": "false", "f": "json"})
            if j.get("features"): st.success("도시공간포털 필지 레이어: 정상")
            else: st.error("도시공간포털 응답은 왔으나 필지가 비어 있습니다.")
        except Exception as e:
            st.error(f"도시공간포털: {e}")
        d = dongcode.refresh(force=True)
        if d["source"] == "api": st.success(f"법정동 코드표: API 에서 {d['count']}개 갱신됨 ({d['updated']})")
        elif not d["api_key_set"]: st.warning(f"법정동 코드표: 예비본 {d['count']}개 사용 중 (DATA_GO_KEY 미설정 -> 자동 갱신 안 됨)")
        else: st.error(f"법정동 코드표 API 갱신 실패, 예비본 사용 중: {d['error']}")

def show_docs(raw):
    sns = dict(raw.get("구역SN") or {})
    for key in ("지구단위계획구역", "특별계획구역"):
        for x in raw.get(key) or []:
            if isinstance(x, dict) and x.get("PRESENT_SN"): sns[x["이름"]] = x["PRESENT_SN"]
    if not sns: return
    with st.expander("인센티브표 원문 (결정조서)", expanded=False):
        st.caption("최신 고시가 위에 나옵니다. 링크는 인센티브표가 있는 쪽으로 열립니다. 값은 원문 표로 확인하세요.")
        for name, sn in sns.items():
            r = incdocs.for_zone(sn)
            st.markdown("**%s**" % name)
            if not r["docs"]: st.caption(r["note"]); continue
            for d in r["docs"][:4]:
                st.markdown("- [%s](%s#page=%d)" % (d["file"], d["url"].replace(" ", "%20"), d["pages"][0][0]))

if SS.raw:
    show_docs(SS.raw)
    components.html(build_html(SS.raw), height=2000, scrolling=True)
else:
    st.info("지번을 조회하면 계산 화면이 나타납니다.")
