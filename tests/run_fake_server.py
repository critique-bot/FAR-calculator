"""외부 서비스를 가짜로 바꾼 개발용 서버 (화면 테스트용). python tests/run_fake_server.py"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..")); sys.path.insert(0, os.path.dirname(__file__))
os.environ["CACHE_DIR"] = tempfile.mkdtemp(); os.environ["VWORLD_KEY"] = "TEST"
import test_all as t, lookup_core as lc, uvicorn, app
f = t.Fake(); lc.vworld_pnu = f.pnu; lc.portal_query = f.portal
uvicorn.run(app.app, host="127.0.0.1", port=int(os.environ.get("PORT", "8765")), log_level="warning")
