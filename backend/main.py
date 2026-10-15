import os
import sqlite3
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Nobel Laureates API",
    description="RESTful API providing access to Nobel Prize laureates and statistics.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_path():
    return os.getenv("DB_PATH", "/data/nobel.db")


def get_db_connection():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        raise HTTPException(status_code=503, detail=f"Database file not found at {db_path}. Has downloader run?")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/healthz")
def healthz():
    """Liveness and readiness probe endpoint."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        raise HTTPException(status_code=503, detail="Database file missing")
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1 FROM laureates LIMIT 1;")
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection error: {str(e)}")
    return {"status": "ok"}


@app.get("/api/laureates")
def get_laureates(
    category: Optional[str] = Query(None, description="Filter by Nobel category (e.g., Physics, Chemistry, Peace)"),
    year_start: Optional[int] = Query(None, description="Filter starting award year"),
    year_end: Optional[int] = Query(None, description="Filter ending award year"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Retrieve list of laureates with optional category and year range filters."""
    conn = get_db_connection()
    cursor = conn.cursor()

    where_clauses = []
    params = []

    if category:
        where_clauses.append("LOWER(p.category) = LOWER(?)")
        params.append(category)
    if year_start is not None:
        where_clauses.append("p.award_year >= ?")
        params.append(year_start)
    if year_end is not None:
        where_clauses.append("p.award_year <= ?")
        params.append(year_end)

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Count query
    count_sql = f"""
        SELECT COUNT(DISTINCT l.id)
        FROM laureates l
        JOIN laureate_prizes p ON l.id = p.laureate_id
        {where_str}
    """
    cursor.execute(count_sql, params)
    total_count = cursor.fetchone()[0]

    # Data query
    data_sql = f"""
        SELECT DISTINCT l.id, l.known_name, l.full_name, l.gender, l.birth_date, l.birth_year, l.birth_country, l.birth_city, l.is_organization
        FROM laureates l
        JOIN laureate_prizes p ON l.id = p.laureate_id
        {where_str}
        ORDER BY l.known_name ASC
        LIMIT ? OFFSET ?
    """
    cursor.execute(data_sql, params + [limit, offset])
    laureate_rows = cursor.fetchall()

    results = []
    for row in laureate_rows:
        laureate_dict = dict(row)
        # Fetch associated prizes for each laureate
        cursor.execute(
            """
            SELECT award_year, category, category_full, portion, sort_order, motivation, prize_status, affiliations
            FROM laureate_prizes
            WHERE laureate_id = ?
            ORDER BY award_year DESC
            """,
            (laureate_dict["id"],)
        )
        laureate_dict["prizes"] = [dict(p) for p in cursor.fetchall()]
        results.append(laureate_dict)

    conn.close()
    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "laureates": results
    }


@app.get("/api/laureates/multiple")
def get_multiple_prize_laureates():
    """Retrieve individuals or organizations that have won multiple Nobel prizes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT l.id, l.known_name, l.full_name, l.gender, l.birth_country, COUNT(p.id) as prize_count
        FROM laureates l
        JOIN laureate_prizes p ON l.id = p.laureate_id
        GROUP BY l.id
        HAVING prize_count > 1
        ORDER BY prize_count DESC, l.known_name ASC
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        laureate_dict = dict(row)
        cursor.execute(
            """
            SELECT award_year, category, category_full, portion, motivation, affiliations
            FROM laureate_prizes
            WHERE laureate_id = ?
            ORDER BY award_year ASC
            """,
            (laureate_dict["id"],)
        )
        laureate_dict["prizes"] = [dict(p) for p in cursor.fetchall()]
        results.append(laureate_dict)

    conn.close()
    return {
        "count": len(results),
        "laureates": results
    }


@app.get("/api/stats/countries")
def get_country_stats():
    """Retrieve laureate counts grouped by birth country."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT birth_country, COUNT(id) as laureate_count
        FROM laureates
        WHERE birth_country IS NOT NULL AND birth_country != ''
        GROUP BY birth_country
        ORDER BY laureate_count DESC, birth_country ASC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    results = [dict(r) for r in rows]
    return {
        "total_countries": len(results),
        "countries": results
    }


@app.get("/api/search")
def search_motivations(q: str = Query(..., min_length=1, description="Search query term for prize motivations")):
    """Full-text search across award motivations."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Sanitize search term for FTS5
    safe_q = f'"{q.replace('"', '""')}"*' if not any(c in q for c in ['*', ':']) else q

    query = """
        SELECT f.laureate_id, f.known_name, f.award_year, f.category, f.motivation,
               l.full_name, l.birth_country
        FROM fts_motivations f
        JOIN laureates l ON f.laureate_id = l.id
        WHERE fts_motivations MATCH ?
        ORDER BY f.award_year DESC
    """
    try:
        cursor.execute(query, (safe_q,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        # Fallback to LIKE if FTS query syntax is invalid
        like_query = """
            SELECT p.laureate_id, l.known_name, p.award_year, p.category, p.motivation,
                   l.full_name, l.birth_country
            FROM laureate_prizes p
            JOIN laureates l ON p.laureate_id = l.id
            WHERE p.motivation LIKE ?
            ORDER BY p.award_year DESC
        """
        cursor.execute(like_query, (f"%{q}%",))
        rows = cursor.fetchall()

    conn.close()
    return {
        "query": q,
        "count": len(rows),
        "results": [dict(r) for r in rows]
    }
