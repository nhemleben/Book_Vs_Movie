
import requests
import math
import pandas as pd
import csv
import os
from threading import Thread
import time

OPEN_LIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPEN_LIBRARY_WORK = "https://openlibrary.org"

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
GOOGLE_BOOKS_API_KEY = "AIzaSyD1VtIwjaYaOfs4gW6nDsJf9P0RPOth0zY"  # Replace with your actual key

def google_search_book(title):
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": title, "key": GOOGLE_BOOKS_API_KEY}

    r = requests.get(url, params=params)
    if r.status_code == 429:
        print("Rate limit hit for Google Books. Waiting before retrying...")
        return None
    return r.json()


def extract_ratings(items):
    ratings = []

    for item in items:
        info = item.get("volumeInfo", {})

        rating = info.get("averageRating")
        count = info.get("ratingsCount", 0)

        if rating is not None and count > 0:
            ratings.append((2*rating, count)) #double the rating to convert from 0-5 to 0-10 scale

    return ratings


def weighted_rating(ratings):
    if not ratings:
        return None

    total_weight = sum(c for _, c in ratings)
    if total_weight == 0:
        return None

    return sum(r * c for r, c in ratings) / total_weight



def compute_book_rating(data):
    items = data.get("items", [])

    ratings = extract_ratings(items)
    return weighted_rating(ratings)











def get_wikidata_id(title):
    url = "https://www.wikidata.org/w/api.php"

    params = {
        "action": "wbsearchentities",
        "search": title,
        "language": "en",
        "format": "json"
    }

    headers = {
        "User-Agent": "BookAdaptationComparer/1.0"
    }

    r = requests.get(url, params=params, headers=headers, timeout=10)

    if r.status_code != 200:
        return None

    data = r.json()

    if "search" not in data:
        return None

    candidates = data["search"]

    # ----------------------------
    # Prefer high-quality matches
    # ----------------------------
    preferred_keywords = [
        "novel",
        "book",
        "literary work",
        "written work"
    ]

    for c in candidates:
        desc = (c.get("description") or "").lower()

        if any(k in desc for k in preferred_keywords):
            return c["id"]

    # fallback
    return candidates[0]["id"] if candidates else None





def get_novel_qid(title):
    url = "https://query.wikidata.org/sparql"

    query = f"""
    SELECT ?item WHERE {{
      ?item rdfs:label "{title}"@en .

      ?item (wdt:P31/wdt:P279*) ?type .

      VALUES ?type {{
        wd:Q7725634   # literary work
        wd:Q571        # book
        wd:Q8261       # novel
      }}
    }}
    LIMIT 5
    """

    headers = {
        "User-Agent": "BookAdaptationComparer/1.0"
    }

    r = requests.get(url, params={"query": query, "format": "json"}, headers=headers)

    if r.status_code != 200:
        print("SPARQL error:", r.status_code)
        return None

    data = r.json()

    results = data["results"]["bindings"]

    if not results:
        return None

    # Extract QID from full URL
    uri = results[0]["item"]["value"]
    qid = uri.split("/")[-1]

    return qid



def get_adaptations_wikidata(book_qid):
    query = f"""
    SELECT ?adaptation ?adaptationLabel ?imdb
    WHERE {{
      ?adaptation wdt:P144 wd:{book_qid} .
      OPTIONAL {{ ?adaptation wdt:P345 ?imdb . }}  # IMDb ID if exists
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """

    url = "https://query.wikidata.org/sparql"

    headers = {
        "User-Agent": "BookAdaptationComparer/1.0"
    }

    r = requests.get(url, params={"query": query, "format": "json"}, headers=headers)
    data = r.json()

    results = []

    for item in data["results"]["bindings"]:
        results.append({
            "title": item["adaptationLabel"]["value"],
            "imdb_id": item.get("imdb", {}).get("value"),
            'url': item["adaptation"]["value"],
            'url_ending': item["adaptation"]["value"].split("/")[-1]  # Extract QID for potential future use
        })

    return results


def get_derivative_works(qid):
    url = "https://query.wikidata.org/sparql"

    query = f"""
    SELECT ?work ?workLabel ?type (YEAR(?date) AS ?year) WHERE {{
      {{
        ?work wdt:P144 wd:{qid} .
        BIND("based_on" AS ?type)
      }}
      UNION
      {{
        ?work wdt:P941 wd:{qid} .
        BIND("inspired_by" AS ?type)
      }}

      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """

    headers = {
        "User-Agent": "DerivativeWorkFetcher/1.0"
    }

    r = requests.get(url, params={"query": query, "format": "json"}, headers=headers)
    data = r.json()

    results = []

    for item in data["results"]["bindings"]:
        results.append({
            "title": item["workLabel"]["value"],
            "type": item["type"]["value"],
            "year": item["work"]["value"],
            "imdb_id": item.get("imdb", {}).get("value")
        })

    return results


