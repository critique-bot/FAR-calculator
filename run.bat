@echo off
cd /d %~dp0
pip install -r requirements.txt
echo.
echo  브라우저에서 http://localhost:8000 을 여세요
python -m uvicorn app:app --port 8000
