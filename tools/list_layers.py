"""포털 지도 서비스의 레이어 목록을 뽑아 군자동 478-5 필지가 겹치는 레이어와 속성을 보여 줍니다.
사용 (서버 폴더에서):  python tools/list_layers.py            -> 레이어 목록(전체)
                       python tools/list_layers.py 478-5     -> 이 필지와 겹치는 레이어와 속성값
결과를 채팅에 붙여 주세요. (키 등 비밀은 쓰지 않습니다.)"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import settings as cfg
import lookup_core as lc
from urllib.parse import urlencode

def root():
    return lc.fetch_json(cfg.PORTAL_PROXY + cfg.PORTAL_BASE.rstrip("/") + "?f=json", timeout=40)

j = root()
layers = j.get("layers", [])
print("레이어 %d개" % len(layers))
for l in layers: print(l["id"], l["name"])
if len(sys.argv) > 1:
    addr = "광진구 군자동 " + sys.argv[1]
    p = lc.lookup(addr)
    pnu = p["PNU"]
    q = lc.portal_query(1, {"where": "PNU='%s'" % pnu, "outFields": "PNU", "returnGeometry": "true", "outSR": 5174, "f": "json"})
    geom = q["features"][0]["geometry"]
    print("\n필지", addr, pnu, "와 겹치는 레이어")
    for l in layers:
        try:
            r = lc.portal_query(l["id"], {"geometry": json.dumps(geom), "geometryType": "esriGeometryPolygon", "inSR": 5174, "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "false", "f": "json"})
        except Exception as e:
            continue
        fs = r.get("features", [])
        if fs:
            print("\n[%s] %s  (%d건)" % (l["id"], l["name"], len(fs)))
            for f in fs[:2]: print("  ", json.dumps(f["attributes"], ensure_ascii=False)[:400])
