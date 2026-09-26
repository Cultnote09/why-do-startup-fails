# Why startups fail

Power BI report on 1,028 IdeaProof failure write-ups, coded sector postmortems, and a summarized Crunchbase company registry.

## Open the report

1. Install [Power BI Desktop](https://www.microsoft.com/power-bi).
2. Open `Startup Failure Analysis.pbip`.
3. If the charts are empty, choose **Refresh** on the Home ribbon.

The model reads the CSV files in `powerbi/data`. On this machine that folder is set in the **DataFolder** parameter:

`C:/Users/pavni/Desktop/startup analysis/powerbi/data`

After cloning the repo somewhere else, update that parameter before refreshing:

1. **Home > Transform data > Manage parameters**.
2. Set **DataFolder** to the full path of `powerbi/data` in your clone. Use forward slashes.
3. Close and apply, then refresh.

## What is in the report

- **Overview** — startup count, funding, median lifespan, failure themes, industry, and prominence.
- **Funding and timing** — funding by industry in billions, failures by year, and top countries.
- **Case browser** — one row per write-up, including the reason, the lesson, and the source link. Funding on this page is in millions of dollars per company.
- **Sector postmortems** — driver flags from the sector spreadsheets. A company can have more than one flag.
- **Company registry** — outcome mix from the Crunchbase extract. This is a different population from the failure write-ups.

Funding totals on the cards are in billions. The total is dominated by a few mega-rounds in the source labels.
