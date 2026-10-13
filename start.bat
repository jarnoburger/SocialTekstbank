@echo off
cd /d "%~dp0"
python -c "import flask, PIL, requests" 2>nul || python -m pip install -r requirements.txt
python app.py
pause
