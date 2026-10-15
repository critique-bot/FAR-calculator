import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["CACHE_DIR"] = tempfile.mkdtemp(); os.environ["VWORLD_KEY"] = "TEST"; os.environ["RATE_PER_MIN"] = "1000"
import pytest
from fastapi.testclient import TestClient
import settings; settings.CACHE_DIR = os.environ["CACHE_DIR"]; settings.VWORLD_KEY = "TEST"
import app as appmod, lookup_core as lc, engine, standard

client = TestClient(appmod.app)
SAMPLES = json.load(open(os.path.join(os.path.dirname(__file__), "samples.json"), encoding="utf-8"))
def sample(name): return next(s for s in SAMPLES if name in s["입력"])

# ---------- 엔진: 노고산동 57-1~3 회귀 ----------
M2 = appmod.REGISTRY["신촌지구일대 지구단위계획구역|특별계획구역 4"]
def mapo2(**kw):
    items = [{"id": i, "on": True} for i in ("biz", "open", "ev", "green", "barrier")] + [{"id": "disaster", "on": True}]
    b = dict(area=1624.5, alt_area=1607.7, base=600, permit=800, legal=800, mult=2, registry_key="신촌지구일대 지구단위계획구역|특별계획구역 4", items=items)
    b.update(kw); return b

def test_mapo2_permit_800():
    r = client.post("/api/calc", json=mapo2()).json()["result"]
    assert r["permit"] == 800 and r["incentive_input"] == 50 + 50 + 20 + 20 + 30 + 30 and r["incentive_applied"] == 200
    assert r["floor_area"]["permit"]["main"] == 12996.0 and r["floor_area"]["permit"]["alt"] == 12861.6
    assert r["floor_area"]["base"]["main"] == 9747.0 and r["floor_area"]["base"]["alt"] == 9646.2
    assert "upper" not in r["floor_area"]       # 공공기여 0 -> 상한 비대상

def test_mapo2_planned_three_items_720():
    items = [{"id": "biz", "on": True}, {"id": "open", "on": True}, {"id": "disaster", "on": True}]
    r = client.post("/api/calc", json=mapo2(items=items)).json()["result"]
    assert r["permit"] == 600 + 50 + 50 + 20 == 720

def test_biz_below_50_is_zero():
    r = client.post("/api/calc", json=mapo2(items=[{"id": "biz", "on": True, "ratio": 40}])).json()["result"]
    assert r["permit"] == 600 and any("50% 미만" in n["text"] for n in r["notes"])

def test_upper_land_10pct():
    r = client.post("/api/calc", json=mapo2(land=162.45)).json()["result"]
    assert r["permit"] == 800 and r["upper"] == pytest.approx(915.56, abs=0.01) and not r["capped"]
    assert r["floor_area"]["upper"]["main"] == pytest.approx((1624.5 - 162.45) * 9.1556, abs=0.2)

def test_upper_capped_at_1600():
    r = client.post("/api/calc", json=mapo2(land=800)).json()["result"]
    assert r["upper"] == 1600 and r["capped"] is True

def test_upper_bad_land():
    r = client.post("/api/calc", json=mapo2(land=2000)).json()["result"]
    assert r["upper"] is None and any("대지면적 이상" in n["text"] for n in r["notes"])

def test_rate_item_custom():
    b = dict(area=1000, base=300, permit=400, items=[{"name": "x", "kind": "rate", "on": True, "area": 100, "coef": 0.3, "max": 50}])
    r = client.post("/api/calc", json=b).json()["result"]
    assert r["incentive_input"] == pytest.approx(9.0) and r["permit"] == pytest.approx(309.0)
    b["items"][0]["area"] = 5000; b["items"][0]["max"] = 50
    r = client.post("/api/calc", json=b).json()["result"]
    assert r["incentive_input"] == 50 and r["permit"] == 350

def test_calc_validation():
    assert client.post("/api/calc", json={"area": 0, "base": 1, "permit": 1}).status_code == 422
    assert client.post("/api/calc", json=mapo2(registry_key="없음")).status_code == 422

