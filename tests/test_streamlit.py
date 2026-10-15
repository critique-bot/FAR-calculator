import os, sys, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..")); sys.path.insert(0, os.path.dirname(__file__))
os.environ["CACHE_DIR"] = tempfile.mkdtemp()
import pytest
from streamlit.testing.v1 import AppTest
import test_all as t, lookup_core as lc
from embed import build_html

APP = os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")

def run(text, monkeypatch, tmp_path):
    import settings; monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    f = t.Fake(); monkeypatch.setattr(lc, "portal_query", f.portal)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].set_value(text); at.button[0].click().run()
    return at

def test_lookup_ok(monkeypatch, tmp_path):
    at = run("마포구 노고산동 57-1, 57-2, 57-3", monkeypatch, tmp_path)
    assert not at.exception, at.exception
    assert any("조회했습니다" in c.value for c in at.caption)

def test_not_found(monkeypatch, tmp_path):
    at = run("마포구 없는동 1", monkeypatch, tmp_path)
    assert not at.exception and "법정동 목록에 없는 동" in str([c.value for c in at.caption])

@pytest.mark.parametrize("name", ["노고산동", "군자동", "종로1가", "불광동", "역삼동", "성수동1가", "잠실동", "여의도동"])
def test_embed_builds_for_all_samples(name):
    raw = t.sample(name); h = build_html(raw)
    assert "load([" in h and "REG=" in h and raw["PNU"] in h and "</script></script>" not in h
    assert "  load(DEMO);\n})();" not in h          # 시작 시 예시 데이터를 불러오지 않음
