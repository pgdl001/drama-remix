@echo off
echo ========================================
echo  Drama Remix Tool - Full Start
echo ========================================
echo.
echo Starting backend and frontend...
echo.

start "Drama-Remix-Backend" cmd /k "%~dp0start-backend.bat"
timeout /t 3 >nul
start "Drama-Remix-Frontend" cmd /k "%~dp0start-frontend.bat"

echo.
echo Backend: http://127.0.0.1:8001 (API docs: http://127.0.0.1:8001/docs)
echo Frontend: http://localhost:5173
echo.
echo Both servers started in separate windows.
pause
