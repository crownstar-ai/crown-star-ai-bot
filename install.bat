@echo off
echo Installing CrownStar...
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
pip install aiosqlite
copy .env.example .env
echo.
echo ==========================================
echo Please edit .env and add your DEEPSEEK_API_KEY
echo Then run: uvicorn app.main:app --host 0.0.0.0 --port 8000
echo ==========================================
pause
