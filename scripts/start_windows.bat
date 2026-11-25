@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt || exit /b 1
if not exist "frontend\dist\index.html" (
    pushd frontend
    call npm ci --no-audit --no-fund || exit /b 1
    call npm run build || exit /b 1
    popd
)
echo Open http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

