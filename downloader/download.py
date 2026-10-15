#!/usr/bin/env python3
"""
Downloader script for Nobel Prize API data.
Fetches laureates and nobelPrizes endpoints, normalizes data, and saves to SQLite database.
"""

import os
import sys
import json
import sqlite3
import argparse
import logging
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

LAUREATES_API_URL = "https://api.nobelprize.org/2.1/laureates"
NOBEL_PRIZES_API_URL = "https://api.nobelprize.org/2.1/nobelPrizes"


def fetch_all_pages(base_url, item_key):
    """Fetch all pages from the Nobel Prize API using offset/limit pagination."""
    items = []
    offset = 0
    limit = 100
    headers = {"User-Agent": "NobelDownloader/1.0"}

    while True:
        url = f"{base_url}?offset={offset}&limit={limit}"
        logging.info(f"Fetching {url}...")
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            logging.error(f"Error fetching {url}: {e}")
            raise e

        page_items = data.get(item_key, [])
        items.extend(page_items)
        meta = data.get("meta", {})
        count = meta.get("count", len(items))

        logging.info(f"Fetched {len(items)} / {count} {item_key}")
        if len(items) >= count or not page_items:
            break
        offset += limit

    return items


def init_db(db_path):
    """Initialize SQLite database schema."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS laureates (
            id TEXT PRIMARY KEY,
            known_name TEXT,
            full_name TEXT,
            gender TEXT,
            birth_date TEXT,
            birth_year INTEGER,
            birth_country TEXT,
            birth_country_now TEXT,
            birth_city TEXT,
            death_country TEXT,
            death_country_now TEXT,
            wikipedia_url TEXT,
            is_organization INTEGER
        );

        CREATE TABLE IF NOT EXISTS nobel_prizes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            award_year INTEGER,
            category TEXT,
            category_full TEXT,
            date_awarded TEXT,
            prize_amount INTEGER
        );

        CREATE TABLE IF NOT EXISTS laureate_prizes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            laureate_id TEXT,
            award_year INTEGER,
            category TEXT,
            category_full TEXT,
            portion TEXT,
            sort_order TEXT,
            motivation TEXT,
            prize_status TEXT,
            affiliations TEXT,
            award_country TEXT,
            award_country_now TEXT,
            FOREIGN KEY (laureate_id) REFERENCES laureates(id)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS fts_motivations USING fts5(
            laureate_id,
            known_name,
            award_year,
            category,
            motivation
        );

        CREATE INDEX IF NOT EXISTS idx_laureates_country ON laureates(birth_country);
        CREATE INDEX IF NOT EXISTS idx_prizes_category_year ON laureate_prizes(category, award_year);
        CREATE INDEX IF NOT EXISTS idx_prizes_laureate ON laureate_prizes(laureate_id);
        CREATE INDEX IF NOT EXISTS idx_prizes_award_country ON laureate_prizes(award_country);
    """)
    conn.commit()
    return conn


