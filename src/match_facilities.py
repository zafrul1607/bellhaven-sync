
import json
import re
from pathlib import Path

from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


# Load our two datasets
def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as file:
        return json.load(file)


website = load_json("website_facilities.json")
crm = load_json("crm_accounts.json")


# Standardize text for comparison
def normalize(text):
    text = str(text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


# Standardize common street abbreviations
def normalize_street(text):
    replacements = {
        "rd": "road",
        "st": "street",
        "ave": "avenue",
        "blvd": "boulevard",
        "dr": "drive",
        "ln": "lane",
        "ct": "court",
        "pkwy": "parkway",
        "hwy": "highway"
    }

    words = normalize(text).split()
    words = [replacements.get(word, word) for word in words]

    return " ".join(words)


def normalize_zip(value):
    match = re.search(r"\d{5}", str(value or ""))
    return match.group() if match else ""


# Check if two records share the same address
def exact_address_match(facility, account):
    street1 = normalize_street(facility.get("street"))
    street2 = normalize_street(account.get("billing_street"))

    zip1 = normalize_zip(facility.get("zip"))
    zip2 = normalize_zip(account.get("billing_zip"))

    state1 = normalize(facility.get("state"))
    state2 = normalize(account.get("billing_state"))

    return bool(
        street1 and zip1 and state1
        and street1 == street2
        and zip1 == zip2
        and state1 == state2
    )


# Calculate a similarity score
def calculate_score(facility, account):
    name_score = fuzz.token_sort_ratio(
        normalize(facility.get("name")),
        normalize(account.get("name"))
    )

    street_score = fuzz.ratio(
        normalize_street(facility.get("street")),
        normalize_street(account.get("billing_street"))
    )

    city_score = fuzz.ratio(
        normalize(facility.get("city")),
        normalize(account.get("billing_city"))
    )

    zip_score = 100 if (
        normalize_zip(facility.get("zip"))
        and normalize_zip(facility.get("zip"))
        == normalize_zip(account.get("billing_zip"))
    ) else 0

    state_score = 100 if (
        normalize(facility.get("state"))
        and normalize(facility.get("state"))
        == normalize(account.get("billing_state"))
    ) else 0

    score = (
        street_score * 0.50
        + name_score * 0.30
        + city_score * 0.10
        + zip_score * 0.05
        + state_score * 0.05
    )

    return round(score, 2)


# Exclude parent-company accounts from facility matching
facility_accounts = [
    account for account in crm
    if "(parent account)" not in str(
        account.get("name") or ""
    ).lower()
]


# Generate candidate matches
results = []

for facility in website:

    exact_matches = [
        account for account in facility_accounts
        if exact_address_match(facility, account)
    ]

    if len(exact_matches) == 1:
        match_type = "single_address_match"
        pool = exact_matches

    elif len(exact_matches) > 1:
        match_type = "multiple_accounts_same_address"
        pool = exact_matches

    else:
        match_type = "needs_manual_review"
        pool = facility_accounts

    ranked = sorted(
        pool,
        key=lambda account: calculate_score(facility, account),
        reverse=True
    )

    candidates = []

    for account in ranked[:5]:
        candidates.append({
            "account_id": account.get("account_id"),
            "crm_name": account.get("name"),
            "parent_id": account.get("parent_id"),
            "parent_name": account.get("parent_name"),
            "billing_street": account.get("billing_street"),
            "billing_city": account.get("billing_city"),
            "billing_state": account.get("billing_state"),
            "billing_zip": account.get("billing_zip"),
            "lifetime_revenue": account.get("lifetime_revenue"),
            "outstanding_ar": account.get("outstanding_ar"),
            "score": calculate_score(facility, account)
        })

    results.append({
        "website_facility": facility,
        "match_type": match_type,
        "candidates": candidates
    })


# Save candidate matches
output = DATA_DIR / "match_candidates.json"

with open(output, "w", encoding="utf-8") as file:
    json.dump(results, file, indent=4)


# Display summary
print("=== FACILITY MATCHING SUMMARY ===")

for category in [
    "single_address_match",
    "multiple_accounts_same_address",
    "needs_manual_review"
]:
    count = sum(r["match_type"] == category for r in results)
    print(f"{category}: {count}")

print(f"\nTotal website facilities processed: {len(results)}")
print(f"CRM facility accounts considered: {len(facility_accounts)}")
print(f"Saved results to: {output.name}")


# Show facilities that require further investigation
print("\n=== FACILITIES REQUIRING REVIEW ===")

for result in results:
    if result["match_type"] != "single_address_match":
        print(f"\nWebsite: {result['website_facility']['name']}")
        print(f"Reason: {result['match_type']}")

        for candidate in result["candidates"][:3]:
            print(
                f"  Candidate: {candidate['crm_name']} "
                f"| Score: {candidate['score']} "
                f"| Parent: {candidate['parent_name']}"
            )
