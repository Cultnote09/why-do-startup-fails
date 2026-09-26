# Why startups fail

Power BI report on why startups failed, built from three datasets. The cleaning script is `clean_data.py`. The report reads the cleaned tables in `data/processed`.

## Datasets

### 1. IdeaProof failure write-ups

- **Source:** [IdeaProof](https://ideaproof.io/). Each row links to a case page such as `https://ideaproof.io/failure/milkrun`.
- **File:** `data/raw/ideaproof-startup-failures.csv`
- **What it is:** 1,028 failed startups, with founding year, failure year, country, industry, funding label, the stated reason, and a lesson.
- **Cleaned table:** `data/processed/Failures.csv`

### 2. Sector postmortems

- **Files:** the six sector spreadsheets in `data/raw/sectors/`
- **What they are:** 409 coded cases. Each row has what the company did, how much it raised, why it failed, a takeaway, and 0/1 flags such as Giants, Competition, and Poor Market Fit.
- **Not loaded:** `data/raw/sectors/Startup Failures.csv` is only a name, sector, and years. It has no failure reason. The six sector files already carry the cases the report uses.
- **Cleaned tables:** `data/processed/SectorCases.csv` (one row per company) and `data/processed/SectorDrivers.csv` (one row per flagged driver). A company can have more than one driver.

### 3. Crunchbase company registry

- **Source:** [Startup Investments on Kaggle](https://www.kaggle.com/datasets/justinas/startup-investments), file `companies.csv`. This is a historical Crunchbase extract, not a current list of failures.
- **File:** `data/raw/crunchbase/companies.csv`. It is about 129 MB, so it is not in this repository.
- **Cleaned table:** `data/processed/Registry.csv`, already included. It rolls companies up by status, category, and country. Of 196,553 companies, 183,441 were operating, 9,394 were acquired, 1,134 reached an IPO, and 2,584 were closed.

These three sources are different populations. The failure write-ups and the sector postmortems are not the same companies as the Crunchbase registry.

## What the cleaning script does

`python clean_data.py` writes the four processed tables.

For the IdeaProof file it:

- trims text and standardizes country names (`USA` and `UK` become United States and United Kingdom)
- groups the free-text industry into 12 industry groups, plus Other
- groups the written failure reason into a theme, using the first matching rule in `clean_data.py`
- reads funding from the text label (`$75M`, `$1.7B`). Labels about assets are ignored. If the label cannot be read, the numeric column is used
- keeps lifespan only when failure year minus founding year is between 0 and 45
- drops founding years outside 1950–2026 and failure years outside 1990–2026

For the sector files it keeps one row per company and expands each driver flag of 1 into its own row.

For Crunchbase, if `companies.csv` is present, it keeps rows where `entity_type` is Company, maps status to Operating, Acquired, Closed, or IPO, and keeps the 12 largest categories plus Other. If the file is missing, `Registry.csv` is left as it is.

## Open the report

1. Install [Power BI Desktop](https://www.microsoft.com/power-bi).
2. Open `Startup Failure Analysis.pbip`.
3. If the charts are empty, choose **Refresh** on the Home ribbon.

The model reads `data/processed`. On this machine the **DataFolder** parameter is:

`C:/Users/pavni/Desktop/startup analysis/data/processed`

After cloning the repo somewhere else:

1. **Home > Transform data > Manage parameters**.
2. Set **DataFolder** to the full path of `data/processed` in your clone. Use forward slashes.
3. Close and apply, then refresh.

## Report pages

- **Overview** — count, funding in billions, median lifespan, failure themes, industry, and prominence.
- **Funding and timing** — funding by industry, failures by year, and the countries with the most write-ups.
- **Case browser** — reason, lesson, and source link. Funding on this page is in millions of dollars per company.
- **Sector postmortems** — driver flags. Giants and competition are the most common.
- **Company registry** — the Crunchbase outcome mix.

The funding total is about $491 billion in the source labels. A few mega-rounds pull that number up. The median disclosed funding is $100 million, and the median lifespan is 7 years.
