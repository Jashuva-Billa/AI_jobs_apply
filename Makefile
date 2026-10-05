.PHONY: install dev-backend dev-streamlit test docker-up docker-down

install:
	pip install -r backend/requirements.txt

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-streamlit:
	streamlit run streamlit_app.py --server.port 8501

dev:
	@echo "To run both backend and streamlit copilot concurrently:"
	@echo "1. In terminal 1: make dev-backend"
	@echo "2. In terminal 2: make dev-streamlit"

test:
	cd backend && pytest tests/ -v

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

