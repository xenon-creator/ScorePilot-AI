from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import our models and DATABASE_URL
from app.models.database import Base, DATABASE_URL

# this is the Alembic Config object
config = context.config

# Set the sqlalchemy.url dynamically from our app config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata from our models
target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connect to a real database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
