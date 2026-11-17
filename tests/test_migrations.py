from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.migrations import add_missing_columns

# The evidence_candidates table exactly as it was BEFORE the quote-check columns existed.
OLD_TABLE = """
CREATE TABLE evidence_candidates (
    id INTEGER PRIMARY KEY,
    niche_id INTEGER NOT NULL,
    criterion VARCHAR(50) NOT NULL,
    proposed_score INTEGER NOT NULL,
    confidence VARCHAR(20) NOT NULL,
    claim TEXT NOT NULL,
    source_url VARCHAR(1000) NOT NULL,
    source_title VARCHAR(300) NOT NULL,
    publisher VARCHAR(200),
    source_published VARCHAR(100),
    source_excerpt TEXT NOT NULL,
    origin VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL,
    reviewer_note TEXT,
    reviewed_at DATETIME,
    evidence_id INTEGER,
    created_at DATETIME NOT NULL
)
"""


def old_database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(text(OLD_TABLE))
        conn.execute(
            text(
                "INSERT INTO evidence_candidates (niche_id, criterion, proposed_score, confidence,"
                " claim, source_url, source_title, source_excerpt, origin, status, created_at)"
                " VALUES (1, 'audience_demand', 7, 'low', 'An existing claim', 'https://example.com',"
                " '', 'An existing excerpt', 'human_entered', 'pending', '2026-11-01 00:00:00')"
            )
        )
    return engine


def test_missing_columns_are_added_and_old_rows_survive():
    engine = old_database()
    added = add_missing_columns(engine)

    assert "evidence_candidates.quote_check_status" in added
    assert "evidence_candidates.quote_checked_at" in added
    columns = {c["name"] for c in inspect(engine).get_columns("evidence_candidates")}
    assert {"quote_check_status", "quote_checked_at"} <= columns

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT claim, quote_check_status, quote_checked_at FROM evidence_candidates")
        ).one()
    assert row.claim == "An existing claim"          # old data kept
    assert row.quote_check_status == "not_checked"   # sensible default for old rows
    assert row.quote_checked_at is None


def test_running_it_twice_changes_nothing():
    engine = old_database()
    add_missing_columns(engine)
    assert add_missing_columns(engine) == []


def test_tables_that_do_not_exist_yet_are_left_for_create_all():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    assert add_missing_columns(engine) == []
