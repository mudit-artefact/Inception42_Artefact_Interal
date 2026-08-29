"""
The database connection, and the session each request works through.
"""
import os
import logging
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from app.database.tables import Base, Employee, LeaveBalance, ManagerHistory, LeaveRequest, ExpenseClaim

logger = logging.getLogger(__name__)

# Locate omni_hr.db inside Backend/data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "omni_hr.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite multi-threading in FastAPI
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_database_session():
    """
    Hands each request its own database session and closes it afterwards.

    Use this with Depends() rather than calling SessionLocal() by hand, so the session's
    lifetime is tied to the request and tests can substitute a temporary database.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# Older name, kept until the last caller is updated.
get_db = get_database_session


def columns_missing_from_the_database() -> dict[str, set[str]]:
    """
    Columns the code expects that the database on disk does not have.

    `create_all` creates tables that are missing but never alters one that already
    exists, so a database written before a column was added keeps working right up until
    something reads that column — and then every request fails with a bare "no such
    column". Comparing up front turns that into something the application can act on.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing: dict[str, set[str]] = {}

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all will make it
        on_disk = {column["name"] for column in inspector.get_columns(table.name)}
        absent = {column.name for column in table.columns} - on_disk
        if absent:
            missing[table.name] = absent
    return missing


def _seeded_employees_have_changed() -> bool:
    """Whether the database holds a different cast of employees from the seed."""
    from app.database.seed_employees import build_seed_employees

    session = SessionLocal()
    try:
        in_database = {employee.user_id for employee in session.query(Employee).all()}
    finally:
        session.close()

    if not in_database:
        return False
    expected = {record["employee"].user_id for record in build_seed_employees()}
    return in_database != expected


def init_and_seed_db(force_reseed: bool = False) -> int:
    """
    Create the tables if they are missing, then add the starting employees.

    This database holds demonstration data and nothing else — it is written from
    `seed_employees.py` and never edited by hand — so when it no longer matches the code
    it is rebuilt rather than left to fail on the next query. The two ways it stops
    matching are a column being added to a model, and the seed itself changing.
    """
    from app.database.seed_database import seed_database

    Base.metadata.create_all(bind=engine)

    missing_columns = columns_missing_from_the_database()
    if missing_columns:
        logger.warning(
            f"The database at {DB_PATH} was written before these columns existed: "
            f"{missing_columns}. Rebuilding it from the seed, because it holds only "
            f"demonstration data. Any local edits to it will be lost."
        )
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        force_reseed = True
    elif _seeded_employees_have_changed():
        logger.warning(
            "The employees in the database are not the ones the seed defines. "
            "Reseeding so the records and the policies agree."
        )
        force_reseed = True

    session = SessionLocal()
    try:
        return seed_database(session, force=force_reseed)
    finally:
        session.close()
