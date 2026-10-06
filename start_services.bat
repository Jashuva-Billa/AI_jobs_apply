@echo off
title Antigravity AI - Agentic Job Platform Launcher
cls
color 0B
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

echo [3/4] Starting Job Platform MCP Server on http://localhost:8001 (16 Tools)...
start "Job Platform MCP Server (Port 8001)" cmd /k "cd /d %~dp0 && python mcp-servers/job-platform/server.py"

timeout /t 2 /nobreak >nul

echo [4/4] Starting Ngrok HTTPS Tunnel for ChatGPT MCP (Port 8001)...
start "Ngrok Tunnel (Port 8001)" cmd /k "cd /d %~dp0 && ngrok http 8001"

echo.
echo ==============================================================================
echo  All 4 services successfully launched in separate windows!
echo.
echo  • FastAPI Backend API:   http://localhost:8000/docs
echo  • Streamlit Dashboard:   http://localhost:8501
echo  • Local MCP Server:      http://localhost:8001/health
echo  • MCP SSE Transport:     http://localhost:8001/sse
echo  • ChatGPT MCP URL:       Check the Ngrok window for: https://*.ngrok-free.dev/sse
echo.
echo  Registered MCP Tools:   16 Tools (Candidate, Search, Match, HITL, Status, Outreach)
echo ==============================================================================
echo.
pause
