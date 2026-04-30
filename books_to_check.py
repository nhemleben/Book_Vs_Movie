import requests
import pandas as pd

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

QUERY = """
SELECT ?book ?bookLabel (COUNT(?adaptation) AS ?adaptationCount) WHERE {
  ?adaptation wdt:P144 ?book.

  ?book wdt:P31/wdt:P279* wd:Q7725634.  # literary work

  #FILTER NOT EXISTS { ?book wdt:P31 wd:Q4242810 }  # exclude religious text
  #FILTER NOT EXISTS { ?book wdt:P31 wd:Q9143 }     # exclude mythology

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en".
  }
}
GROUP BY ?book ?bookLabel
ORDER BY DESC(?adaptationCount)
LIMIT 10000
"""

def run_sparql(query):
    headers = {
        "User-Agent": "BookAdaptationAnalyzer/1.0 (contact: youremail@example.com)",
        "Accept": "application/sparql-results+json"
    }

    params = {"query": query}

    response = requests.get(
        WIKIDATA_ENDPOINT,
        params=params,
        headers=headers
    )

    response.raise_for_status()
    return response.json()


def parse_results(data):
    results = []

    for item in data["results"]["bindings"]:
        book = item["bookLabel"]["value"]
        count = int(item["adaptationCount"]["value"])

        wikidata_url = item["book"]["value"]

        results.append({
            "book": book,
            "adaptation_count": count,
            "wikidata": wikidata_url
        })

    return results


def main():
    print("Querying Wikidata...")

    data = run_sparql(QUERY)
    books = parse_results(data)

    df = pd.DataFrame(books)

    print("\nTop adapted books:")
    print(df.head(20))

    df.to_csv("books_with_adaptations.csv", index=False)
    print("\nSaved to books_with_adaptations.csv")


if __name__ == "__main__":
    main()