# ---------- 법정 기준 해석: 실제 조회 샘플 8건 ----------
def test_standard_samples():
    s = standard.derive(sample("군자동")["용적률계획"][0], "일반상업지역")
    assert (s["기준"], s["허용"], s["상한한도"], s["건폐율"], s["높이"]) == (300, 630, 800, 60, 100)
    s = standard.derive(sample("노고산동")["용적률계획"][0], "일반상업지역")
    assert (s["기준"], s["허용"], s["법적용적률"], s["상한배수"], s["상한한도"]) == (600, 800, 800, None, None)
    s = standard.derive(sample("역삼동")["용적률계획"][0], "일반상업지역")
    assert (s["기준"], s["허용"], s["상한배수"], s["상한한도"]) == (800, 880, 2, 1600) and s["flags"]
    s = standard.derive(sample("종로1가")["용적률계획"][0], "일반상업지역")
    assert s["허용"] is None and any("조례 위임" in f for f in s["flags"]) and s["산식"]["c_bldg"] == 0.7 and s["산식"]["기준"] == "base"
    s = standard.derive(sample("성수동1가")["용적률계획"][0], "준주거지역")
    assert (s["높이"], s["상한한도"]) == (25, None) or s["높이"] == 25      # 25(35)m -> 25 + 완화 35
    s = standard.derive(sample("잠실동")["용적률계획"][0], "일반상업지역")
    assert s["상한한도"] == 1600

def test_site_view_samples():
    v = appmod.site_view(sample("노고산동"))
    assert v["registry_key"] and v["area"] == 546.9 and v["zones"] == ["신촌지구일대 지구단위계획구역"]
    v = appmod.site_view(sample("불광동"))
    assert v["plans"] == [] and v["portal_standard"] is None and v["warnings"]
    v = appmod.site_view(sample("군자동"))
    assert v["registry_key"] is None and v["redevelopment"] == [] and v["portal_standard"]["출처"].startswith("포털값")

# ---------- 조회: 외부 호출을 가짜로 바꿔 전체 흐름 검증 ----------
def rect(x0, y0, x1, y1): return [[[x0, y0], [x0, y1], [x1, y1], [x1, y0], [x0, y0]]]   # 시계방향(외곽)
class Fake:
    def __init__(self): self.calls = []
    def pnu(self, addr):
        self.calls.append(("pnu", addr))
        if "없는동" in addr: raise lc.LookupError_("주소를 찾지 못했습니다: " + addr, "address_not_found")
        n = addr.split()[-1]; return "1144011000100" + n.replace("-", "0000")[:6].ljust(6, "0"), "서울특별시 마포구 노고산동 " + n
    def portal(self, layer, params):
        self.calls.append(("portal", layer))
        parcel = rect(0, 0, 10, 10)
        if layer == 1: return {"features": [{"geometry": {"rings": parcel}, "attributes": {}}]}
        if layer == 28: return {"features": [{"geometry": {"rings": rect(-5, -5, 20, 20)}, "attributes": {"DGM_NM": "신촌지구일대 지구단위계획구역", "PRESENT_SN": "S1"}}]}
        if layer == 29: return {"features": [{"geometry": {"rings": rect(-5, -5, 20, 20)}, "attributes": {"DGM_NM": "특별계획구역 4", "PRESENT_SN": "S2"}}]}
        if layer == 34: return {"features": [{"geometry": {"rings": rect(-5, -5, 20, 20)}, "attributes": {"NONUSE": "특4", "STANFARA": "600%이하", "PERMITFARA": "800%이하", "MAXFARA": " ", "BDTLDR": "60%이하", "TOP": "100m이하", "INCENTIVE": "1;"}}]}
        if layer == 63: return {"features": [{"geometry": {"rings": rect(-5, -5, 20, 20)}, "attributes": {"DGM_NM": "일반상업지역", "CREATE_DAT": "20200101"}}]}
        if layer == 64: return {"features": [{"geometry": {"rings": rect(-5, -5, 20, 20)}, "attributes": {"DGM_NM": "신촌지역 마포2도시환경정비구역"}}, {"geometry": {"rings": rect(-5, -5, 20, 20)}, "attributes": {"DGM_NM": "대현토지구획정리사업"}}]}
        return {"features": []}

