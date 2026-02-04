import os
import sys

from alembic import command
from alembic.config import Config

# Add current directory to path so alembic can find 'models' etc
sys.path.append(os.getcwd())


def run_migrations():
    print("Running migrations...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("Migrations complete!")


if __name__ == "__main__":
    run_migrations()
