import requests
from difflib import SequenceMatcher

OMDB_API_KEY = "f73a0372"

# ----------------------------
# Helpers
# ----------------------------
def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_book_rating(rating_5_scale):
    return rating_5_scale * 2  # convert /5 → /10

# ----------------------------
# Step 1: Get book info
# ----------------------------
def get_book(title):
    url = f"https://www.googleapis.com/books/v1/volumes?q=intitle:{title}"
    data = requests.get(url).json()

    if "items" not in data:
        return None

    book = data["items"][0]["volumeInfo"]

    return {
        "title": book.get("title"),
        "authors": book.get("authors", []),
        "rating": book.get("averageRating", None)
    }


# ----------------------------
# Step 2: Find adaptations
# ----------------------------
def search_adaptations(book_title):
    url = f"http://www.omdbapi.com/?s={book_title}&apikey={OMDB_API_KEY}"
    data = requests.get(url).json()

    if "Search" not in data:
        return []

    results = []
    for item in data["Search"]:
        title = item["Title"]

        # Filter by similarity (avoids junk results)
        if similarity(book_title, title) > 0.5:
            details = get_movie_details(item["imdbID"])
            if details:
                results.append(details)

    return results

def get_movie_details(imdb_id):
    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
    data = requests.get(url).json()

    try:
        return {
            "title": data["Title"],
            "year": data["Year"],
            "rating": float(data["imdbRating"])
        }
    except:
        return None

# ----------------------------
# Step 3: Compare
# ----------------------------
def compare(title):
    book = get_book(title)

    if not book:
        print("Book not found.")
        return

    print(f"\n📚 Book: {book['title']}")
    print(f"Authors: {', '.join(book['authors'])}")

    if book["rating"]:
        book_rating = normalize_book_rating(book["rating"])
        print(f"Book Rating: {book_rating:.1f}/10")
    else:
        print("Book rating not available.")
        return

    adaptations = search_adaptations(book["title"])

    if not adaptations:
        print("\nNo adaptations found.")
        return

    print("\n🎬 Adaptations:")
    for a in adaptations:
        print(f"- {a['title']} ({a['year']}): {a['rating']}/10")

    print("\n🏆 Comparison:")
    for a in adaptations:
        diff = a["rating"] - book_rating

        if diff > 0:
            print(f"{a['title']} is rated HIGHER by {diff:.2f}")
        else:
            print(f"{a['title']} is rated LOWER by {abs(diff):.2f}")

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    compare("Dune")