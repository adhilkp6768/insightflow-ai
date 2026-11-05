.PHONY: test backend frontend

backend:
	./scripts/dev-backend.sh

frontend:
	./scripts/dev-frontend.sh

test:
	cd backend && .venv/bin/pytest
	cd frontend && npm test
