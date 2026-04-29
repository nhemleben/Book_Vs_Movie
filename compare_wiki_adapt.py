import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

OMDB_API_KEY = "f73a0372"

# ----------------------------
# Wikipedia Parse API
# ----------------------------
def get_wikipedia_sections(title):
    url = "https://en.wikipedia.org/w/api.php"

    params = {
        "action": "parse",
        "page": title,
        "format": "json",
        "prop": "sections"
    }

    r = requests.get(url, params=params)
    data = r.json()

    if "error" in data:
        return None

    return data["parse"]["sections"]

# ----------------------------
# Get full section HTML
# ----------------------------
def get_section_html(title, section_index):
    url = "https://en.wikipedia.org/w/api.php"

    params = {
        "action": "parse",
        "page": title,
        "format": "json",
        "prop": "text",
        "section": section_index
    }

    r = requests.get(url, params=params)
    try:
        data = r.json()
    except ValueError:
        print(r.status_code)
        print("Error parsing JSON:", r.text)
        return None

    if "error" in data:
        return None

    html = data["parse"]["text"]["*"]
    return html

# ----------------------------
# Extract adaptation-related sections
# ----------------------------
def find_adaptation_sections(title):
    sections = get_wikipedia_sections(title)

    if not sections:
        return []

    keywords = ["adapt", "film", "television", "stage", "radio"]

    relevant = []
    for sec in sections:
        sec_title = sec["line"].lower()

        if any(k in sec_title for k in keywords):
            relevant.append(sec["index"])

    return relevant

# ----------------------------
# Parse adaptation names from HTML
# ----------------------------
def extract_titles_from_html(html):
    soup = BeautifulSoup(html, "html.parser")

    titles = set()

    for link in soup.find_all("a"):
        t = link.get("title")
        if t and not t.startswith("Help:"):
            titles.add(t)

    return list(titles)

# ----------------------------
# OMDb lookup
# ----------------------------
def get_movie_rating(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={OMDB_API_KEY}"
    r = requests.get(url).json()

    if r.get("imdbRating") and r["imdbRating"] != "N/A":
        return {
            "title": r["Title"],
            "rating": float(r["imdbRating"])
        }

    return None

# ----------------------------
# Main function
# ----------------------------
def get_adaptations(title):
    sections = find_adaptation_sections(title)

    if not sections:
        print("No adaptation sections found.")
        return []

    all_adaptations = set()

    for sec in sections:
        html = get_section_html(title, sec)
        if html:
            titles = extract_titles_from_html(html)
            all_adaptations.update(titles)

    return list(all_adaptations)

# ----------------------------
# Compare logic
# ----------------------------
def compare(title):
    print(f"\n📚 Book: {title}")

    adaptations = get_adaptations(title)

    if not adaptations:
        print("No adaptations found.")
        return

    print("\n🎬 Adaptations found:")
    for a in adaptations:
        print("-", a)

    print("\n📊 Ratings:")

    for a in adaptations:
        movie = get_movie_rating(a)
        if movie:
            print(f"{movie['title']}: {movie['rating']}/10")

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    compare("Dune")