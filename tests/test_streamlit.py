import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..")); sys.path.insert(0, os.path.dirname(__file__))
os.environ["CACHE_DIR"] = tempfile.mkdtemp(); os.environ["VWORLD_KEY"] = "TEST"
import pytest
from streamlit.testing.v1 import AppTest
import test_all as t, lookup_core as lc

def run(text, monkeypatch, tmp_path):
    import settings; monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    f = t.Fake(); monkeypatch.setattr(lc, "vworld_pnu", f.pnu); monkeypatch.setattr(lc, "portal_query", f.portal)
    at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py"), default_timeout=30).run()
    at.text_input[0].set_value(text); at.button[0].click().run()
    return at

def test_mapo2(monkeypatch, tmp_path):
    at = run("마포구 노고산동 57-1, 57-2, 57-3", monkeypatch, tmp_path)
    assert not at.exception, at.exception
    m = {x.label: x.value for x in at.metric}
    assert m["허용용적률 (인센티브 반영)"] == "800.0 %" and m["상한용적률"] == "1,600 % 이하"
    at.number_input(key=[k for k in [n.key for n in at.number_input] if k.endswith("land")][0]).set_value(30.0).run()
    assert not at.exception
    assert "비대상" not in str([x.value for x in at.dataframe][0])

def test_not_found(monkeypatch, tmp_path):
    at = run("마포구 없는동 1", monkeypatch, tmp_path)
    assert not at.exception and "주소를 찾지 못했습니다" in str([c.value for c in at.caption])

@pytest.mark.parametrize("name", ["군자동", "종로1가", "불광동", "역삼동", "성수동1가"])
def test_portal_only_sites(monkeypatch, tmp_path, name):
    s = t.sample(name); monkeypatch.setattr(lc, "lookup_text", lambda x: s)
    at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py"), default_timeout=30).run()
    at.text_input[0].set_value("x"); at.button[0].click().run()
    assert not at.exception, at.exception
    if name == "군자동":
        m = {x.label: x.value for x in at.metric}
        assert m["기준용적률"] == "300 % 이하" and m["허용용적률"] == "630 % 이하" and m["허용용적률 (인센티브 반영)"] == "300.0 %" and m["상한용적률"] == "800 % 이하"
