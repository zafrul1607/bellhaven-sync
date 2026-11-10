# Bellhaven CRM Ownership Reconciliation

### Python | REST API | Web Scraping | Fuzzy Matching | Streamlit | SQLite

## Project Overview

This project is a CRM data reconciliation application designed to identify and correct ownership discrepancies between Bellhaven Senior Living's website and its CRM records.

Senior care facilities are frequently acquired, renamed, or transferred between parent companies, making it challenging to maintain accurate ownership information. The goal of this project is to identify inconsistencies, provide supporting evidence, and allow a human reviewer to approve or reject corrections before they are applied to the CRM.

I built the application using Python, API integration, web scraping, fuzzy matching, and a Streamlit review dashboard.

## Key Features

- **Web Scraping:** Collects facility names, addresses, ZIP codes, and care offerings from Bellhaven's website.
- **CRM API Integration:** Retrieves CRM accounts using authenticated REST API requests and pagination.
- **Data Standardization:** Normalizes facility names, addresses, and ZIP codes for comparison.
- **Fuzzy Matching:** Identifies potential matches even when facility names or addresses are inconsistent.
- **Discrepancy Detection:** Flags incorrect parent companies, outdated names, possible duplicates, unresolved facilities, and potentially stale CRM accounts.
- **Review Dashboard:** Displays website and CRM evidence for human verification.
- **Approval Workflow:** Supports reviewer decisions and verified parent-company updates through the CRM API.
- **Decision Tracking:** Uses SQLite to preserve review decisions and recorded update outcomes.
- **Financial Safeguards:** Checks revenue history and outstanding accounts receivable before ownership corrections.

## Data Analysis Results

The initial analysis produced the following results:

| Metric | Result |
|---|---:|
| CRM accounts retrieved | 121 |
| Website facilities extracted | 35 |
| Single-address matches | 22 |
| Multiple-account address matches | 3 |
| Facilities without exact address matches | 10 |
| Apparently correct records | 11 |
| Potential discrepancies requiring review | 24 |
| Potentially stale Bellhaven accounts | 4 |

These figures represent the initial reconciliation results. Flagged discrepancies require verification before corrective actions are taken.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application development |
| Requests | REST API communication |
| BeautifulSoup | Website data extraction |
| Pandas | CRM data analysis |
| RapidFuzz | Name and address similarity matching |
| Streamlit | Interactive review dashboard |
| SQLite | Persistent review and action records |
| Python-dotenv | Environment variable management |
| Git & GitHub | Version control and project sharing |

## How the System Works

**1. Data Collection**

The application scrapes Bellhaven's community pages and retrieves CRM accounts through the provided API.

**2. Data Processing**

Facility names, addresses, and ZIP codes are standardized to improve consistency between the two datasets.

**3. Record Matching**

The matching engine prioritizes matching physical addresses and uses fuzzy similarity scores to identify additional candidates. Scores are used to prioritize investigation, not as automatic proof of a match.

**4. Discrepancy Detection**

Potential issues are classified into categories including incorrect ownership, outdated names, possible duplicates, and missing or stale records.

**5. Human Review**

A Streamlit application displays the supporting evidence and allows reviewers to investigate findings, record decisions, and approve supported corrections.

**6. CRM Updates**

The implemented write-back workflow supports verified, non-CHOW parent-company corrections. Approved updates are sent through the CRM API, followed by verification against the updated record.

## Change of Ownership (CHOW) Safeguards

The assessment includes an important business rule involving financial history.

If an account has both historical revenue and positive outstanding accounts receivable, its original record must be preserved during a parent-company change.

The required approach is to create a replacement account under the correct parent and link the old record using `chow_current_account`.

If this financial condition is not met, the existing account may be eligible for direct re-parenting.

The application checks these conditions and blocks direct re-parenting when CHOW preservation is required. The complete automated replacement-account workflow remains a future enhancement.