def find_book(title):
    params = {"q": title}
    r = requests.get(OPEN_LIBRARY_SEARCH, params=params)
    data = r.json()

    if "docs" not in data or not data["docs"]:
        return None

    book = data["docs"][0]

    return {
        "title": book.get("title"),
        "key": book.get("key"),  # /works/OL...
        "ratings_average": book.get("ratings_average"),
        "ratings_count": book.get("ratings_count", 0)
    }

# ----------------------------
# Step 2: Normalize rating
# Open Library uses 0–5 scale
# ----------------------------
def normalize_rating(r):
    if r is None:
        return None
    return r * 2  # convert to 0–10 scale






OMDB_API_KEY = "f73a0372"

def get_rating(imdb_id):
    if not imdb_id:
        return None

    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
    data = requests.get(url).json()

    # Check for OMDb API rate limit
    if data.get("Response") == "False" and data.get("Error") == "Request limit reached!":
        print("OMDb API request limit reached! Please wait until the next UTC day for reset.")
        return None

    if data.get("imdbRating") and data["imdbRating"] != "N/A":
        return float(data["imdbRating"])

    return None


def compare_book_vs_adaptations(book_title):
    print(f"\n📚 Book: {book_title}")

    #real_book_data = analyze_book(book_title)
    google_book_data = google_search_book(book_title)

    if not google_book_data.get("items"):
        print("No Google Books data found.")
        return False

    ratings = extract_ratings(google_book_data["items"])
    weighted_ratings = weighted_rating(ratings)
    if not weighted_ratings:
        print("No Google Books ratings found.")
        weighted_ratings = -1

    print(f"Weighted Google Books rating: {(weighted_ratings):.2f}/10")

    book_qid = get_wikidata_id(book_title)

    if not book_qid:
        print("Book not found in Wikidata.")
        return False

    print(f"Wikidata ID: {book_qid}")

    adaptations = get_adaptations_wikidata(book_qid)

    if not adaptations:
        print("No book adaptations found via P144.")
        return False

    print("\n🎬 Adaptations (Wikidata P144):")

    scored = []

    for a in adaptations:
        rating = get_rating(a["imdb_id"])
        if rating:
            scored.append((a["title"], a['url'], rating))
        else:
            scored.append((a["title"], a['url'], -1))  # Use -1 to indicate no rating found

    scored.sort(key=lambda x: x[2], reverse=True)

    print("\n🏆 Ranked adaptations:")
    for title, url, rating in scored:
        print(f"{title} ({url}): {rating}/10")

    write_adaptations_to_csv(book_title, weighted_ratings, scored)
    return True  # Indicate success


def write_adaptations_to_csv(source, book_score, scored, csv_path="adaptations_with_ratings.csv"):
    """
    Write a list of (title, url, rating) tuples to a CSV file.
    """
    file_exists = os.path.isfile(csv_path)
    with open(csv_path, mode="a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["source", "source_score", "title", "url", "rating"])

        for title, url, rating in scored:
            writer.writerow([source, book_score, title, url, rating])


def load_book_titles_from_csv(csv_path="books_with_adaptations.csv"):
    """
    Load all book titles from the given CSV file.
    Returns a list of titles.
    """
    df = pd.read_csv(csv_path)
    return df["book"].tolist()


def compare_book_with_timeout(book_title):
    for attempt in range(2):
        try:
            # Run with timeout

            result = [False]
            def target(book_title=book_title):
                result[0] = compare_book_vs_adaptations(book_title)

            t = Thread(target=target)
            t.start()
            t.join(timeout=5)
            if t.is_alive():
                print(f"Timeout for {book_title} (attempt {attempt+1})")
                t.join(0)  # Try to clean up thread
            elif result[0]:
                break  # Success
            else:
                print(f"Failed to process {book_title} (attempt {attempt+1})")
        except Exception as e:
            print(f"Exception during attempt {attempt+1} for {book_title}: {e}")
    else:
        print(f"Skipped {book_title} after two timeouts.")





# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":

    properties_to_check = load_book_titles_from_csv()

    # properties_to_check = [
    #     "Dune",
    #     "Harry Potter and the Sorcerer's Stone",
    #     "The Lord of the Rings",
    #     "The Great Gatsby",
    #     "The Shining",
    # ]
    #property_to_check = properties_to_check[0]  # Change index to test different books


    #properties_to_check = ["The Three Musketeers"]

    last_ran = "Ach wie flüchtig, ach wie nichtig"
    start_index = 1 + properties_to_check.index(last_ran)  # Find the index of the last ran book to resume from there


    start_index = 0  # For testing, start from the beginning
    properties_to_check = ["Estoria de España"]

    for property_to_check in properties_to_check[start_index:]:
        #compare_book_vs_adaptations(property_to_check)
        compare_book_with_timeout(property_to_check)