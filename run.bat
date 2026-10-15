@echo off
cd /d %~dp0
if not exist .env copy .env.example .env
pip install -r requirements.txt
echo.
echo  .env 에 VWORLD_KEY 를 넣었다면 브라우저에서 http://localhost:8000 을 여세요
python -m uvicorn app:app --port 8000
