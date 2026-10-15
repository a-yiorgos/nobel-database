import os
import pytest
import sqlite3
from fastapi.testclient import TestClient
from downloader.download import init_db, populate_db
from backend.main import app

TEST_DB_PATH = "/tmp/test_backend_nobel.db"

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    os.environ["DB_PATH"] = TEST_DB_PATH
    sample_laureates = [
        {
            "id": "1",
            "knownName": {"en": "Marie Curie"},
            "fullName": {"en": "Marie Curie, née Sklodowska"},
            "gender": "female",
            "birth": {
                "date": "1867-11-07",
                "year": "1867",
                "place": {
                    "countryNow": {"en": "Poland"},
                    "cityNow": {"en": "Warsaw"}
                }
            },
            "nobelPrizes": [
                {
                    "awardYear": "1903",
                    "category": {"en": "Physics"},
                    "categoryFullName": {"en": "The Nobel Prize in Physics"},
                    "portion": "1/4",
                    "motivation": {"en": "in recognition of the extraordinary services they have rendered by their joint researches on the radiation phenomena discovered by Professor Henri Becquerel"}
                },
                {
                    "awardYear": "1911",
                    "category": {"en": "Chemistry"},
                    "categoryFullName": {"en": "The Nobel Prize in Chemistry"},
                    "portion": "1",
                    "motivation": {"en": "in recognition of her services to the advancement of chemistry by the discovery of the elements radium and polonium"}
                }
            ]
        },
        {
            "id": "2",
            "knownName": {"en": "Albert Einstein"},
            "fullName": {"en": "Albert Einstein"},
            "gender": "male",
            "birth": {
                "date": "1879-03-14",
                "year": "1879",
                "place": {
                    "countryNow": {"en": "Germany"},
                    "cityNow": {"en": "Ulm"}
                }
            },
            "nobelPrizes": [
                {
                    "awardYear": "1921",
                    "category": {"en": "Physics"},
                    "categoryFullName": {"en": "The Nobel Prize in Physics"},
                    "portion": "1",
                    "motivation": {"en": "for his services to Theoretical Physics, and especially for his discovery of the law of the photoelectric effect"}
                }
            ]
        }
    ]
    sample_prizes = [
        {"awardYear": "1903", "category": {"en": "Physics"}, "categoryFullName": {"en": "Physics"}, "dateAwarded": "1903-12-10", "prizeAmount": 141358},
        {"awardYear": "1911", "category": {"en": "Chemistry"}, "categoryFullName": {"en": "Chemistry"}, "dateAwarded": "1911-12-10", "prizeAmount": 140695},
        {"awardYear": "1921", "category": {"en": "Physics"}, "categoryFullName": {"en": "Physics"}, "dateAwarded": "1922-11-09", "prizeAmount": 121524}
    ]

    conn = init_db(TEST_DB_PATH)
    populate_db(conn, sample_laureates, sample_prizes)
    conn.close()

    yield

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


client = TestClient(app)

def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_laureates():
    response = client.get("/api/laureates")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["laureates"]) == 2

def test_get_laureates_filter_category():
    response = client.get("/api/laureates?category=Chemistry")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["laureates"][0]["known_name"] == "Marie Curie"

def test_get_laureates_filter_year_range():
    response = client.get("/api/laureates?year_start=1910&year_end=1930")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2

def test_get_multiple_laureates():
    response = client.get("/api/laureates/multiple")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["laureates"][0]["known_name"] == "Marie Curie"
    assert len(data["laureates"][0]["prizes"]) == 2

def test_get_country_stats():
    response = client.get("/api/stats/countries")
    assert response.status_code == 200
    data = response.json()
    assert data["total_countries"] == 2
    countries = {c["birth_country"]: c["laureate_count"] for c in data["countries"]}
    assert countries["Poland"] == 1
    assert countries["Germany"] == 1

def test_search():
    response = client.get("/api/search?q=photoelectric")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["known_name"] == "Albert Einstein"
