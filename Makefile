.PHONY: help dev dev-backend dev-frontend test test-backend test-frontend lint lint-frontend docker-up docker-down clean

help:
	@echo "HopTrace — Available Commands:"
	@echo "  make dev            Run both backend and frontend development servers"
	@echo "  make dev-backend    Run FastAPI development server on port 8000"
	@echo "  make dev-frontend   Run Vite frontend development server on port 5173"
	@echo "  make test           Run full test suite (backend pytest + frontend node test)"
	@echo "  make test-backend   Run pytest test suite (202+ tests)"
	@echo "  make test-frontend  Run Node.js frontend tests (42 tests)"
	@echo "  make lint           Run frontend ESLint and check syntax"
	@echo "  make docker-up      Build and run via Docker Compose"
	@echo "  make docker-down    Stop Docker Compose containers"
	@echo "  make clean          Clean temporary files and test caches"

dev:
	@echo "Starting backend and frontend in parallel..."
	@python -c "import subprocess, sys; b = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000', '--app-dir', 'backend']); f = subprocess.Popen(['npm', 'run', 'dev'], cwd='frontend', shell=True); b.wait(); f.wait()"

dev-backend:
	python -m uvicorn app.main:app --reload --port 8000 --app-dir backend

dev-frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	python -m pytest tests -v

test-frontend:
	node --test frontend/src/components/VillageMap/*.test.js frontend/src/components/NetworkView/viewPref.test.js

lint: lint-frontend

lint-frontend:
	cd frontend && npm run lint

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	python -c "import shutil, os, glob; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True) + glob.glob('.pytest_cache')]"
