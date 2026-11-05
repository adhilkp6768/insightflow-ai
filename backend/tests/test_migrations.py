from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings
from app.core.database import reset_engine


def test_auth_migration_upgrades_sqlite(tmp_path, monkeypatch):
    database_path = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    get_settings.cache_clear()
    reset_engine()

    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    assert {
        "users",
        "workspaces",
        "workspace_memberships",
        "refresh_tokens",
        "activity_logs",
        "datasets",
        "dataset_versions",
        "dataset_columns",
        "dataset_profiles",
        "processing_jobs",
        "model_runs",
        "reports",
        "assistant_conversations",
        "assistant_messages",
        "workspace_invites",
        "alembic_version",
    } <= tables
    job_columns = {column["name"] for column in inspect(engine).get_columns("processing_jobs")}
    assert "payload" in job_columns
    get_settings.cache_clear()
    reset_engine()
