# InsightFlow AI

Transforming business data into intelligent decisions.

InsightFlow AI is an analytics workspace for retail transactions. Upload a CSV or Excel file, or load the generated sample, then review a quality score and create a cleaned copy. Dashboards, customer and product views, models, the assistant, and reports all calculate from that cleaned copy. The uploaded file is left unchanged.

## What it calculates

- Quality score: `100 × (0.30 completeness + 0.20 uniqueness + 0.30 validity + 0.20 consistency)`. Returns and cancellations stay valid. Outliers are reported and are not deleted.
- Revenue is quantity × unit price, including returns and cancellations. Invalid rows stay in the cleaned copy and are excluded from KPIs.
- Sales, customer, and product views honor the workspace, dataset, date range, and filters.
- Segments use scaled recency, frequency, and monetary value. K is chosen by silhouette.
- Churn is inferred from a configurable inactivity window. Features stop at the cutoff. Customers whose first purchase is after the cutoff are counted and not scored. The list is a rank, not a calibrated probability.
- Forecasts use a chronological holdout, a seasonal naive baseline, and Holt-Winters or Holt smoothing when it fits. A horizon is omitted when the history is too short, and the result is marked unreliable when the history or holdout error does not support it.
- The assistant turns a question into a fixed analytical plan and runs a read-only query, or quotes a saved model. It does not invent a number. With `INSIGHTFLOW_LLM_API_KEY` set, the model may choose the plan. The number still comes from the query.
- Reports export the same calculations to PDF, Excel, and CSV.

The generated sample is not the UCI Online Retail II dataset. Data Management can download and profile that workbook, or you can fetch it with `python scripts/download_uci.py`. The file stays in `data/uci` and is not committed. Cleaning, model training, and that import run in the API process and the screen polls until they finish. Set `JOBS_INLINE=true` to finish them before the response, which is what the tests do.

Citation: Chen, Daqing. Online Retail II. UCI Machine Learning Repository, 2019. https://archive.ics.uci.edu/dataset/502/online+retail+ii

## Prerequisites

- Python 3.11
- Node.js 20
- Docker, with the Compose plugin, for the supported PostgreSQL and Redis stack
- On macOS, the OpenMP runtime (`libomp`) so XGBoost can load. `brew install libomp` is the usual install. Linux CI installs `libgomp1`.

On this machine Python 3.11 is at `~/.local/python/bin/python3.11` and Node.js 20 is at `~/.local/node/bin`. Add both directories to `PATH` before running commands outside the scripts.

## Run on this machine without Docker

Docker is not installed here, and Compose has not been booted. The dev script uses a SQLite file and skips Redis when `DATABASE_URL` is unset. PostgreSQL and Redis through Compose are the supported stack.

```bash
cp .env.example .env
# Put a unique value of at least 32 characters in JWT_SECRET.

./scripts/dev-backend.sh
./scripts/dev-frontend.sh
```

Open http://127.0.0.1:5173. The API is at http://127.0.0.1:8000 and the Vite dev server proxies `/api` to it.

## Run with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

The web app is at http://localhost:8080. The API is at http://localhost:8000. Compose overrides the database host to the `postgres` service and points Redis at the `redis` service. The Compose default `JWT_SECRET` is for a private local demo. Replace it before any shared deployment. This path has not been executed on this machine.

## Tests

```bash
cd backend && .venv/bin/pytest
cd frontend && npm test
cd frontend && npm run lint && npm run build
cd frontend && npx playwright test
```

Backend tests use an isolated SQLite database and cover cleaning, revenue, authorization, churn, forecasting, the assistant's SQL guard, and a PDF report. `tests/test_migrations.py` applies the Alembic revisions to a temporary SQLite file. GitHub Actions runs the backend suite, the frontend suite and build, and the Playwright path.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health` | Process is up |
| GET | `/api/v1/health/ready` | Database, and Redis when `REDIS_URL` is set |
| POST | `/api/v1/auth/register` | Create an account and its workspace |
| POST | `/api/v1/auth/login` | Issue access and refresh tokens |
| POST | `/api/v1/auth/refresh` | Rotate the refresh token |
| POST | `/api/v1/auth/logout` | Revoke the refresh token |
| GET | `/api/v1/auth/me` | Current user |
| GET | `/api/v1/workspaces` | Workspaces the caller belongs to |
| POST | `/api/v1/workspaces/{id}/datasets` | Upload a CSV or XLSX file |
| GET | `/api/v1/workspaces/{id}/members` | Members and pending invitations |
| POST | `/api/v1/workspaces/{id}/members` | Invite an admin, analyst, or viewer |
| POST | `/api/v1/workspaces/{id}/datasets/sample` | Load the generated sample |
| POST | `/api/v1/workspaces/{id}/datasets/uci` | Profile Online Retail II in the background |
| GET | `/api/v1/jobs/{id}` | Poll a cleaning, training, or import job |
| POST | `/api/v1/datasets/{id}/prepare` | Create a cleaned version |
| GET | `/api/v1/datasets/{id}/analytics/sales` | KPIs and charts |
| POST | `/api/v1/datasets/{id}/models/{type}` | Train segments, churn, or a forecast |
| POST | `/api/v1/assistant/messages` | Ask a grounded question |
| POST | `/api/v1/reports` | Build a report |
| GET | `/api/v1/reports/{id}/download` | PDF, Excel, or CSV |

Errors use `{ "error": { "code", "message", "details" } }`. Access tokens expire after 15 minutes. Refresh tokens expire after 7 days, are stored as SHA-256 hashes, and are rotated on use. A viewer can read a workspace and cannot upload, train, or generate reports. Owners and admins invite members from Settings. A pending invite is accepted when that email registers. A non-member receives 404.

Login and registration limits use Redis when `REDIS_URL` is set. If Redis does not answer, the limit is counted in the current process.

Passwords are hashed with Argon2id. `JWT_SECRET` must be at least 32 characters and is read from the environment. The dev script supplies a local default only when the variable is absent. The application itself has no default secret.

## Layout

```text
backend/app/api/routes     HTTP
backend/app/services       Business rules and query execution
backend/app/ml             Segmentation, churn, and forecasting
backend/app/models         SQLAlchemy models
backend/alembic            Migrations
frontend/src/pages         Screens
frontend/src/components    Shell, charts, and UI primitives
docs/architecture.md       Data model and calculation decisions
```

## Resolved versions

Backend versions are pinned in `backend/requirements.lock`. The direct stack includes FastAPI 0.162.0, SQLAlchemy 2.1.8, Alembic 1.20.1, pandas 3.1.1, scikit-learn 1.9.1, XGBoost 3.2.0, statsmodels 0.15.0, and reportlab 5.1.0.

Frontend: React 18.3.1, Vite 6.4.5, TypeScript 5.9.3, Tailwind CSS 3.4.19, TanStack Query 5.106.0, React Router 7.18.5, Recharts, and Vitest 3.2.7.
