"""Manage service database migrations and metadata operations.

Examples:
    uv run python scripts/migration.py list
    uv run python scripts/migration.py init --service model-registry
    uv run python scripts/migration.py revision --service model-registry -m "add model metrics" --autogenerate
    uv run python scripts/migration.py upgrade --service model-registry
    uv run python scripts/migration.py reset --service media --yes
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


ROOT = Path(__file__).resolve().parents[1]
SITE_PACKAGES = ROOT / ".venv" / "Lib" / "site-packages"


@dataclass(frozen=True)
class Service:
    name: str
    path: Path
    config_module: str
    database_module: str
    metadata_expr: str | None
    model_imports: tuple[str, ...] = field(default_factory=tuple)

    @property
    def migrations_path(self) -> Path:
        return self.path / "migrations"

    @property
    def versions_path(self) -> Path:
        return self.migrations_path / "versions"

    @property
    def alembic_ini(self) -> Path:
        return self.path / "alembic.ini"


SERVICES = {
    "auth": Service(
        name="auth",
        path=ROOT / "services" / "auth-service",
        config_module="app.config",
        database_module="agriculture_ai.types.models",
        metadata_expr="Base.metadata",
        model_imports=("app.models.user",),
    ),
    "ai": Service(
        name="ai",
        path=ROOT / "services" / "ai-service",
        config_module="app.config",
        database_module="app.core.database",
        metadata_expr="Base.metadata",
    ),
    "media": Service(
        name="media",
        path=ROOT / "services" / "media-service",
        config_module="app.config",
        database_module="app.database",
        metadata_expr="Base.metadata",
    ),
    "model-registry": Service(
        name="model-registry",
        path=ROOT / "services" / "model-registry",
        config_module="app.config",
        database_module="app.database",
        metadata_expr="Base.metadata",
    ),
    "sync": Service(
        name="sync",
        path=ROOT / "services" / "sync-service",
        config_module="app.config",
        database_module="app.database",
        metadata_expr="Base.metadata",
    ),
    "analytics": Service(
        name="analytics",
        path=ROOT / "services" / "analytics-service",
        config_module="app.config",
        database_module="app.core.database",
        metadata_expr=None,
    ),
}


def load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def service_choices() -> list[str]:
    return sorted(SERVICES)


def selected_services(name: str) -> list[Service]:
    if name == "all":
        return [SERVICES[key] for key in service_choices()]
    return [SERVICES[name]]


def configure_imports(service: Service) -> None:
    paths = [
        service.path,
        ROOT / "shared" / "types",
        ROOT / "shared" / "inference-sdk",
        SITE_PACKAGES,
    ]
    values = [str(path) for path in paths]
    sys.path[:] = values + [path for path in sys.path if path not in values]


def clear_app_modules() -> None:
    for name in list(sys.modules):
        if (
            name == "app"
            or name.startswith("app.")
            or name == "agriculture_ai"
            or name.startswith("agriculture_ai.")
        ):
            sys.modules.pop(name, None)


def load_service_env(service: Service, *, docker: bool = False) -> None:
    env = load_dotenv(ROOT / ".env")
    env.update(load_dotenv(service.path / ".env"))

    if docker:
        db_password = env.get("DB_PASSWORD", "secure_password")
        redis_password = env.get("REDIS_PASSWORD", "redis_pass")
        env["DATABASE_URL"] = f"postgresql://agri_user:{db_password}@postgres:5432/agriculture_ai"
        env["REDIS_URL"] = f"redis://:{redis_password}@redis:6379/0"

    os.environ.update(env)


def get_database_url(service: Service) -> str:
    configure_imports(service)
    config = importlib.import_module(service.config_module)
    return config.settings.DATABASE_URL


def get_metadata(service: Service):
    if not service.metadata_expr:
        raise RuntimeError(f"{service.name} does not expose SQLAlchemy metadata")

    configure_imports(service)
    for module_name in service.model_imports:
        importlib.import_module(module_name)

    database = importlib.import_module(service.database_module)
    current = database
    for part in service.metadata_expr.split("."):
        current = getattr(current, part)
    return current


def async_database_url(url: str) -> str:
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def alembic_env_py() -> str:
    return '''"""Alembic environment generated by scripts/migration.py."""

from __future__ import annotations

import importlib
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

SERVICE_PATH = Path(__file__).resolve().parents[1]
ROOT = SERVICE_PATH.parents[1]
for path in (
    SERVICE_PATH,
    ROOT / "shared" / "types",
    ROOT / "shared" / "inference-sdk",
):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT / ".env")
load_dotenv(SERVICE_PATH / ".env")

config_module = config.get_main_option("app_config_module")
database_module = config.get_main_option("app_database_module")
metadata_expr = config.get_main_option("app_metadata")
model_imports = [
    name.strip()
    for name in config.get_main_option("app_model_imports", "").split(",")
    if name.strip()
]

for module_name in model_imports:
    importlib.import_module(module_name)

settings = importlib.import_module(config_module).settings
database = importlib.import_module(database_module)
target_metadata = database
for part in metadata_expr.split("."):
    target_metadata = getattr(target_metadata, part)

target_table_names = {table.name for table in target_metadata.tables.values()}


def include_name(name, type_, parent_names):
    if type_ == "table":
        return name in target_table_names
    return True


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "table":
        return name in target_table_names
    return True


config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("+asyncpg", ""))


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_name=include_name,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
            include_object=include_object,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''


def alembic_ini(service: Service) -> str:
    model_imports = ",".join(service.model_imports)
    return f"""[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = driver://user:pass@localhost/dbname
app_config_module = {service.config_module}
app_database_module = {service.database_module}
app_metadata = {service.metadata_expr or ""}
app_model_imports = {model_imports}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""


def script_template() -> str:
    return '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''


def ensure_alembic(service: Service) -> None:
    if not service.metadata_expr:
        raise RuntimeError(f"{service.name} has no metadata; Alembic cannot autogenerate it yet")

    service.versions_path.mkdir(parents=True, exist_ok=True)
    (service.migrations_path / "env.py").write_text(alembic_env_py())
    (service.migrations_path / "script.py.mako").write_text(script_template())
    service.alembic_ini.write_text(alembic_ini(service))
    print(f"Initialized Alembic for {service.name}: {service.migrations_path}")


def run_alembic(service: Service, args: Iterable[str]) -> None:
    if not service.alembic_ini.exists() or not service.migrations_path.exists():
        raise RuntimeError(f"Alembic is not initialized for {service.name}; run init first")

    env = os.environ.copy()
    env.update(load_dotenv(ROOT / ".env"))
    env.update(load_dotenv(service.path / ".env"))
    paths = [
        str(service.path),
        str(ROOT / "shared" / "types"),
        str(ROOT / "shared" / "inference-sdk"),
        str(SITE_PACKAGES),
        env.get("PYTHONPATH", ""),
    ]
    env["PYTHONPATH"] = os.pathsep.join(path for path in paths if path)

    command = [sys.executable, "-m", "alembic", "-c", str(service.alembic_ini), *args]
    subprocess.run(command, cwd=service.path, env=env, check=True)


async def create_tables(service: Service) -> None:
    load_service_env(service)
    metadata = get_metadata(service)
    engine = create_async_engine(async_database_url(get_database_url(service)))
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    await engine.dispose()
    print(f"Created tables for {service.name}")


async def drop_tables(service: Service) -> None:
    load_service_env(service)
    metadata = get_metadata(service)
    engine = create_async_engine(async_database_url(get_database_url(service)))
    async with engine.begin() as connection:
        def drop_with_cascade(sync_connection):
            preparer = sync_connection.dialect.identifier_preparer
            for table in reversed(metadata.sorted_tables):
                sync_connection.execute(
                    text(f"DROP TABLE IF EXISTS {preparer.format_table(table)} CASCADE")
                )

        await connection.run_sync(drop_with_cascade)
    await engine.dispose()
    print(f"Dropped tables for {service.name}")


async def reset_tables(service: Service) -> None:
    await drop_tables(service)
    clear_app_modules()
    await create_tables(service)


def confirm(action: str, yes: bool) -> None:
    if yes:
        return
    response = input(f"{action}. Type 'yes' to continue: ")
    if response != "yes":
        raise SystemExit("Aborted.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage service database migrations.")
    parser.add_argument(
        "command",
        choices=[
            "list",
            "init",
            "create",
            "revision",
            "upgrade",
            "downgrade",
            "current",
            "history",
            "heads",
            "stamp",
            "create-tables",
            "drop",
            "drop-tables",
            "reset",
        ],
    )
    parser.add_argument("--service", choices=["all", *service_choices()], default="model-registry")
    parser.add_argument("-m", "--message", default="schema change")
    parser.add_argument("--revision", default="head")
    parser.add_argument("--sql", action="store_true")
    parser.add_argument("--autogenerate", action="store_true")
    parser.add_argument("--yes", action="store_true")
    return parser


async def run(args: argparse.Namespace) -> None:
    if args.command == "list":
        for name in service_choices():
            service = SERVICES[name]
            metadata = "yes" if service.metadata_expr else "no"
            alembic = "yes" if service.alembic_ini.exists() else "no"
            print(f"{name:15} metadata={metadata:3} alembic={alembic}")
        return

    for service in selected_services(args.service):
        clear_app_modules()
        metadata_command = args.command in {"create-tables", "drop", "drop-tables", "reset"}
        if args.service == "all" and metadata_command and not service.metadata_expr:
            print(f"Skipped {service.name}: no SQLAlchemy metadata")
            continue

        if args.command == "init":
            ensure_alembic(service)
        elif args.command in {"create", "revision"}:
            command = ["revision", "-m", args.message]
            if args.autogenerate:
                command.append("--autogenerate")
            run_alembic(service, command)
        elif args.command == "upgrade":
            command = ["upgrade", args.revision]
            if args.sql:
                command.append("--sql")
            run_alembic(service, command)
        elif args.command == "downgrade":
            command = ["downgrade", args.revision]
            if args.sql:
                command.append("--sql")
            run_alembic(service, command)
        elif args.command in {"current", "history", "heads"}:
            run_alembic(service, [args.command])
        elif args.command == "stamp":
            run_alembic(service, ["stamp", args.revision])
        elif args.command == "create-tables":
            await create_tables(service)
        elif args.command in {"drop", "drop-tables"}:
            confirm(f"Drop all {service.name} tables", args.yes)
            await drop_tables(service)
        elif args.command == "reset":
            confirm(f"Drop and recreate all {service.name} tables", args.yes)
            await reset_tables(service)


def main() -> int:
    args = build_parser().parse_args()
    asyncio.run(run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
