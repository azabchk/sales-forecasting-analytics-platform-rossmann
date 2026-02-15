import sqlalchemy as sa

from app.config import get_settings

settings = get_settings()
engine = sa.create_engine(settings.database_url, future=True, pool_pre_ping=True)


def fetch_all(query: sa.sql.elements.TextClause, params: dict | None = None) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(query, params or {}).mappings().all()
    return [dict(row) for row in rows]


def fetch_one(query: sa.sql.elements.TextClause, params: dict | None = None) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(query, params or {}).mappings().first()
    return dict(row) if row else None
