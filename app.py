"""지구단위계획 용적률 계산 API.   실행: uvicorn app:app --host 0.0.0.0 --port 8000"""
import json, os, time, collections, threading
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import settings as cfg
import lookup_core as lc
import engine, standard

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "0.1.0"

app = FastAPI(title="지구단위계획 용적률 API", version=VERSION)
if cfg.ALLOWED_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=cfg.ALLOWED_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])

# ---------- 간단한 IP별 속도 제한 (포털 보호) ----------
_hits = collections.defaultdict(collections.deque); _hl = threading.Lock()
def rate_ok(ip):
    now = time.time()
    with _hl:
        d = _hits[ip]
        while d and now - d[0] > 60: d.popleft()
        if len(d) >= cfg.RATE_PER_MIN: return False
        d.append(now); return True

def client_ip(req: Request):
    return (req.headers.get("x-forwarded-for", "").split(",")[0].strip() or (req.client.host if req.client else "?"))

# ---------- 모델 ----------
class LookupReq(BaseModel):
    text: Optional[str] = Field(None, description="'마포구 노고산동 57-1, 57-2, 57-3' 처럼 한 줄 (구분: , / | ; 줄바꿈)")
    addresses: Optional[List[str]] = Field(None, description="전체 주소 목록(묶음 조회)")

class ItemIn(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    kind: Optional[str] = None    # fixed | rate | biz (등록 구역이면 생략)
    on: bool = False
    val: Optional[float] = None   # fixed: 가산 %p
    area: Optional[float] = None  # rate: 도입시설면적 ㎡
    coef: Optional[float] = None  # rate: 보상계수
    max: Optional[float] = None   # 항목 최대 %p
    ratio: Optional[float] = None # biz: 업무복합비율 %

class CalcReq(BaseModel):
    area: float = Field(..., gt=0)
    alt_area: Optional[float] = None
    basis: str = "main"           # main | alt
    base: float = Field(..., ge=0)
    permit: float = Field(..., ge=0)
    legal: Optional[float] = None
    mult: Optional[float] = None
    c_land: float = 1.3
    c_bldg: float = 1.0
    c_cash: float = 1.0
    base_of: str = "permit"       # 상한 산식의 곱셈 기준: base | permit
    land: float = 0
    bldg: float = 0
    cash: float = 0
    weight: float = 1.0
    registry_key: Optional[str] = Field(None, description="등록 구역 키. 주면 항목 정의를 서버 등록표에서 가져오고 items 에는 on/ratio/area 만 보내면 됨")
    items: List[ItemIn] = []

from siteview import site_view, REGISTRY

# ---------- 엔드포인트 ----------
@app.get("/api/health")
def health():
    return {"ok": True, "version": VERSION, "vworld_key_set": bool(cfg.VWORLD_KEY), "registry_zones": len(REGISTRY)}

@app.post("/api/lookup")
def api_lookup(body: LookupReq, request: Request):
    if not rate_ok(client_ip(request)): raise HTTPException(429, "요청이 너무 많습니다. 잠시 뒤에 다시 시도하세요.")
    try:
        if body.addresses: r = lc.group([a.strip() for a in body.addresses if a.strip()]) if len(body.addresses) > 1 else lc.lookup(body.addresses[0])
        elif body.text: r = lc.lookup_text(body.text)
        else: raise lc.LookupError_("지번을 입력하세요.", "empty")
    except lc.LookupError_ as e:
        return JSONResponse({"ok": False, "code": e.code, "message": str(e)}, status_code=502 if e.code.startswith("upstream") or e.code == "portal_error" else 422)
    return {"ok": True, "raw": r, "site": site_view(r)}

@app.get("/api/lookup")
def api_lookup_get(q: str, request: Request):
    return api_lookup(LookupReq(text=q), request)

@app.post("/api/calc")
def api_calc(b: CalcReq):
    p = b.model_dump()
    items = []
    if b.registry_key:
        reg = REGISTRY.get(b.registry_key)
        if not reg: raise HTTPException(422, "등록되지 않은 구역: %s" % b.registry_key)
        given = {i.id: i for i in b.items if i.id}
        unknown = [k for k in given if k not in {d["id"] for d in reg["items"]}]
        if unknown: raise HTTPException(422, "등록 구역에 없는 항목: %s" % unknown)
        for d in reg["items"]:
            g = given.get(d["id"]); it = dict(d)
            if g is not None:
                it["on"] = g.on
                if g.ratio is not None: it["ratio"] = g.ratio
                if g.area is not None: it["area"] = g.area
            else: it["on"] = False
            if d["kind"] == "rate" and not it.get("area"): it["on"] = False
            it["label"] = {"warn": "해석필요", "info": "사용자입력"}.get(d.get("tag", "info"), "사용자입력")
            items.append(it)
    else:
        items = [i.model_dump() for i in b.items]
        if any(i["kind"] not in ("fixed", "rate", "biz") for i in items): raise HTTPException(422, "items[].kind 는 fixed | rate | biz 중 하나여야 합니다.")
    p["items"] = items
    return {"ok": True, "result": engine.compute(p)}

@app.get("/api/registry")
def api_registry():
    return {k: {"label": v["label"], "refs": v["refs"], "item_count": len(v["items"])} for k, v in REGISTRY.items()}

@app.get("/api/registry/full")
def api_registry_full(): return REGISTRY

@app.get("/api/diagnose")
def diagnose():
    """배포한 서버에서 외부 서비스에 닿는지 확인 (키는 노출하지 않음)"""
    out = {"vworld": None, "portal": None}
    t = time.time()
    try:
        pnu, text = lc.vworld_pnu("마포구 노고산동 57-1")
        out["vworld"] = {"ok": True, "ms": int((time.time() - t) * 1000), "pnu": pnu, "check": "PNU 1144011000100570001 기대" if pnu != "1144011000100570001" else "기대값과 일치"}
    except lc.LookupError_ as e:
        out["vworld"] = {"ok": False, "code": e.code, "message": str(e), "hint": {
            "no_vworld_key": "환경변수 VWORLD_KEY 설정",
            "upstream_http_403": "서버 IP 차단 또는 키/도메인 불일치(VWORLD_DOMAIN 이 키 발급 때 등록한 도메인인지 확인)",
            "upstream_unreachable": "서버 외부망 차단 여부 확인"}.get(e.code, "")}
    t = time.time()
    try:
        j = lc.portal_query(1, {"where": "PNU='1144011000100570001'", "outFields": "PNU", "returnGeometry": "false", "f": "json"})
        n = len(j.get("features") or [])
        out["portal"] = {"ok": n == 1, "ms": int((time.time() - t) * 1000), "features": n}
    except lc.LookupError_ as e:
        out["portal"] = {"ok": False, "code": e.code, "message": str(e), "hint": "도시공간포털 접속 차단일 수 있음: 다른 호스팅(국내 IDC)에서 재확인하거나 PORTAL_PROXY 환경변수 조정"}
    out["all_ok"] = bool(out["vworld"] and out["vworld"]["ok"] and out["portal"] and out["portal"]["ok"])
    return out

# ---------- 화면 ----------
STATIC = os.path.join(HERE, "static")
if os.path.isdir(STATIC):
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    @app.get("/")
    def index(): return FileResponse(os.path.join(STATIC, "index.html"))
