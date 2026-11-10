
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://analyst-assessment-production.up.railway.app"

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Download a web page and read its HTML
def get_page(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


# Find links pointing to individual communities
def find_community_links(soup):
    links = set()

    for tag in soup.find_all("a", href=True):
        url = urljoin(BASE_URL, tag["href"])
        path = urlparse(url).path

        if path.startswith("/communities/"):
            links.add(url.split("#")[0])

    return links


# Visit every page in the community directory
directory_links = set()

page_url = urljoin(BASE_URL, "/communities")
visited_pages = set()

while page_url and page_url not in visited_pages:
    visited_pages.add(page_url)

    soup = get_page(page_url)

    links = find_community_links(soup)
    directory_links.update(links)

    print(f"Directory page: found {len(links)} facilities")

    # Find the next page, if one exists
    next_link = None

    for tag in soup.find_all("a", href=True):
        if tag.get_text(strip=True).lower().startswith("next"):
            next_link = tag
            break

    if next_link:
        page_url = urljoin(BASE_URL, next_link["href"])
    else:
        page_url = None


# Also check the homepage for additional facilities
homepage = get_page(BASE_URL)
homepage_links = find_community_links(homepage)

extra_links = homepage_links - directory_links

# Combine all discovered facility links
all_links = sorted(directory_links | homepage_links)

records = []

for url in all_links:
    sources = []

    if url in directory_links:
        sources.append("directory")

    if url in homepage_links:
        sources.append("homepage")

    records.append({
        "url": url,
        "sources": sources
    })


# Save our results
output_file = PROJECT_ROOT / "data" / "community_links.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(records, file, indent=4)


print("\n=== SCRAPING SUMMARY ===")
print(f"Directory facilities: {len(directory_links)}")
print(f"Additional homepage facilities: {len(extra_links)}")
print(f"Total unique facilities: {len(all_links)}")
print(f"Saved to: {output_file.name}")
