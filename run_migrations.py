import sys
import os
from alembic.config import Config
from alembic import command

# Add current directory to path so alembic can find 'models' etc
sys.path.append(os.getcwd())

def run_migrations():
    print("Running migrations...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("Migrations complete!")

if __name__ == "__main__":
    run_migrations()
