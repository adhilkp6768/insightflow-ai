# Architecture

InsightFlow AI separates the browser, the API, domain services, and the data plane.

The browser renders a workspace shell and calls `/api/v1`. FastAPI validates input, enforces membership, and returns a stable error shape. Services own registration, tokens, and workspace lookup. Later phases add ingestion, analytics, models, the assistant, and reports behind the same boundary. The browser does not calculate business metrics.

## Phase 1 data

PostgreSQL is the system of record. Identifiers are UUIDs.

- `users` stores the email, Argon2id password hash, and active flag.
- `workspaces` belongs to an owner.
- `workspace_memberships` grants `owner`, `admin`, `analyst`, or `viewer`. The pair of workspace and user is unique.
- `refresh_tokens` stores a SHA-256 hash, expiry, and revocation time.
- `activity_logs` records auth actions. The metadata column keeps the client address. It does not store passwords, tokens, or dataset rows.

A non-member requesting a workspace receives 404. The list endpoint returns only the caller's memberships.

Redis is checked by `/api/v1/health/ready` when `REDIS_URL` is set. An empty URL skips that check so local SQLite development can run. Compose always sets the URL. The in-process auth rate limit is per API process. A shared Redis limiter is a later hardening step.

## Decisions already fixed for later phases

Raw uploads stay immutable. Cleaning writes a new dataset version and a queryable PostgreSQL table. Analytics run only after columns are mapped to roles: invoice, invoice date, stock code, description, quantity, unit price, customer, and country. A missing role returns an explanation.

Revenue is quantity times price. Cancellations and negative quantities stay in the data because they change revenue. Rows with an unparseable date, a missing price, or an empty invoice are excluded from KPIs. Rows without a customer stay in sales analytics and are excluded from customer models.

The quality score is `100 × (0.30 completeness + 0.20 uniqueness + 0.30 validity + 0.20 consistency)`. Completeness weights invoice date, quantity, price, and customer more heavily. Returns are valid rows. Outliers are reported and kept.

Churn on the retail dataset is inferred. A customer is churned when they purchased before a cutoff and then had no purchase for a configurable window, default 90 days. Features are computed only on history before that window. The model run stores the label kind and the window length.

The assistant receives a structured analytical plan from the model provider, compiles that plan to parameterized `SELECT` SQL, and runs it as a read-only role with a timeout and a row cap. Answers are marked as data-backed, a prediction, or an interpretation. Numbers in an answer come from the query result.

Forecasting uses a chronological split, a seasonal naive baseline, and a statsmodels model when the series is long enough. Horizons are 30, 60, and 90 days. Metrics are MAE, RMSE, and MAPE on non-zero actuals. Segmentation is K-Means on scaled recency, frequency, and monetary features, with `k` chosen by silhouette score from 2 to 8.

The demonstration dataset is UCI Online Retail II. A later setup script downloads it. The file stays out of git. The same upload path accepts a user's CSV or Excel file after column roles are mapped.

Background jobs will use `processing_jobs` in PostgreSQL as the status record and Redis as the queue. Airflow is a scheduled-pipeline extension after the core product works.
