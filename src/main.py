
import os
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

# Step 1: Locate the project and load credentials
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

API_TOKEN = os.getenv("BELLHAVEN_API_TOKEN")

API_URL = "https://analyst-assessment-production.up.railway.app/api/v1"


# Step 2: Retrieve all CRM accounts
def get_all_accounts():

    if not API_TOKEN:
        raise ValueError("API token not found in .env file")

    all_accounts = []
    page = 1
    page_size = 50

    while True:

        response = requests.get(
            f"{API_URL}/accounts",
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            params={
                "page": page,
                "page_size": page_size
            },
            timeout=30
        )

        response.raise_for_status()

        result = response.json()

        accounts = result["data"]
        total = result["total"]

        if not isinstance(accounts, list):
            raise ValueError("Unexpected CRM response format")

        all_accounts.extend(accounts)

        print(f"Page {page}: Retrieved {len(accounts)} accounts")

        if len(all_accounts) >= total:
            break

        if not accounts:
            raise RuntimeError("Pagination stopped before all accounts were retrieved")

        page += 1

    if len(all_accounts) != total:
        raise RuntimeError("Retrieved account count does not match CRM total")

    return all_accounts


# Step 3: Save the accounts locally
def save_accounts(accounts):

    output_path = PROJECT_ROOT / "data" / "crm_accounts.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(accounts, file, indent=4)

    print(f"Saved {len(accounts)} accounts to data/crm_accounts.json")


# Step 4: Run the program
if __name__ == "__main__":

    accounts = get_all_accounts()

    print(f"\nTotal accounts retrieved: {len(accounts)}")

    save_accounts(accounts)

    print("CRM data extraction completed successfully!")
