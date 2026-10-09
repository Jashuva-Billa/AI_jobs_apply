@echo off
title Antigravity AI - Stop All Services
cls
color 0C

echo ==========================================
echo   Antigravity AI - Stopping All Services
echo ==========================================
echo.

echo [1/5] Stopping FastAPI on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

echo [2/5] Stopping Streamlit on port 8501...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

echo [3/5] Stopping Job Platform MCP Server on port 8001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

echo [4/5] Stopping Ngrok...
taskkill /F /T /IM ngrok.exe >nul 2>&1

echo [5/5] Closing only the AI Job Platform service terminals...
taskkill /F /T /FI "WINDOWTITLE eq FastAPI Backend (Port 8000)*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Streamlit Dashboard (Port 8501)*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Job Platform MCP Server (Port 8001)*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Ngrok Tunnel (Port 8001)*" >nul 2>&1

echo.
echo Verifying service ports...

set "PORTS_CLEAR=YES"

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8000 is still in use.
    set "PORTS_CLEAR=NO"
) else (
    echo [OK] Port 8000 is free.
)

netstat -ano | findstr ":8001" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8001 is still in use.
    set "PORTS_CLEAR=NO"
) else (
    echo [OK] Port 8001 is free.
)

netstat -ano | findstr ":8501" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8501 is still in use.
    set "PORTS_CLEAR=NO"
) else (
    echo [OK] Port 8501 is free.
)

echo.
if "%PORTS_CLEAR%"=="YES" (
    echo ==========================================
    echo   ALL AI JOB PLATFORM SERVICES STOPPED
    echo ==========================================
) else (
    echo ==========================================
    echo   WARNING: SOME SERVICES ARE STILL RUNNING
    echo ==========================================
)

echo.
echo Only the FastAPI, Streamlit, MCP and Ngrok
echo service terminals are targeted for closing.
echo Other CMD/PowerShell/VS Code terminals are untouched.
echo.
pause
