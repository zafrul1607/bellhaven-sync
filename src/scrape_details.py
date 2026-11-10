
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Locate our project
PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "community_links.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "website_facilities.json"

# Known care offerings on Bellhaven's website
CARE_TYPES = [
    "Assisted Living",
    "Memory Support",
    "Short-Term Rehabilitation & Nursing"
]


# Step 1: Load our previously collected facility links
with open(INPUT_FILE, "r", encoding="utf-8") as file:
    community_links = json.load(file)


# Step 2: Extract data from an individual facility page
def extract_facility(entry):

    url = entry["url"]

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Get the facility name
    heading = soup.find("h1")
    name = heading.get_text(" ", strip=True) if heading else ""

    # Extract the visible text from the website
    lines = [
        text.strip()
        for text in soup.stripped_strings
        if text.strip()
    ]

    street = ""
    city = ""
    state = ""
    zip_code = ""

    # Locate the Address section
    if "Address" in lines:
        index = lines.index("Address")

        if index + 2 < len(lines):
            street = lines[index + 1]
            location = lines[index + 2]

            # Separate city, state and ZIP
            match = re.match(
                r"^(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
                location
            )

            if match:
                city = match.group(1)
                state = match.group(2)
                zip_code = match.group(3)

    # Locate the Care Offerings section
    care_offerings = []

    if "Care Offerings" in lines:
        start = lines.index("Care Offerings") + 1
        end = start

        while end < len(lines):
            if lines[end] in ["Administrator", "Phone"]:
                break
            if "Back to all communities" in lines[end]:
                break
            end += 1

        care_text = " ".join(lines[start:end])

        for care in CARE_TYPES:
            if care.lower() in care_text.lower():
                care_offerings.append(care)

    # Return a structured facility record
    return {
        "name": name,
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "care_offerings": care_offerings,
        "source_url": url,
        "sources": entry["sources"]
    }


# Step 3: Visit every facility page
facilities = []

print("=== EXTRACTING BELLHAVEN FACILITIES ===")

for number, entry in enumerate(community_links, start=1):

    facility = extract_facility(entry)

    facilities.append(facility)

    print(f"{number}. {facility['name']}")

    # Small pause between website requests
    time.sleep(0.1)


# Step 4: Save our structured dataset
with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
    json.dump(facilities, file, indent=4)


# Step 5: Check data quality
required_fields = [
    "name", "street", "city", "state", "zip"
]

incomplete = []

for facility in facilities:
    missing = [
        field for field in required_fields
        if not facility[field]
    ]

    if not facility["care_offerings"]:
        missing.append("care_offerings")

    if missing:
        incomplete.append({
            "name": facility["name"],
            "missing": missing
        })


print("\n=== EXTRACTION SUMMARY ===")
print(f"Total facilities: {len(facilities)}")
print(f"Incomplete facilities: {len(incomplete)}")
print(f"Saved to: {OUTPUT_FILE.name}")

if incomplete:
    print("\nRecords requiring investigation:")
    for item in incomplete:
        print(item)
else:
    print("All required fields were extracted successfully!")

print("\nFirst two facility records:")
print(json.dumps(facilities[:2], indent=4))
