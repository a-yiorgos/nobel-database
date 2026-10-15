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


def check_column_exists(conn, table_name, column_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


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

    has_wiki = check_column_exists(conn, "laureates", "wikipedia_url")

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

    # Select fields
    wiki_col = "l.wikipedia_url," if has_wiki else "NULL as wikipedia_url,"
    birth_country_now_col = "l.birth_country_now," if check_column_exists(conn, "laureates", "birth_country_now") else "NULL as birth_country_now,"
    death_country_col = "l.death_country, l.death_country_now," if check_column_exists(conn, "laureates", "death_country") else "NULL as death_country, NULL as death_country_now,"

    data_sql = f"""
        SELECT DISTINCT l.id, l.known_name, l.full_name, l.gender, l.birth_date, l.birth_year,
               l.birth_country, {birth_country_now_col} {death_country_col} {wiki_col} l.birth_city, l.is_organization
        FROM laureates l
        JOIN laureate_prizes p ON l.id = p.laureate_id
        {where_str}
        ORDER BY l.known_name ASC
        LIMIT ? OFFSET ?
    """
    cursor.execute(data_sql, params + [limit, offset])
    laureate_rows = cursor.fetchall()

    has_award_country = check_column_exists(conn, "laureate_prizes", "award_country")
    prize_award_cols = "award_country, award_country_now," if has_award_country else "NULL as award_country, NULL as award_country_now,"

    results = []
    for row in laureate_rows:
        laureate_dict = dict(row)
        cursor.execute(
            f"""
            SELECT award_year, category, category_full, portion, sort_order, motivation, prize_status, {prize_award_cols} affiliations
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

    has_wiki = check_column_exists(conn, "laureates", "wikipedia_url")
    wiki_col = "l.wikipedia_url," if has_wiki else "NULL as wikipedia_url,"

    query = f"""
        SELECT l.id, l.known_name, l.full_name, l.gender, l.birth_country, {wiki_col} COUNT(p.id) as prize_count
        FROM laureates l
        JOIN laureate_prizes p ON l.id = p.laureate_id
        GROUP BY l.id
        HAVING prize_count > 1
        ORDER BY prize_count DESC, l.known_name ASC
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    has_award_country = check_column_exists(conn, "laureate_prizes", "award_country")
    prize_award_cols = "award_country, award_country_now," if has_award_country else "NULL as award_country, NULL as award_country_now,"

    results = []
    for row in rows:
        laureate_dict = dict(row)
        cursor.execute(
            f"""
            SELECT award_year, category, category_full, portion, motivation, {prize_award_cols} affiliations
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
    """Retrieve laureate counts grouped by country at time of award (affiliation/residence country)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    has_award_country = check_column_exists(conn, "laureate_prizes", "award_country")

    if has_award_country:
        query = """
            SELECT award_country as country, COUNT(DISTINCT laureate_id) as laureate_count
            FROM laureate_prizes
            WHERE award_country IS NOT NULL AND award_country != ''
            GROUP BY award_country
            ORDER BY laureate_count DESC, award_country ASC
        """
    else:
        # Fallback to birth country if award_country column is absent
        query = """
            SELECT birth_country as country, COUNT(id) as laureate_count
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
        "stat_type": "At time of prize awarded (Affiliation/Residence Country)" if has_award_country else "Birth Country",
        "total_countries": len(results),
        "countries": results
    }


@app.get("/api/search/country")
def search_by_country(q: str = Query(..., min_length=1, description="Search query term for country matching")):
    """Search laureates across birth, death, and award countries (then and now) and highlight matching reasons."""
    conn = get_db_connection()
    cursor = conn.cursor()

    has_award_country = check_column_exists(conn, "laureate_prizes", "award_country")
    has_birth_now = check_column_exists(conn, "laureates", "birth_country_now")
    has_death = check_column_exists(conn, "laureates", "death_country")
    has_wiki = check_column_exists(conn, "laureates", "wikipedia_url")

    wiki_col = "l.wikipedia_url," if has_wiki else "NULL as wikipedia_url,"
    birth_now_col = "l.birth_country_now," if has_birth_now else "NULL as birth_country_now,"
    death_cols = "l.death_country, l.death_country_now," if has_death else "NULL as death_country, NULL as death_country_now,"

    # Query all laureates and their prizes to evaluate country matches
    sql = f"""
        SELECT DISTINCT l.id, l.known_name, l.full_name, l.birth_country, {birth_now_col} {death_cols} {wiki_col} l.is_organization
        FROM laureates l
    """
    cursor.execute(sql)
    laureates_list = cursor.fetchall()

    term = q.strip().lower()
    matched_results = []

    for l_row in laureates_list:
        l_dict = dict(l_row)
        laureate_id = l_dict["id"]

        # Fetch prizes for this laureate
        prize_award_cols = "award_country, award_country_now," if has_award_country else "NULL as award_country, NULL as award_country_now,"
        cursor.execute(
            f"""
            SELECT award_year, category, motivation, {prize_award_cols} affiliations
            FROM laureate_prizes
            WHERE laureate_id = ?
            ORDER BY award_year DESC
            """,
            (laureate_id,)
        )
        prizes = [dict(p) for p in cursor.fetchall()]

        matched_reasons = []

        # Check birth country (then)
        bc = l_dict.get("birth_country")
        if bc and term in bc.lower():
            matched_reasons.append(f"Birth Country (then): {bc}")

        # Check birth country (now)
        bc_now = l_dict.get("birth_country_now")
        if bc_now and term in bc_now.lower() and (not bc or bc_now.lower() != bc.lower() or f"Birth Country (then): {bc}" not in matched_reasons):
            matched_reasons.append(f"Birth Country (now): {bc_now}")

        # Check death country (then)
        dc = l_dict.get("death_country")
        if dc and term in dc.lower():
            matched_reasons.append(f"Death Country (then): {dc}")

        # Check death country (now)
        dc_now = l_dict.get("death_country_now")
        if dc_now and term in dc_now.lower() and (not dc or dc_now.lower() != dc.lower() or f"Death Country (then): {dc}" not in matched_reasons):
            matched_reasons.append(f"Death Country (now): {dc_now}")

        # Check award country (then and now)
        for p in prizes:
            ac = p.get("award_country")
            if ac and term in ac.lower():
                reason = f"Award Country (then) for {p['category']} ({p['award_year']}): {ac}"
                if reason not in matched_reasons:
                    matched_reasons.append(reason)

            ac_now = p.get("award_country_now")
            if ac_now and term in ac_now.lower() and (not ac or ac_now.lower() != ac.lower()):
                reason = f"Award Country (now) for {p['category']} ({p['award_year']}): {ac_now}"
                if reason not in matched_reasons:
                    matched_reasons.append(reason)

        if matched_reasons:
            l_dict["prizes"] = prizes
            l_dict["matched_reasons"] = matched_reasons
            matched_results.append(l_dict)

    conn.close()
    return {
        "query": q,
        "count": len(matched_results),
        "results": matched_results
    }


@app.get("/api/search")
def search_motivations(q: str = Query(..., min_length=1, description="Search query term for prize motivations")):
    """Full-text search across award motivations."""
    conn = get_db_connection()
    cursor = conn.cursor()

    safe_q = f'"{q.replace('"', '""')}"*' if not any(c in q for c in ['*', ':']) else q

    has_wiki = check_column_exists(conn, "laureates", "wikipedia_url")
    wiki_col = "l.wikipedia_url," if has_wiki else "NULL as wikipedia_url,"

    query = f"""
        SELECT f.laureate_id, f.known_name, f.award_year, f.category, f.motivation,
               l.full_name, l.birth_country, {wiki_col} l.is_organization
        FROM fts_motivations f
        JOIN laureates l ON f.laureate_id = l.id
        WHERE fts_motivations MATCH ?
        ORDER BY f.award_year DESC
    """
    try:
        cursor.execute(query, (safe_q,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        like_query = f"""
            SELECT p.laureate_id, l.known_name, p.award_year, p.category, p.motivation,
                   l.full_name, l.birth_country, {wiki_col} l.is_organization
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
