"""환경변수 설정. 키는 코드에 넣지 않고 서버 환경변수/.env 로만 받는다."""
import os

def _load_dotenv(path=".env"):
    if not os.path.exists(path): return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
_load_dotenv()

PORTAL_PROXY = os.environ.get("PORTAL_PROXY", "https://urban.seoul.go.kr/proxy/proxy.jsp?")
PORTAL_BASE = os.environ.get("PORTAL_BASE", "http://98.33.2.225:6080/arcgis/rest/services/UPIS/20200526_WFS/MapServer/")
CACHE_DIR = os.environ.get("CACHE_DIR", "./cache")
CACHE_TTL_H = float(os.environ.get("CACHE_TTL_HOURS", "24"))
ALLOWED_ORIGINS = [x.strip() for x in os.environ.get("ALLOWED_ORIGINS", "").split(",") if x.strip()]
RATE_PER_MIN = int(os.environ.get("RATE_PER_MIN", "30"))     # IP당 분당 조회 수 (포털 보호)
MAX_PARCELS = int(os.environ.get("MAX_PARCELS", "20"))
DATA_GO_KEY = os.environ.get("DATA_GO_KEY", "")                 # 공공데이터포털 법정동코드 API 인증키 (코드표 자동 갱신용)
DONG_REFRESH_DAYS = float(os.environ.get("DONG_REFRESH_DAYS", "7"))
