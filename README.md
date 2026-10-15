# 지구단위계획 용적률 서버

지번 입력 → 구역·용적률 계획 자동 조회 → 인센티브·기부채납 반영 계산. FastAPI 서버 + 화면 한 벌.


## 0. 무료로 먼저 테스트 (Streamlit Community Cloud)
1. GitHub 에 새 저장소를 만들고 이 폴더의 파일을 올립니다. `.env`, 키가 든 파일은 올리지 않습니다 (`.gitignore` 가 막아 줍니다).
2. https://share.streamlit.io 에서 GitHub 로 로그인 → New app → 저장소, 브랜치 `main`, 파일 `streamlit_app.py` 선택.
3. 배포 전 Advanced settings > Secrets 에 아래를 붙여넣습니다.
   ```
   VWORLD_KEY = "발급받은 키"
   VWORLD_DOMAIN = "www.test.com"
   ```
4. 배포되면 화면 위쪽 "접속 진단"을 열어 **진단 실행**. 두 줄이 모두 정상이면 그대로 테스트할 수 있습니다.
   실패하면 이 호스팅에서는 포털이 막힌 것입니다 → 아래 1번(내 PC 실행)으로 확인하세요.
- 저장소를 공개로 두면 코드가 보입니다. 키는 Secrets 에만 있어 노출되지 않습니다.
- 무료 앱은 한동안 접속이 없으면 잠들고, 다시 열 때 몇 초 걸립니다.

## 1. 내 PC에서 먼저 실행 (포털 접속 확인)
1. `.env.example` 을 `.env` 로 복사하고 `VWORLD_KEY` 를 채웁니다.
2. `python check_connection.py` — 두 줄 모두 `[OK]` 여야 합니다.
3. `pip install -r requirements.txt` 후 `python -m uvicorn app:app --port 8000` (Windows는 `run.bat`)
4. 브라우저에서 `http://localhost:8000` (Streamlit 화면은 `python -m streamlit run streamlit_app.py`)

## 2. 서버에 올리기
- 올릴 서버에서 **먼저** `python check_connection.py` 를 실행해 포털에 닿는지 확인합니다. 닿지 않으면 그 호스팅은 쓸 수 없습니다(국내 IDC/VPS 권장).
- Docker: `docker build -t far .` → `docker run -d -p 8000:8000 --env-file .env -v far-data:/data far`
- 앞단에 Nginx/Caddy 로 도메인 + HTTPS 연결 (Caddy는 도메인만 지정하면 인증서 자동).
- 도메인을 사면 V-World 에서 키를 그 도메인으로 다시 발급받아 `.env` 의 `VWORLD_KEY`, `VWORLD_DOMAIN` 을 바꿉니다.
- 배포 후 `https://도메인/api/diagnose` 에서 `all_ok: true` 확인.

## API
| 주소 | 설명 |
|---|---|
| `POST /api/lookup` `{"text":"마포구 노고산동 57-1, 57-2, 57-3"}` | 조회. 단일/묶음. `raw`(원자료) + `site`(화면용 요약, 포털 기준값, 등록 구역) |
| `POST /api/calc` | 계산. 등록 구역은 `registry_key` + 항목 on/off, 그 외는 `items`(fixed/rate)를 직접 보냄 |
| `GET /api/registry`, `/api/registry/full` | 인센티브표가 등록된 구역 |
| `GET /api/diagnose` | V-World·포털 접속 진단 |
| `GET /api/health` | 상태 |

문서: `/docs` (자동 생성)

## 데이터 신뢰 수준
- 등록 구역(`data/registry.json`): 고시 문서에서 직접 옮긴 인센티브표. 현재 **마포2 2-4지구**만.
- 그 외 구역: 포털 값을 불러오며 "포털값, 고시 확인 필요"로 표시. 인센티브표는 사용자가 입력.
- 조회 결과는 `CACHE_TTL_HOURS` 동안 저장되어 같은 지번은 포털을 다시 부르지 않습니다. IP당 분당 `RATE_PER_MIN` 건 제한.
- 새 구역 등록: `data/registry.json` 에 항목 추가(마포2 항목을 본보기로). 출처 파일명 `refs` 를 반드시 적습니다.

## 테스트
`pip install pytest httpx` 후 `python -m pytest tests -q` (외부 접속 없이 19건)
`python tests/run_fake_server.py` — 가짜 포털로 화면 확인용 서버(포트 8765)
