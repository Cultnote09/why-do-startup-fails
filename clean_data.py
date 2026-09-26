# -*- coding: utf-8 -*-
"""Clean the raw startup-failure files into the tables Power BI imports.

Run from the repository root:

    python clean_data.py

Inputs (see README for the source of each file):

    data/raw/ideaproof-startup-failures.csv
    data/raw/sectors/*.csv
    data/raw/crunchbase/companies.csv   optional, too large to store on GitHub

Outputs, written to data/processed/:

    Failures.csv        one row per IdeaProof write-up
    SectorCases.csv     one row per coded sector postmortem
    SectorDrivers.csv   one row per postmortem x flagged driver
    Registry.csv        Crunchbase companies rolled up by status, category, country

Startup Failures.csv in the sectors folder is only a name index. It has no
failure reason, so this script does not load it. The six sector files already
include the reason text and the 0/1 driver flags.

If companies.csv is absent, the existing Registry.csv is left unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
SECTOR_DIR = RAW / "sectors"
CRUNCHBASE_PATH = RAW / "crunchbase" / "companies.csv"
OUT = ROOT / "data" / "processed"

IDEAPROOF_PATH = RAW / "ideaproof-startup-failures.csv"

# These six files have the written reason and the driver flags.
# "Startup Failures.csv" is intentionally absent from this list.
SECTOR_FILES = [
    "Startup Failure (Finance and Insurance).csv",
    "Startup Failure (Food and services).csv",
    "Startup Failure (Health Care).csv",
    "Startup Failure (Manufactures).csv",
    "Startup Failure (Retail Trade).csv",
    "Startup Failures (Information Sector).csv",
]

SECTOR_SHORT = {
    "Retail Trade": "Retail",
    "Information": "Information",
    "Manufacturing": "Manufacturing",
    "Health Care": "Health care",
    "Finance and Insurance": "Finance",
    "Accommodation and Food Services": "Food service",
    "Professional Scientific and Technical Services": "Professional services",
}

TEXT_COLUMNS = {
    "Name",
    "Sector",
    "Years of Operation",
    "What They Did",
    "How Much They Raised",
    "Why They Failed",
    "Takeaway",
}

# First matching rule wins. Patterns are applied to the industry string.
INDUSTRY_RULES = [
    ("Crypto", r"crypto|bitcoin|blockchain|\bnft\b|web3"),
    ("Fintech & insurance", r"fintech|insur|neobank|\bbank|lend|payment|\bbnpl\b|financ|wealth|trading|crowdfunding"),
    ("Healthcare & biotech", r"health|bio|pharma|medical|medtech|therap|clinic|hospital|\bcare\b"),
    ("Food & grocery", r"food|grocery|restaurant|meal|kitchen|beverage|quick[\s-]?commerce|\bagri|agtech|farm"),
    ("Mobility & logistics", r"vehicle|automotive|electric vehicle|\bevs?\b|mobility|\bride\b|freight|logistic|transport|scooter|aviation|airline|autonomous|robotaxi|\bcars?\b|truck|delivery|\btravel\b|flight"),
    ("Energy & climate", r"energy|solar|climate|cleantech|clean tech|battery|carbon|charging|hydrogen|utilit"),
    ("Real estate", r"proptech|real estate|housing|rent-to-own|construction|\bproperty\b"),
    ("Hardware & robotics", r"hardware|robot|manufactur|semiconductor|drone|electronics|\bchip\b|\bdevice\b|\biot\b|\bspace\b|aerospace|wearable|industrial|chemical"),
    ("Media & social", r"media|social|content|\bnews\b|gaming|\bgame\b|stream|entertainment|music|\bvideo\b|communication|virtual event|\breview|telecom|dating|\bevents?\b"),
    ("Education", r"edtech|education|learning|\btutor"),
    ("Software & AI", r"software|\bsaas\b|information technology|\bcloud\b|\bdata\b|cyber|security|\bai\b|artificial|devtool|developer|internet|productivity|marketing|martech|analytics|mobile app|\bhr\b|workforce|legal|geospatial|\bdesign\b|enterprise tech|customer service|augmented|on-demand"),
    ("Commerce & retail", r"e-?commerce|retail|marketplace|shopping|\bdtc\b|\bd2c\b|beauty|rental|\bconsumer\b"),
]

# First matching rule wins. Patterns are applied to the failure-reason text.
THEME_RULES = [
    ("Fraud or governance", r"fraud|scandal|convict|embezzl|mismanag|governance|founder|\bsec\b|probe|lawsuit|toxic|ponzi|fake pre-order|\bfake\b"),
    ("Regulatory or legal", r"regulat|banned|compliance|licen[cs]e|antitrust|illegal|gdpr|privacy|\bpolicy\b|sanction|unauthorized"),
    ("Acquired or shut by owner", r"acqui|sunset|pulled the plug|write-? ?down|wrote down|\bparent\b|gutt|wound down|liquidation"),
    ("Public-market collapse", r"stock collapse|stock decline|stock fell|failed ipo|\bspac\b|short report|take-private|impairment"),
    ("Macro, timing, or shock", r"\brates?\b|covid|pandemic|recession|downturn|\bmacro\b|inflation|market crash|tariff|crypto winter|\bwinter\b|too early|too late|prematur|\btiming\b|market cooled|climate risk|spending pullback"),
    ("Outcompeted", r"compet|outcompeted|lost to|market share|amazon|google|facebook|incumbent|disruption|obsolesc|differentiat|commodit|overcrowded|lack of (?:differentiation|moat)"),
    ("Unit economics", r"unit economic|unprofit|margin|\bburn|ltv|cac|high cost|economics|\bdebt\b|capital-intensive|capex|unsustainable|profitab|race to the bottom|race to bottom|couldn.?t cover|could not cover|\bcosts?\b|(?<!stock )collaps|model (?:collapse|collapsed|proved|broke|failed|unproven)|inventory|economically|not cheaper|no business model|\bpricing\b"),
    ("Ran out of cash or could not raise", r"could not raise|failed to raise|unable to raise|ran out|runway|bankrupt|chapter 11|insolven|cash crunch|out of cash|no cash|liquidity|underfund|lack of (?:capital|funding|cash)"),
    ("Could not scale", r"failed to scale|couldn.?t scale|could not scale|slow growth|scaling|failed to grow|beyond niche|overfund|reach scale|international expansion"),
    ("No market need", r"no market|product[- ]market|lack of demand|low adoption|no demand|zero commercial|no clear use|use case|market mismatch|didn.?t meet|did not meet|\bniche\b|no one wanted|adoption|\bdemand\b|failed commercialization|lack of (?:traction|customers|users|market)|\bpmf\b|too small|looking for a problem|solution in search"),
    ("Monetization", r"monetiz|ad revenue|revenue collapse|couldn.t charge|no revenue|failed to monetize|revenue never"),
    ("Product or execution failed", r"pivot|never produced|overpromis|glitch|execution|failed to launch|failed to deliver|failed to ship|technical|didn.?t work|not work|\bbug\b|over-engineer|complex product|couldn.?t replace|could not replace|lack of focus"),
]
THEME_ORDER = [name for name, _ in THEME_RULES] + ["Other"]

COUNTRY_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "u.s": "United States",
    "u.s.a": "United States",
    "united states": "United States",
    "uk": "United Kingdom",
    "u.k": "United Kingdom",
    "united kingdom": "United Kingdom",
    "uae": "United Arab Emirates",
    "u.a.e": "United Arab Emirates",
    "south korea": "South Korea",
    "korea": "South Korea",
    "republic of korea": "South Korea",
    "russia": "Russia",
    "czech republic": "Czechia",
    "czechia": "Czechia",
}

FAILURE_COLUMNS = [
    "Write-up",
    "Startup",
    "Slug",
    "Country",
    "Country (top 12)",
    "Industry",
    "Industry Group",
    "Prominence",
    "Category",
    "Founded Year",
    "Failed Year",
    "Lifespan Years",
    "Failure Theme",
    "Theme Sort",
    "Failure Reason",
    "Lesson",
    "Funding Label",
    "Funding USD",
    "Peak Valuation USD",
    "Employees At Peak",
    "Investors",
    "Url",
]

CASE_COLUMNS = [
    "Startup",
    "Sector",
    "What They Did",
    "Why They Failed",
    "Takeaway",
    "Raised Label",
    "Raised USD",
    "Start Year",
    "End Year",
    "Lifespan Years",
    "Driver Count",
]

DRIVER_COLUMNS = [
    "Startup",
    "Sector",
    "Driver",
    "Why They Failed",
    "Takeaway",
]

REGISTRY_COLUMNS = [
    "Status",
    "Category Group",
    "Country",
    "Companies",
    "Funding USD",
]


def squash(value):
    """Collapse whitespace. Empty strings become missing values."""
    if not isinstance(value, str):
        return value
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def classify(value, rules):
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
    for name, pattern in rules:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return name
    return "Other"


def normalize_country(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Unknown"
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none", "null"}:
        return "Unknown"
    return COUNTRY_ALIASES.get(raw.lower().strip("."), raw)


def parse_money_label(label):
    """Read amounts such as '$75M' or '$1.7B' from a text label.

    Returns US dollars. Labels that describe assets, or that have no amount,
    return None. A euro or pound sign is stripped before the number is read,
    so the figure is the number printed in the source, not a converted value.
    """
    if not isinstance(label, str) or not label.strip():
        return None
    if re.search(r"\bassets?\b", label, flags=re.IGNORECASE):
        return None
    if re.search(r"\bN/?A\b", label, flags=re.IGNORECASE):
        return None
    text = "".join(ch if ord(ch) < 128 else " " for ch in label)
    text = text.replace("$", " ").replace("EUR", " ").replace("GBP", " ")
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*([BMK])\b", text, flags=re.IGNORECASE)
    if not match:
        if re.fullmatch(r"[\s]*0(?:\.0+)?[\s]*", text.strip()):
            return 0.0
        return None
    number = float(match.group(1).replace(",", ""))
    return number * {"B": 1e9, "M": 1e6, "K": 1e3}[match.group(2).upper()]


def parse_funding(label, numeric):
    """Prefer the text label. Fall back to the numeric column when the label fails.

    In the IdeaProof file the numeric column is usually already in millions.
    A few rows stored the raw currency amount instead. Values up to 30,000 are
    treated as millions. Larger values are treated as dollars.
    """
    if isinstance(label, str) and re.search(r"\bassets?\b", label, flags=re.IGNORECASE):
        return None
    parsed = parse_money_label(label)
    if parsed is not None:
        return parsed
    if pd.isna(numeric):
        return None
    value = float(numeric)
    if value < 0:
        return None
    if value <= 30000:
        return value * 1e6
    return value


def parse_years(text):
    """Read a span such as '3 (2010-2013)' or '2015-2019'."""
    if not isinstance(text, str):
        return None, None, None
    match = re.search(r"(\d{4})\s*[-–]\s*(\d{4})", text)
    if not match:
        return None, None, None
    start, end = int(match.group(1)), int(match.group(2))
    span = end - start
    if span < 0 or span > 45:
        span = None
    return start, end, span


def nullable_int(series):
    return pd.to_numeric(series, errors="coerce").round().astype("Int64")


def write_csv(frame, filename, columns):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / filename
    frame.loc[:, columns].to_csv(path, index=False, encoding="utf-8", lineterminator="\n", float_format="%.2f")
    return path


def load_failures():
    raw = pd.read_csv(IDEAPROOF_PATH)
    frame = pd.DataFrame()
    frame["Startup"] = raw["name"].map(squash)
    frame["Slug"] = raw["slug"].map(squash)
    duplicated = frame["Startup"].duplicated(keep=False)
    frame["Write-up"] = frame["Startup"]
    frame.loc[duplicated, "Write-up"] = (
        frame.loc[duplicated, "Startup"].fillna("") + " (" + frame.loc[duplicated, "Slug"].fillna("") + ")"
    )
    frame["Country"] = raw["country"].map(normalize_country)
    frame["Industry"] = raw["industry"].map(squash)
    frame["Industry Group"] = frame["Industry"].map(lambda value: classify(value, INDUSTRY_RULES))
    prominence = {"mega": "Mega", "major": "Major", "notable": "Notable", "recent": "Recent"}
    frame["Prominence"] = raw["category"].astype(str).str.lower().map(prominence).fillna("Other")
    frame["Category"] = raw["category"].map(squash)
    frame["Founded Year"] = nullable_int(raw["founded"])
    frame["Failed Year"] = nullable_int(raw["failed"])
    frame.loc[(frame["Founded Year"] < 1950) | (frame["Founded Year"] > 2026), "Founded Year"] = pd.NA
    frame.loc[(frame["Failed Year"] < 1990) | (frame["Failed Year"] > 2026), "Failed Year"] = pd.NA
    lifespan = frame["Failed Year"].astype("Float64") - frame["Founded Year"].astype("Float64")
    frame["Lifespan Years"] = lifespan.where((lifespan >= 0) & (lifespan <= 45)).round().astype("Int64")
    frame["Failure Theme"] = raw["failure_reason"].map(lambda value: classify(value, THEME_RULES))
    frame["Theme Sort"] = frame["Failure Theme"].map(
        {name: index for index, name in enumerate(THEME_ORDER, start=1)}
    ).astype("Int64")
    frame["Failure Reason"] = raw["failure_reason"].map(squash)
    frame["Lesson"] = raw["lesson"].map(squash)
    frame["Funding Label"] = raw["funding_raised_label"].map(squash)
    frame["Funding USD"] = [
        parse_funding(label, numeric)
        for label, numeric in zip(raw["funding_raised_label"], raw["funding_raised_usd_millions"])
    ]
    frame["Peak Valuation USD"] = raw["peak_valuation"].map(parse_money_label)
    employees = pd.to_numeric(raw["employees_at_peak"], errors="coerce")
    frame["Employees At Peak"] = employees.where((employees > 0) & (employees <= 100000)).round().astype("Int64")
    frame["Investors"] = raw["investors"].map(squash)
    frame["Url"] = raw["url"].map(squash)
    top_countries = frame.loc[frame["Country"] != "Unknown", "Country"].value_counts().head(12).index
    frame["Country (top 12)"] = frame["Country"].where(frame["Country"].isin(top_countries), "Other")
    frame.loc[frame["Country"].eq("Unknown"), "Country (top 12)"] = "Unknown"
    return frame.loc[:, FAILURE_COLUMNS]


def load_sectors():
    frames = []
    for filename in SECTOR_FILES:
        part = pd.read_csv(SECTOR_DIR / filename)
        part.columns = [str(column).strip() for column in part.columns]
        frames.append(part)
    raw = pd.concat(frames, ignore_index=True, sort=False)

    driver_cols = []
    for column in raw.columns:
        if column in TEXT_COLUMNS:
            continue
        numeric = pd.to_numeric(raw[column], errors="coerce")
        values = set(numeric.dropna().unique().tolist())
        if values and values <= {0, 1, 0.0, 1.0}:
            driver_cols.append(column)
            raw[column] = numeric.fillna(0).astype(int)

    cases = pd.DataFrame()
    cases["Startup"] = raw["Name"].map(squash)
    cases["Sector"] = raw["Sector"].map(lambda value: SECTOR_SHORT.get(squash(value) or "", squash(value)))
    cases["What They Did"] = raw["What They Did"].map(squash)
    cases["Why They Failed"] = raw["Why They Failed"].map(squash)
    cases["Takeaway"] = raw["Takeaway"].map(squash)
    cases["Raised Label"] = raw["How Much They Raised"].map(squash)
    cases["Raised USD"] = raw["How Much They Raised"].map(parse_money_label)
    years = raw["Years of Operation"].map(parse_years)
    cases["Start Year"] = nullable_int(years.map(lambda item: item[0]))
    cases["End Year"] = nullable_int(years.map(lambda item: item[1]))
    cases["Lifespan Years"] = nullable_int(years.map(lambda item: item[2]))
    cases["Driver Count"] = raw[driver_cols].sum(axis=1).astype("Int64")
    cases = cases.dropna(subset=["Startup"]).drop_duplicates(["Startup", "Sector"])

    long = raw[["Name", "Sector", "Why They Failed", "Takeaway"] + driver_cols].copy()
    long["Startup"] = long["Name"].map(squash)
    long["Sector"] = long["Sector"].map(lambda value: SECTOR_SHORT.get(squash(value) or "", squash(value)))
    long = long.drop(columns=["Name"]).melt(
        id_vars=["Startup", "Sector", "Why They Failed", "Takeaway"],
        value_vars=driver_cols,
        var_name="Driver",
        value_name="Flag",
    )
    long = long[long["Flag"] == 1].drop(columns=["Flag"])
    long["Why They Failed"] = long["Why They Failed"].map(squash)
    long["Takeaway"] = long["Takeaway"].map(squash)
    long = long.dropna(subset=["Startup"])
    return cases.loc[:, CASE_COLUMNS], long.loc[:, DRIVER_COLUMNS].reset_index(drop=True), driver_cols


def load_registry():
    raw = pd.read_csv(
        CRUNCHBASE_PATH,
        usecols=["entity_type", "category_code", "status", "country_code", "funding_total_usd"],
        low_memory=False,
    )
    raw = raw[raw["entity_type"].eq("Company")]
    raw["funding"] = pd.to_numeric(raw["funding_total_usd"], errors="coerce")
    raw["Status"] = (
        raw["status"].fillna("unknown").astype(str).str.strip().str.lower().map(
            {"operating": "Operating", "acquired": "Acquired", "closed": "Closed", "ipo": "IPO"}
        ).fillna("Unknown")
    )
    raw["Category"] = (
        raw["category_code"].fillna("unknown").astype(str).str.replace("_", " ", regex=False).str.title()
    )
    raw["Country"] = raw["country_code"].fillna("Unknown").astype(str).str.strip()
    raw.loc[raw["Country"].str.lower().isin(["", "unknown", "nan", "none"]), "Country"] = "Unknown"
    top = raw["Category"].value_counts().head(12).index
    raw["Category Group"] = raw["Category"].where(raw["Category"].isin(top), "Other")
    grouped = (
        raw.groupby(["Status", "Category Group", "Country"], dropna=False)
        .agg(Companies=("Status", "size"), **{"Funding USD": ("funding", lambda series: series.sum(min_count=1))})
        .reset_index()
    )
    grouped["Companies"] = grouped["Companies"].astype("Int64")
    return grouped.loc[:, REGISTRY_COLUMNS], raw


def main():
    if not IDEAPROOF_PATH.exists():
        raise FileNotFoundError(IDEAPROOF_PATH)

    failures = load_failures()
    cases, drivers, driver_cols = load_sectors()
    write_csv(failures, "Failures.csv", FAILURE_COLUMNS)
    write_csv(cases, "SectorCases.csv", CASE_COLUMNS)
    write_csv(drivers, "SectorDrivers.csv", DRIVER_COLUMNS)

    print("Failures: {:,} write-ups, {:,} with funding".format(len(failures), int(failures["Funding USD"].notna().sum())))
    print("  median lifespan: {} years".format(float(failures["Lifespan Years"].median())))
    print("  median funding: ${:,.0f} million".format(failures["Funding USD"].median() / 1e6))
    print("  themes:")
    print(failures["Failure Theme"].value_counts().to_string())
    print("Sector cases: {:,}".format(len(cases)))
    print("Driver tags: {:,} across {}".format(len(drivers), ", ".join(driver_cols)))

    if CRUNCHBASE_PATH.exists():
        registry, companies = load_registry()
        write_csv(registry, "Registry.csv", REGISTRY_COLUMNS)
        print("Registry: {:,} companies rolled into {:,} rows".format(len(companies), len(registry)))
        print(companies["Status"].value_counts().to_string())
    else:
        print("Registry: left unchanged. Place companies.csv at")
        print("  {}".format(CRUNCHBASE_PATH))

    print("Wrote {}".format(OUT))


if __name__ == "__main__":
    main()
