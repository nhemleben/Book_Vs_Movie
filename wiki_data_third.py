
import requests
import math

OPEN_LIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPEN_LIBRARY_WORK = "https://openlibrary.org"

def get_editions(work_key):
    url = f"https://openlibrary.org{work_key}/editions.json"
    r = requests.get(url)

    if r.status_code != 200:
        return []

    return r.json().get("entries", [])


def extract_ratings(editions):
    ratings = []

    for e in editions:
        r = e.get("ratings_average")
        c = e.get("ratings_count")

        if r is not None and c:
            ratings.append((r, c))

    return ratings


def aggregate(ratings):
    if not ratings:
        return None

    total_weight = sum(c for _, c in ratings)
    if total_weight == 0:
        return None

    weighted = sum(r * c for r, c in ratings) / total_weight
    return weighted














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
            "imdb_id": item.get("imdb", {}).get("value")
        })

    return results


def get_derivative_works(qid):
    url = "https://query.wikidata.org/sparql"

    query = f"""
    SELECT ?work ?workLabel ?type WHERE {{
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

# ----------------------------
# Step 3: Weighted sentiment score
# ----------------------------
def compute_sentiment(rating, count):
    if rating is None:
        return None

    return rating * math.log10(count + 1)

def analyze_book(title):
    book = find_book(title)

    print(book)

    if not book:
        print("Book not found.")
        return


    editions = get_editions(book["key"])
    ratings = extract_ratings(editions)

    avg = aggregate(ratings)

    print("\n📊 Aggregated rating:", avg)
    print("📦 Edition count with ratings:", len(ratings))

    return avg

#    rating_5 = book["ratings_average"]
#    rating_10 = normalize_rating(rating_5)
#    count = book["ratings_count"]
#
#    sentiment = compute_sentiment(rating_10, count)
#
#    print(f"\n📚 {book['title']}")
#    print(f"Open Library rating: {rating_5}/5")
#    print(f"Normalized rating: {rating_10}/10")
#    print(f"Ratings count: {count}")
#    if sentiment is None:
#        print("Sentiment score: N/A")
#    else:
#        print(f"Sentiment score: {sentiment:.2f}")
#
#    return {
#        "title": book["title"],
#        "rating_10": rating_10,
#        "ratings_count": count,
#        "sentiment": sentiment
#    }






OMDB_API_KEY = "f73a0372"

def get_rating(imdb_id):
    if not imdb_id:
        return None

    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
    data = requests.get(url).json()

    if data.get("imdbRating") and data["imdbRating"] != "N/A":
        return float(data["imdbRating"])

    return None


def compare_book_vs_adaptations(book_title):
    print(f"\n📚 Book: {book_title}")

    real_book_data = analyze_book(book_title)

    book_qid = get_wikidata_id(book_title)
    novel_qid = get_novel_qid(book_title)

    if not book_qid and not novel_qid:
        print("Book not found in Wikidata.")
        return

    print(f"Wikidata ID: {book_qid}")
    print(f"Wikidata novel ID: {novel_qid}")

    adaptations = get_adaptations_wikidata(book_qid)
#    novel_adaptations = get_adaptations_wikidata(novel_qid)
    derivations = get_derivative_works(book_qid)

    if not adaptations:
        print("No book adaptations found via P144.")
        return

    print("\n🎬 Adaptations (Wikidata P144):")

    scored = []

    for a in adaptations:
        rating = get_rating(a["imdb_id"])
        if rating:
            scored.append((a["title"], rating))

# Derivations code if interested in exploring works that are based on or inspired by the original
# book, which may not be direct adaptations but still relevant to the discussion. 
# Uncomment if you want to include these as well.
#    for a in derivations:
#        rating = get_rating(a["imdb_id"])
#        if rating:
#            scored.append((a["title"], rating))

    scored.sort(key=lambda x: x[1], reverse=True)

    print("\n🏆 Ranked adaptations:")
    for title, rating in scored:
        print(f"{title}: {rating}/10")


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    
    properties_to_check = [
        "Dune",
        "Goodfellas",
        "The Lord of the Rings",
        "The Great Gatsby",
        "The Shining",
    ]

    property_to_check = properties_to_check[0]  # Change index to test different books
    compare_book_vs_adaptations(property_to_check)