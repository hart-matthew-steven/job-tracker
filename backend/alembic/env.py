from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import create_engine

from alembic import context

from app.core.config import settings
from app.core.base import Base

from app.models.job_application import JobApplication
from app.models.job_activity import JobActivity
from app.models.job_application_note import JobApplicationNote
from app.models.job_application_tag import JobApplicationTag
from app.models.job_document import JobDocument
from app.models.job_interview import JobInterview
from app.models.saved_view import SavedView
from app.models.user import User
from app.models.refresh_token import RefreshToken

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic should run with the migrator (DDL-capable) credentials.
# Fall back to the app user if migrator env vars are not defined (e.g. local proto setups).
if settings.DB_MIGRATOR_USER and settings.DB_MIGRATOR_PASSWORD:
    migrations_url = settings.migrations_database_url
else:
    migrations_url = settings.database_url

# ConfigParser treats "%" as interpolation markers; escape them for the .ini writer.
config.set_main_option("sqlalchemy.url", migrations_url.replace("%", "%%"))

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=migrations_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(
        migrations_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
