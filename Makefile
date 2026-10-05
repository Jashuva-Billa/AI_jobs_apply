.PHONY: install dev-backend dev-frontend dev test lint format docker-up docker-down

install:
	pip install -r backend/requirements.txt
	cd frontend && npm install

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-streamlit:
	streamlit run streamlit_app.py --server.port 8501

dev-frontend:
	cd frontend && npm run dev

dev:
	@echo "To run both backend and frontend concurrently:"
	@echo "1. In terminal 1: make dev-backend"
	@echo "2. In terminal 2: make dev-frontend"

test:
	cd backend && pytest tests/test_all.py -v

lint:
	cd frontend && npm run build

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
