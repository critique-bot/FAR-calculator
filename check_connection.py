"""이 컴퓨터/서버에서 V-World와 서울 도시공간포털에 닿는지 확인.  사용: python check_connection.py
(서버를 올릴 곳에서 먼저 돌려보세요. 호스팅을 결제하기 전에 확인하는 용도입니다.)"""
import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as cfg, lookup_core as lc
print("VWORLD_KEY 설정:", "예" if cfg.VWORLD_KEY else "아니오 (.env 확인)", "| 도메인:", cfg.VWORLD_DOMAIN or "(없음)")
ok = True
for name, fn in (
    ("V-World 주소 -> PNU", lambda: lc.vworld_pnu("마포구 노고산동 57-1")),
    ("도시공간포털 필지 레이어", lambda: lc.portal_query(1, {"where": "PNU='1144011000100570001'", "outFields": "PNU", "returnGeometry": "false", "f": "json"})),
):
    t = time.time()
    try:
        r = fn(); print("[OK]  %-22s %dms" % (name, (time.time() - t) * 1000), str(r)[:80])
    except Exception as e:
        ok = False; print("[실패] %-22s %s" % (name, e))
print("\n결과:", "모두 정상. 이 곳에서 서버를 운영할 수 있습니다." if ok else "닿지 않는 서비스가 있습니다. 위 메시지를 알려주세요. (403이면 접속 차단, 키/도메인 불일치도 같은 증상)")
