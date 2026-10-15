"""조회 결과를 계산 화면(static/index.html)에 끼워 넣은 HTML 을 만든다. Streamlit 에서 그대로 보여 준다."""
import json, os
from siteview import REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))

def _js(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

def build_html(raw):
    html = open(os.path.join(HERE, "static", "index.html"), encoding="utf-8").read()
    html = html.replace("api('/api/health').then(", "Promise.reject().then(", 1)          # 서버 API 연결은 쓰지 않음
    tail = "  load(DEMO);\n})();"
    assert tail in html, "static/index.html 의 시작 코드를 찾지 못했습니다"
    html = html.replace(tail, "  REG=%s;\n  load([%s]);\n  $('loadMsg').textContent='';\n})();" % (_js(REGISTRY), _js(raw)), 1)
    style = "<style>section.card:has(#addrBox){display:none}body{margin:0}</style>"
    return html.replace("</head>", style + "</head>", 1) if "</head>" in html else style + html
