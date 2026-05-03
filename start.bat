@echo off
echo Starting Viral Video Chopper...
echo.

:: Free ports if still occupied
echo Clearing ports 8000 and 5173...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1

timeout /t 1 /nobreak >nul

:: Backend
echo [1/2] Starting backend on http://localhost:8000
start "Backend" cmd /k "cd /d %~dp0backend && set PATH=%PATH%;%~dp0backend\venv\Scripts;C:\Users\prati\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin && venv\Scripts\uvicorn.exe main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

:: Frontend
echo [2/2] Starting frontend on http://localhost:5173
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- --port 5173"

echo.
echo Both servers started.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   Health:   http://localhost:8000/health