@pytest.fixture
def fake(monkeypatch, tmp_path):
    f = Fake(); monkeypatch.setattr(lc, "vworld_pnu", f.pnu); monkeypatch.setattr(lc, "portal_query", f.portal)
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path)); return f

def test_lookup_single(fake):
    j = client.post("/api/lookup", json={"text": "마포구 노고산동 57-1"}).json()
    assert j["ok"] and j["raw"]["필지면적"] == 100.0
    s = j["site"]; assert s["registry_key"] and s["special"] == ["특별계획구역 4"] and s["redevelopment"] == ["신촌지역 마포2도시환경정비구역"]
    assert s["portal_standard"]["허용"] == 800

def test_lookup_group_and_cache(fake):
    j = client.post("/api/lookup", json={"text": "마포구 노고산동 57-1, 57-2, 57-3"}).json()
    assert j["ok"] and len(j["raw"]["필지"]) == 3 and j["raw"]["합계면적"] == 300.0
    n = len(fake.calls)
    j2 = client.post("/api/lookup", json={"text": "마포구 노고산동 57-1, 57-2, 57-3"}).json()
    assert j2["ok"] and j2["raw"]["캐시"] is True and j["raw"]["캐시"] is False and len(fake.calls) == n          # 두 번째는 캐시 -> 외부 호출 없음

def test_lookup_not_found(fake):
    r = client.post("/api/lookup", json={"text": "마포구 없는동 1"})
    assert r.status_code == 422 and r.json()["code"] == "address_not_found"

def test_lookup_upstream_down(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    def boom(*a, **k): raise lc.LookupError_("외부 서비스 응답 오류 403 (urban.seoul.go.kr)", "upstream_http_403")
    monkeypatch.setattr(lc, "vworld_pnu", lambda a: ("1144011000100570001", "서울특별시 마포구 노고산동 57-1")); monkeypatch.setattr(lc, "portal_query", boom)
    r = client.post("/api/lookup", json={"text": "마포구 노고산동 57-1"})
    assert r.status_code == 502 and "403" in r.json()["message"]

def test_split_group():
    assert lc.split_group("마포구 노고산동 57-1, 57-2, 57-3") == ["마포구 노고산동 57-1", "마포구 노고산동 57-2", "마포구 노고산동 57-3"]
    assert lc.split_group("마포구 노고산동 57-1\n마포구 노고산동 57-2") == ["마포구 노고산동 57-1", "마포구 노고산동 57-2"]

def test_too_many(fake, monkeypatch):
    monkeypatch.setattr(settings, "MAX_PARCELS", 2)
    r = client.post("/api/lookup", json={"text": "마포구 노고산동 1, 2, 3"})
    assert r.status_code == 422 and r.json()["code"] == "too_many"

def test_diagnose_ok(fake):
    d = client.get("/api/diagnose").json()
    assert d["vworld"]["ok"] is False or d["vworld"]["ok"] is True       # 가짜 PNU 라 값 검사만, 구조 확인
    assert "portal" in d and "all_ok" in d

def test_diagnose_blocked(monkeypatch):
    def boom(*a, **k): raise lc.LookupError_("403", "upstream_http_403")
    monkeypatch.setattr(lc, "vworld_pnu", boom); monkeypatch.setattr(lc, "portal_query", boom)
    d = client.get("/api/diagnose").json()
    assert d["all_ok"] is False and d["vworld"]["hint"] and d["portal"]["hint"]

def test_health_and_no_key_leak():
    j = client.get("/api/health").json(); assert j["ok"] and "TEST" not in json.dumps(j)
