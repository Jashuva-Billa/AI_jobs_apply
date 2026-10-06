@echo off
title Antigravity AI - Job Platform Launcher
echo ==============================================================================
echo           Starting Antigravity AI - Agentic Job Platform Services
echo ==============================================================================
echo.

echo [1/4] Starting FastAPI Backend on http://localhost:8000...
start "FastAPI Backend (Port 8000)" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 2 /nobreak >nul

echo [2/4] Starting Streamlit UI on http://localhost:8501...
start "Streamlit Dashboard (Port 8501)" cmd /k "cd /d %~dp0 && streamlit run streamlit_app.py --server.port 8501"

timeout /t 2 /nobreak >nul

echo [3/4] Starting Job Platform MCP Server on http://localhost:8001...
start "MCP Server (Port 8001)" cmd /k "cd /d %~dp0 && python mcp-servers/job-platform/server.py"

timeout /t 2 /nobreak >nul

echo [4/4] Starting Ngrok HTTPS Tunnel for ChatGPT MCP (Port 8001)...
start "Ngrok Tunnel (Port 8001)" cmd /k "cd /d %~dp0 && ngrok http 8001"

echo.
echo ==============================================================================
echo  All 4 services launched in separate windows!
echo.
echo  • FastAPI Backend:       http://localhost:8000/docs
echo  • Streamlit Dashboard:   http://localhost:8501
echo  • Local MCP Server:      http://localhost:8001/sse
echo  • ChatGPT MCP URL:       Check the Ngrok window for your https://*.ngrok-free.dev/sse
echo ==============================================================================
echo.
pause
