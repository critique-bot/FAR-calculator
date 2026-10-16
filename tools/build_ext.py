"""추출 결과(extract/*.json) -> data/ext_items.json (구역 이름 키). 사용: python tools/build_ext.py <extract 폴더>"""
import json, glob, re, sys, os
EXT_DIR = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
cat = json.load(open(os.path.join(HERE, "..", "..", "data", "catalog.json"), encoding="utf-8"))
def S(x):
    if x is None: return ""
    if isinstance(x, str): return x
    if isinstance(x, (int, float)): return str(x)
    return json.dumps(x, ensure_ascii=False)
E = {}
for p in sorted(glob.glob(os.path.join(EXT_DIR, "*.json"))):
    d = json.load(open(p, encoding="utf-8")); sn = d["sn"]
    name = (cat.get(sn) or {}).get("구역") or d["zone"]
    secs = []
    for s in d.get("sections", []):
        items = []
        for i in s.get("items", []):
            co = i.get("coeff"); co = co if isinstance(co, dict) else {}
            items.append({"n": S(i.get("name")), "c": S(i.get("category")), "k": S(i.get("kind")), "f": S(i.get("formula"))[:200], "co": co, "m": S(i.get("max")), "cd": S(i.get("condition"))[:240]})
        caps = [S(c.get("text") if isinstance(c, dict) else c) for c in (s.get("caps") or [])]
        b, pp = s.get("base_far"), s.get("allowed_far")
        secs.append({"a": S(s.get("applies_to")), "b": b if isinstance(b, (int, float)) else None, "p": pp if isinstance(pp, (int, float)) else None, "u": S(s.get("upper_far")), "items": items, "caps": caps})
    docs = [re.sub(r"\.pdf(\.txt)?", ".pdf", S(x), flags=re.I) for x in d.get("docs_used", [])]
    E[name] = {"docs": docs, "sections": secs, "un": [S(u) for u in d.get("unresolved", [])]}
out = os.path.join(HERE, "..", "data", "ext_items.json")
open(out, "w", encoding="utf-8").write(json.dumps(E, ensure_ascii=False, separators=(",", ":")))
print(len(E), "zones,", sum(len(s["items"]) for e in E.values() for s in e["sections"]), "items")