def populate_db(conn, laureates_data, prizes_data):
    """Populate SQLite database from fetched laureates and prizes JSON."""
    cursor = conn.cursor()

    # Clear existing data for idempotency
    cursor.execute("DELETE FROM laureate_prizes;")
    cursor.execute("DELETE FROM laureates;")
    cursor.execute("DELETE FROM nobel_prizes;")
    cursor.execute("DELETE FROM fts_motivations;")

    # Populate laureates and their prizes from laureates API response
    for l in laureates_data:
        l_id = str(l.get("id"))
        known_name = (l.get("knownName") or {}).get("en") or (l.get("orgName") or {}).get("en") or "Unknown"
        full_name = (l.get("fullName") or {}).get("en") or (l.get("orgName") or {}).get("en") or known_name
        gender = l.get("gender")
        is_org = 1 if "orgName" in l or gender is None else 0

        # Wikipedia link
        wiki_data = l.get("wikipedia") or {}
        wikipedia_url = wiki_data.get("english")

        birth = l.get("birth") or {}
        birth_date = birth.get("date")
        birth_year_str = birth.get("year")
        birth_year = int(birth_year_str) if birth_year_str and birth_year_str.isdigit() else None

        birth_place = birth.get("place") or {}
        birth_country = (birth_place.get("country") or {}).get("en")
        birth_country_now = (birth_place.get("countryNow") or birth_place.get("country") or {}).get("en")
        birth_city = (birth_place.get("cityNow") or birth_place.get("city") or {}).get("en")

        death = l.get("death") or {}
        death_place = death.get("place") or {}
        death_country = (death_place.get("country") or {}).get("en")
        death_country_now = (death_place.get("countryNow") or death_place.get("country") or {}).get("en")

        cursor.execute(
            """
            INSERT OR REPLACE INTO laureates
            (id, known_name, full_name, gender, birth_date, birth_year, birth_country, birth_country_now, birth_city, death_country, death_country_now, wikipedia_url, is_organization)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (l_id, known_name, full_name, gender, birth_date, birth_year, birth_country, birth_country_now, birth_city, death_country, death_country_now, wikipedia_url, is_org)
        )

        # Process prizes array inside laureate
        for p in l.get("nobelPrizes", []):
            award_year_str = p.get("awardYear")
            award_year = int(award_year_str) if award_year_str and award_year_str.isdigit() else None
            category = (p.get("category") or {}).get("en")
            category_full = (p.get("categoryFullName") or {}).get("en")
            portion = p.get("portion")
            sort_order = p.get("sortOrder")
            motivation = (p.get("motivation") or {}).get("en")
            prize_status = p.get("prizeStatus")

            affiliations_list = []
            award_countries = []
            award_countries_now = []

            for aff in p.get("affiliations", []):
                aff_name = (aff.get("name") or {}).get("en")
                aff_city = (aff.get("city") or {}).get("en")
                aff_country = (aff.get("country") or {}).get("en")
                aff_country_now = (aff.get("countryNow") or aff.get("country") or {}).get("en")

                if aff_country:
                    award_countries.append(aff_country)
                if aff_country_now:
                    award_countries_now.append(aff_country_now)

                parts = [x for x in [aff_name, aff_city, aff_country] if x]
                if parts:
                    affiliations_list.append(", ".join(parts))

            # Residence place fallback if affiliations list has no country
            res_place = p.get("residencePlace") or {}
            res_country = (res_place.get("country") or {}).get("en")
            res_country_now = (res_place.get("countryNow") or res_place.get("country") or {}).get("en")
            if res_country:
                award_countries.append(res_country)
            if res_country_now:
                award_countries_now.append(res_country_now)

            affiliations_str = " | ".join(affiliations_list) if affiliations_list else None
            primary_award_country = award_countries[0] if award_countries else None
            primary_award_country_now = award_countries_now[0] if award_countries_now else None

            cursor.execute(
                """
                INSERT INTO laureate_prizes
                (laureate_id, award_year, category, category_full, portion, sort_order, motivation, prize_status, affiliations, award_country, award_country_now)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (l_id, award_year, category, category_full, portion, sort_order, motivation, prize_status, affiliations_str, primary_award_country, primary_award_country_now)
            )

            if motivation:
                cursor.execute(
                    """
                    INSERT INTO fts_motivations (laureate_id, known_name, award_year, category, motivation)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (l_id, known_name, str(award_year or ""), category or "", motivation)
                )

    # Populate nobel_prizes table from nobelPrizes endpoint
    for p in prizes_data:
        award_year_str = p.get("awardYear")
        award_year = int(award_year_str) if award_year_str and award_year_str.isdigit() else None
        category = (p.get("category") or {}).get("en")
        category_full = (p.get("categoryFullName") or {}).get("en")
        date_awarded = p.get("dateAwarded")
        prize_amount = p.get("prizeAmount")

        cursor.execute(
            """
            INSERT INTO nobel_prizes (award_year, category, category_full, date_awarded, prize_amount)
            VALUES (?, ?, ?, ?, ?)
            """,
            (award_year, category, category_full, date_awarded, prize_amount)
        )

    conn.commit()
    logging.info("Database population completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Download Nobel Prize data into SQLite database.")
    parser.add_argument("--db-path", default=os.getenv("DB_PATH", "/data/nobel.db"), help="Path to SQLite DB file")
    args = parser.parse_args()

    logging.info(f"Starting downloader... Target DB path: {args.db_path}")
    laureates = fetch_all_pages(LAUREATES_API_URL, "laureates")
    prizes = fetch_all_pages(NOBEL_PRIZES_API_URL, "nobelPrizes")

    conn = init_db(args.db_path)
    populate_db(conn, laureates, prizes)
    conn.close()
    logging.info(f"Successfully populated {args.db_path}")


if __name__ == "__main__":
    main()
