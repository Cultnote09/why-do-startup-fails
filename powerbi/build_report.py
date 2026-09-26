# -*- coding: utf-8 -*-
"""Build a Power BI project (PBIP) for the startup-failure datasets in this folder.

Run: python powerbi/build_report.py
Then open "Startup Failure Analysis.pbip" in Power BI Desktop.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "powerbi" / "data"
REPORT_DIR = ROOT / "Startup Failure Analysis.Report"
MODEL_DIR = ROOT / "Startup Failure Analysis.SemanticModel"
PBIP_PATH = ROOT / "Startup Failure Analysis.pbip"
DATA_FOLDER = (DATA_DIR.as_posix())

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
SECTOR_META = {
    "Name",
    "Sector",
    "Years of Operation",
    "What They Did",
    "How Much They Raised",
    "Why They Failed",
    "Takeaway",
}

VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json"
PQ_TYPE = {"string": "type text", "int64": "Int64.Type", "double": "type number"}


def squash(value):
    if not isinstance(value, str):
        return value
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def classify(value, rules, default="Other"):
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
    for name, pattern in rules:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return name
    return default


def normalize_country(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Unknown"
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none", "null"}:
        return "Unknown"
    key = raw.lower().strip(".")
    return COUNTRY_ALIASES.get(key, raw)


def parse_money_label(label):
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
    # Most rows are already in millions. A few European rows were stored as raw currency units.
    if value <= 30000:
        return value * 1e6
    return value


def parse_years(text):
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


def load_failures():
    path = ROOT / "ideaproof-startup-failures (1).csv"
    raw = pd.read_csv(path)
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
    frame["Industry Group"] = frame["Industry"].map(lambda v: classify(v, INDUSTRY_RULES))
    prominence = {
        "mega": "Mega",
        "major": "Major",
        "notable": "Notable",
        "recent": "Recent",
    }
    frame["Prominence"] = raw["category"].astype(str).str.lower().map(prominence).fillna("Other")
    frame["Category"] = raw["category"].map(squash)
    frame["Founded Year"] = nullable_int(raw["founded"])
    frame["Failed Year"] = nullable_int(raw["failed"])
    frame.loc[(frame["Founded Year"] < 1950) | (frame["Founded Year"] > 2026), "Founded Year"] = pd.NA
    frame.loc[(frame["Failed Year"] < 1990) | (frame["Failed Year"] > 2026), "Failed Year"] = pd.NA
    lifespan = frame["Failed Year"].astype("Float64") - frame["Founded Year"].astype("Float64")
    lifespan = lifespan.where((lifespan >= 0) & (lifespan <= 45))
    frame["Lifespan Years"] = lifespan.round().astype("Int64")
    frame["Failure Theme"] = raw["failure_reason"].map(lambda v: classify(v, THEME_RULES))
    frame["Theme Sort"] = frame["Failure Theme"].map({name: i for i, name in enumerate(THEME_ORDER, start=1)}).astype("Int64")
    frame["Failure Reason"] = raw["failure_reason"].map(squash)
    frame["Lesson"] = raw["lesson"].map(squash)
    frame["Funding Label"] = raw["funding_raised_label"].map(squash)
    frame["Funding USD"] = [
        parse_funding(label, numeric)
        for label, numeric in zip(raw["funding_raised_label"], raw["funding_raised_usd_millions"])
    ]
    frame["Peak Valuation USD"] = raw["peak_valuation"].map(parse_money_label)
    employees = pd.to_numeric(raw["employees_at_peak"], errors="coerce")
    employees = employees.where((employees > 0) & (employees <= 100000))
    frame["Employees At Peak"] = employees.round().astype("Int64")
    frame["Investors"] = raw["investors"].map(squash)
    frame["Url"] = raw["url"].map(squash)
    top_countries = (
        frame.loc[frame["Country"] != "Unknown", "Country"].value_counts().head(12).index
    )
    frame["Country (top 12)"] = frame["Country"].where(frame["Country"].isin(top_countries), "Other")
    frame.loc[frame["Country"].eq("Unknown"), "Country (top 12)"] = "Unknown"
    return frame, raw


def load_sectors():
    frames = []
    folder = ROOT / "archive (1)"
    for filename in SECTOR_FILES:
        part = pd.read_csv(folder / filename)
        part.columns = [str(col).strip() for col in part.columns]
        part["Source File"] = filename
        frames.append(part)
    raw = pd.concat(frames, ignore_index=True, sort=False)
    driver_cols = []
    for column in raw.columns:
        if column in SECTOR_META or column == "Source File":
            continue
        numeric = pd.to_numeric(raw[column], errors="coerce")
        values = set(numeric.dropna().unique().tolist())
        if values and values <= {0, 1, 0.0, 1.0}:
            driver_cols.append(column)
            raw[column] = numeric.fillna(0).astype(int)

    cases = pd.DataFrame()
    cases["Startup"] = raw["Name"].map(squash)
    cases["Sector"] = raw["Sector"].map(lambda v: SECTOR_SHORT.get(squash(v) or "", squash(v)))
    cases["What They Did"] = raw["What They Did"].map(squash) if "What They Did" in raw else None
    cases["Why They Failed"] = raw["Why They Failed"].map(squash)
    cases["Takeaway"] = raw["Takeaway"].map(squash)
    cases["Raised Label"] = raw["How Much They Raised"].map(squash)
    cases["Raised USD"] = raw["How Much They Raised"].map(parse_money_label)
    years = raw["Years of Operation"].map(parse_years)
    cases["Start Year"] = nullable_int(years.map(lambda item: item[0]))
    cases["End Year"] = nullable_int(years.map(lambda item: item[1]))
    cases["Lifespan Years"] = nullable_int(years.map(lambda item: item[2]))
    if driver_cols:
        cases["Driver Count"] = raw[driver_cols].sum(axis=1).astype("Int64")
    else:
        cases["Driver Count"] = pd.Series([pd.NA] * len(cases), dtype="Int64")
    cases = cases.dropna(subset=["Startup"]).drop_duplicates(["Startup", "Sector"])

    driver_frame = raw[["Name", "Sector", "Why They Failed", "Takeaway"] + driver_cols].copy()
    driver_frame["Startup"] = driver_frame["Name"].map(squash)
    driver_frame["Sector"] = driver_frame["Sector"].map(lambda v: SECTOR_SHORT.get(squash(v) or "", squash(v)))
    long = driver_frame.melt(
        id_vars=["Startup", "Sector", "Why They Failed", "Takeaway"],
        value_vars=driver_cols,
        var_name="Driver",
        value_name="Flag",
    )
    long = long[long["Flag"] == 1].drop(columns=["Flag"])
    long["Why They Failed"] = long["Why They Failed"].map(squash)
    long["Takeaway"] = long["Takeaway"].map(squash)
    long = long.dropna(subset=["Startup"])
    return cases, long.reset_index(drop=True), driver_cols


def load_registry():
    path = ROOT / "archive (2)" / "companies.csv"
    columns = ["entity_type", "category_code", "status", "country_code", "funding_total_usd"]
    raw = pd.read_csv(path, usecols=columns, low_memory=False)
    if "entity_type" in raw and raw["entity_type"].eq("Company").any():
        raw = raw[raw["entity_type"].eq("Company")]
    raw["funding"] = pd.to_numeric(raw["funding_total_usd"], errors="coerce")
    raw["Status"] = raw["status"].fillna("unknown").astype(str).str.strip().str.lower().map(
        {"operating": "Operating", "acquired": "Acquired", "closed": "Closed", "ipo": "IPO"}
    ).fillna("Unknown")
    raw["Category"] = (
        raw["category_code"].fillna("unknown").astype(str).str.replace("_", " ", regex=False).str.title()
    )
    raw["Country"] = raw["country_code"].fillna("Unknown").astype(str).str.strip()
    raw.loc[raw["Country"].str.lower().isin(["", "unknown", "nan", "none"]), "Country"] = "Unknown"
    top = raw["Category"].value_counts().head(12).index
    raw["Category Group"] = raw["Category"].where(raw["Category"].isin(top), "Other")
    grouped = (
        raw.groupby(["Status", "Category Group", "Country"], dropna=False)
        .agg(
            Companies=("Status", "size"),
            **{"Funding USD": ("funding", lambda s: s.sum(min_count=1))},
        )
        .reset_index()
    )
    grouped["Companies"] = grouped["Companies"].astype("Int64")
    return grouped, raw


def write_csv(frame, filename, columns):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = frame.loc[:, [name for name, *_ in columns]].copy()
    path = DATA_DIR / filename
    out.to_csv(path, index=False, encoding="utf-8", lineterminator="\n", float_format="%.2f")
    return path


def tmdl_id(name):
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        return name
    return "'" + name.replace("'", "''") + "'"


def m_query(filename, columns):
    pairs = ", ".join(
        "{%s, %s}" % (json.dumps(name), PQ_TYPE[dtype])
        for name, dtype, *_rest in columns
    )
    names = ", ".join(json.dumps(name) for name, *_rest in columns)
    lines = [
        "let",
        '    Source = Csv.Document(File.Contents(DataFolder & "/%s"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),' % filename,
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        "    Typed = Table.TransformColumnTypes(Promoted, {%s}, \"en-US\")," % pairs,
        "    Selected = Table.SelectColumns(Typed, {%s})" % names,
        "in",
        "    Selected",
    ]
    return "\n".join("\t\t\t\t" + line for line in lines)


def column_tmdl(column):
    name, dtype, summarize, hidden, fmt, category, sort_by = column
    lines = [
        "\tcolumn %s" % tmdl_id(name),
        "\t\tdataType: %s" % dtype,
    ]
    if hidden:
        lines.append("\t\tisHidden: true")
    lines.append("\t\tlineageTag: %s" % uuid.uuid4())
    lines.append("\t\tsummarizeBy: %s" % summarize)
    if fmt:
        lines.append("\t\tformatString: %s" % fmt)
    lines.append("\t\tsourceColumn: %s" % tmdl_id(name))
    if category:
        lines.append("\t\tdataCategory: %s" % category)
    if sort_by:
        lines.append("\t\tsortByColumn: %s" % tmdl_id(sort_by))
    lines.append("\t\tannotation SummarizationSetBy = Automatic")
    return "\n".join(lines)


def measure_tmdl(name, dax, fmt):
    return "\n".join([
        "\tmeasure %s = %s" % (tmdl_id(name), dax),
        "\t\tformatString: %s" % fmt,
        "\t\tdisplayFolder: Metrics",
        "\t\tlineageTag: %s" % uuid.uuid4(),
    ])


def table_tmdl(table_name, columns, measures, filename):
    parts = [
        "table %s" % tmdl_id(table_name),
        "\tlineageTag: %s" % uuid.uuid4(),
    ]
    parts.extend(column_tmdl(column) for column in columns)
    parts.extend(measure_tmdl(*measure) for measure in measures)
    parts.append("\tpartition %s = m" % tmdl_id(table_name))
    parts.append("\t\tmode: import")
    parts.append("\t\tsource =")
    parts.append(m_query(filename, columns))
    parts.append("\tannotation PBI_ResultType = Table")
    return "\n".join(parts) + "\n"


def literal(value):
    if isinstance(value, bool):
        raw = "true" if value else "false"
    elif isinstance(value, str):
        raw = "'" + value.replace("'", "''") + "'"
    else:
        raw = str(value)
    return {"expr": {"Literal": {"Value": raw}}}


def column_projection(entity, prop, active=False):
    item = {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop,
            }
        },
        "queryRef": "%s.%s" % (entity, prop),
        "nativeQueryRef": prop,
    }
    if active:
        item["active"] = True
    return item


def measure_projection(entity, prop):
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop,
            }
        },
        "queryRef": "%s.%s" % (entity, prop),
        "nativeQueryRef": prop,
    }


def sort_by(kind, entity, prop, direction):
    field_body = {
        "Expression": {"SourceRef": {"Entity": entity}},
        "Property": prop,
    }
    return {
        "sort": [{
            "field": {kind: field_body},
            "direction": direction,
        }]
    }


def visual(visual_type, x, y, w, h, z, query_state=None, sort=None, objects=None, title=None, extra_visual=None):
    name = uuid.uuid4().hex[:20]
    body = {"visualType": visual_type, "drillFilterOtherVisuals": True}
    if query_state is not None:
        query = {"queryState": query_state}
        if sort:
            query["sortDefinition"] = sort
        body["query"] = query
    if objects:
        body["objects"] = objects
    if extra_visual:
        body.update(extra_visual)
    if title:
        body["visualContainerObjects"] = {
            "title": [{
                "properties": {
                    "show": literal(True),
                    "text": literal(title),
                }
            }]
        }
    return name, {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": body,
    }


def textbox(text, x, y, w, h, z, size="20pt", bold=True):
    family = (
        "'Segoe UI Semibold', wf_segoe-ui_semibold, helvetica, arial, sans-serif"
        if bold else
        "'Segoe UI', wf_segoe-ui_normal, helvetica, arial, sans-serif"
    )
    name, payload = visual(
        "textbox", x, y, w, h, z,
        objects={
            "general": [{
                "properties": {
                    "paragraphs": [{
                        "textRuns": [{
                            "value": text,
                            "textStyle": {
                                "fontFamily": family,
                                "fontSize": size,
                                "color": "#252423" if bold else "#605E5C",
                            },
                        }]
                    }]
                }
            }]
        },
        extra_visual={
            "visualContainerObjects": {
                "title": [{"properties": {"show": literal(False)}}],
                "background": [{"properties": {"show": literal(False)}}],
                "border": [{"properties": {"show": literal(False)}}],
            }
        },
    )
    return name, payload


def card(entity, measure, x, y, w, h, z):
    return visual(
        "cardVisual", x, y, w, h, z,
        query_state={"Data": {"projections": [measure_projection(entity, measure)]}},
    )


def slicer(entity, column, title, x, y, w, h, z):
    del title
    return visual(
        "slicer", x, y, w, h, z,
        query_state={"Values": {"projections": [column_projection(entity, column, active=True)]}},
        objects={"data": [{"properties": {"mode": literal("Dropdown")}}]},
    )


def chart(visual_type, entity, category, measure, title, x, y, w, h, z, series=None, sort=None):
    state = {
        "Category": {"projections": [column_projection(entity, category, active=True)]},
        "Y": {"projections": [measure_projection(entity, measure)]},
    }
    if series:
        state["Series"] = {"projections": [column_projection(entity, series)]}
    if sort is None:
        sort = sort_by("Measure", entity, measure, "Descending")
    return visual(visual_type, x, y, w, h, z, query_state=state, sort=sort, title=title)


def table_visual(entity, fields, title, x, y, w, h, z):
    projections = []
    for kind, prop in fields:
        if kind == "Column":
            projections.append(column_projection(entity, prop))
        else:
            projections.append(measure_projection(entity, prop))
    return visual(
        "tableEx", x, y, w, h, z,
        query_state={"Values": {"projections": projections}},
        title=title,
    )


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_page(page_name, display_name, visuals):
    page_dir = REPORT_DIR / "definition" / "pages" / page_name
    write_json(page_dir / "page.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": page_name,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
    })
    for name, payload in visuals:
        write_json(page_dir / "visuals" / name / "visual.json", payload)


def col(name, dtype, summarize="none", hidden=False, fmt=None, category=None, sort_by=None):
    return (name, dtype, summarize, hidden, fmt, category, sort_by)


def build():
    if REPORT_DIR.exists():
        shutil.rmtree(REPORT_DIR)
    if MODEL_DIR.exists():
        shutil.rmtree(MODEL_DIR)
    failures, _raw_failures = load_failures()
    cases, drivers, driver_cols = load_sectors()
    registry, registry_raw = load_registry()

    failure_columns = [
        col("Write-up", "string"),
        col("Startup", "string"),
        col("Slug", "string", hidden=True),
        col("Country", "string", category="Country"),
        col("Country (top 12)", "string"),
        col("Industry", "string"),
        col("Industry Group", "string"),
        col("Prominence", "string"),
        col("Category", "string"),
        col("Founded Year", "int64", fmt="#,0"),
        col("Failed Year", "int64", fmt="0"),
        col("Lifespan Years", "int64", summarize="average", fmt="0"),
        col("Failure Theme", "string", sort_by="Theme Sort"),
        col("Theme Sort", "int64", hidden=True),
        col("Failure Reason", "string"),
        col("Lesson", "string"),
        col("Funding Label", "string"),
        col("Funding USD", "double", summarize="sum", hidden=True, fmt="#,0"),
        col("Peak Valuation USD", "double", summarize="sum", hidden=True, fmt="#,0"),
        col("Employees At Peak", "int64", summarize="average", fmt="#,0"),
        col("Investors", "string"),
        col("Url", "string", category="WebUrl"),
    ]
    failure_measures = [
        ("Failed startups", "COUNTROWS ( Failures )", "#,0"),
        ("Funding raised ($M)", "DIVIDE ( SUM ( Failures[Funding USD] ), 1000000 )", "#,0.0"),
        ("Funding raised ($B)", "DIVIDE ( SUM ( Failures[Funding USD] ), 1000000000 )", "#,0.0"),
        ("Median funding ($M)", "DIVIDE ( MEDIAN ( Failures[Funding USD] ), 1000000 )", "#,0.0"),
        ("Median lifespan (years)", "MEDIAN ( Failures[Lifespan Years] )", "0.0"),
        ("Countries", 'CALCULATE ( DISTINCTCOUNT ( Failures[Country] ), Failures[Country] <> "Unknown" )', "#,0"),
    ]
    case_columns = [
        col("Startup", "string"),
        col("Sector", "string"),
        col("What They Did", "string"),
        col("Why They Failed", "string"),
        col("Takeaway", "string"),
        col("Raised Label", "string"),
        col("Raised USD", "double", summarize="sum", hidden=True, fmt="#,0"),
        col("Start Year", "int64", fmt="0"),
        col("End Year", "int64", fmt="0"),
        col("Lifespan Years", "int64", summarize="average", fmt="0"),
        col("Driver Count", "int64", summarize="sum", fmt="0"),
    ]
    case_measures = [
        ("Sector cases", "COUNTROWS ( SectorCases )", "#,0"),
        ("Sector funding ($B)", "DIVIDE ( SUM ( SectorCases[Raised USD] ), 1000000000 )", "#,0.0"),
    ]
    driver_columns = [
        col("Startup", "string"),
        col("Sector", "string"),
        col("Driver", "string"),
        col("Why They Failed", "string"),
        col("Takeaway", "string"),
    ]
    driver_measures = [
        ("Driver tags", "COUNTROWS ( SectorDrivers )", "#,0"),
        ("Tagged startups", "DISTINCTCOUNT ( SectorDrivers[Startup] )", "#,0"),
    ]
    registry_columns = [
        col("Status", "string"),
        col("Category Group", "string"),
        col("Country", "string"),
        col("Companies", "int64", summarize="sum", fmt="#,0"),
        col("Funding USD", "double", summarize="sum", hidden=True, fmt="#,0"),
    ]
    registry_measures = [
        ("Registry companies", "SUM ( Registry[Companies] )", "#,0"),
        ("Closed companies", 'CALCULATE ( [Registry companies], Registry[Status] = "Closed" )', "#,0"),
        ("Registry funding ($B)", "DIVIDE ( SUM ( Registry[Funding USD] ), 1000000000 )", "#,0.0"),
    ]

    write_csv(failures, "Failures.csv", failure_columns)
    write_csv(cases, "SectorCases.csv", case_columns)
    write_csv(drivers, "SectorDrivers.csv", driver_columns)
    write_csv(registry, "Registry.csv", registry_columns)

    definition = MODEL_DIR / "definition"
    (definition / "tables").mkdir(parents=True, exist_ok=True)
    (definition / "cultures").mkdir(parents=True, exist_ok=True)
    (definition / "tables" / "Failures.tmdl").write_text(
        table_tmdl("Failures", failure_columns, failure_measures, "Failures.csv"), encoding="utf-8"
    )
    (definition / "tables" / "SectorCases.tmdl").write_text(
        table_tmdl("SectorCases", case_columns, case_measures, "SectorCases.csv"), encoding="utf-8"
    )
    (definition / "tables" / "SectorDrivers.tmdl").write_text(
        table_tmdl("SectorDrivers", driver_columns, driver_measures, "SectorDrivers.csv"), encoding="utf-8"
    )
    (definition / "tables" / "Registry.tmdl").write_text(
        table_tmdl("Registry", registry_columns, registry_measures, "Registry.csv"), encoding="utf-8"
    )
    (definition / "database.tmdl").write_text(
        "database\n\tcompatibilityLevel: 1567\n", encoding="utf-8"
    )
    (definition / "model.tmdl").write_text(
        "\n".join([
            "model Model",
            "\tculture: en-US",
            "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
            "\tsourceQueryCulture: en-US",
            "\tdataAccessOptions",
            "\t\tlegacyRedirects",
            "\t\treturnErrorValuesAsNull",
            'annotation PBI_QueryOrder = ["DataFolder","Failures","SectorCases","SectorDrivers","Registry"]',
            "annotation __PBI_TimeIntelligenceEnabled = 0",
            'annotation PBI_ProTooling = ["DevMode"]',
            "ref expression DataFolder",
            "ref table Failures",
            "ref table SectorCases",
            "ref table SectorDrivers",
            "ref table Registry",
            "ref cultureInfo en-US",
            "",
        ]),
        encoding="utf-8",
    )
    (definition / "expressions.tmdl").write_text(
        "\n".join([
            "expression DataFolder = \"%s\" meta [IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]" % DATA_FOLDER,
            "\tlineageTag: %s" % uuid.uuid4(),
            "\tannotation PBI_ResultType = Text",
            "",
        ]),
        encoding="utf-8",
    )
    (definition / "cultures" / "en-US.tmdl").write_text(
        "\n".join([
            "cultureInfo en-US",
            "\tlinguisticMetadata = {\"Version\":\"1.0.0\",\"Language\":\"en-US\"}",
            "\t\tcontentType: json",
            "",
        ]),
        encoding="utf-8",
    )
    write_json(MODEL_DIR / "definition.pbism", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {},
    })
    write_json(MODEL_DIR / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": "Startup Failure Analysis"},
        "config": {"version": "2.0", "logicalId": "8f4c2a91-6e3d-4b70-9a55-1c7e0d44b2aa"},
    })

    funded = int(failures["Funding USD"].notna().sum())
    funding_b = failures["Funding USD"].sum(min_count=1) / 1e9
    countries = failures.loc[failures["Country"] != "Unknown", "Country"].nunique()
    overview_note = (
        "%s IdeaProof write-ups across %s countries. Themes are grouped from the written reason. "
        "%s have a parsed funding figure. Median funding is the typical case; mega-rounds pull the total up."
        % (f"{len(failures):,}", f"{countries:,}", f"{funded:,}")
    )
    sector_note = (
        "%s coded postmortems from the sector spreadsheets, with %s driver tags across %s reason flags. "
        "A startup can carry more than one driver, so tag counts are not a split of companies. "
        "This set is separate from the IdeaProof write-ups."
        % (f"{len(cases):,}", f"{len(drivers):,}", len(driver_cols))
    )
    status_counts = registry_raw["Status"].value_counts().to_dict()
    registry_note = (
        "Historical Crunchbase registry in archive (2): %s companies. Operating %s, acquired %s, IPO %s, closed %s. "
        "This is background on outcomes, not the failure case studies."
        % (
            f"{len(registry_raw):,}",
            f"{status_counts.get('Operating', 0):,}",
            f"{status_counts.get('Acquired', 0):,}",
            f"{status_counts.get('IPO', 0):,}",
            f"{status_counts.get('Closed', 0):,}",
        )
    )

    pages = []

    overview = [
        textbox("Why startups fail", 16, 8, 760, 30, 0, "22pt", True),
        textbox(overview_note, 16, 38, 1248, 42, 1, "11pt", False),
    ]
    kpi = [
        ("Failures", "Failed startups"),
        ("Failures", "Funding raised ($B)"),
        ("Failures", "Median funding ($M)"),
        ("Failures", "Median lifespan (years)"),
        ("Failures", "Countries"),
    ]
    for index, (entity, measure) in enumerate(kpi):
        overview.append(card(entity, measure, 16 + index * 252, 84, 240, 88, 10 + index))
    filters = [
        ("Industry Group", "Industry"),
        ("Country", "Country"),
        ("Prominence", "Prominence"),
        ("Failure Theme", "Failure theme"),
    ]
    for index, (column, title) in enumerate(filters):
        overview.append(slicer("Failures", column, title, 16 + index * 316, 180, 304, 72, 20 + index))
    overview.append(chart(
        "barChart", "Failures", "Failure Theme", "Failed startups",
        "Startups by failure theme", 16, 264, 620, 440, 30,
    ))
    overview.append(chart(
        "barChart", "Failures", "Industry Group", "Failed startups",
        "Startups by industry group", 648, 264, 616, 246, 31,
    ))
    overview.append(chart(
        "donutChart", "Failures", "Prominence", "Failed startups",
        "By prominence", 648, 522, 616, 182, 32,
    ))
    write_page("overview", "Overview", overview)
    pages.append("overview")

    funding = [
        textbox("Funding and timing", 16, 8, 700, 32, 0, "22pt", True),
        textbox("Funding is parsed from the published label, in millions of US dollars. A few mega-rounds dominate the total.", 16, 40, 1248, 24, 1, "11pt", False),
    ]
    for index, measure in enumerate(["Funding raised ($B)", "Median funding ($M)", "Median lifespan (years)", "Failed startups"]):
        funding.append(card("Failures", measure, 16 + index * 316, 70, 304, 80, 10 + index))
    for index, (column, title) in enumerate(filters):
        funding.append(slicer("Failures", column, title, 16 + index * 316, 158, 304, 64, 20 + index))
    funding.append(chart(
        "barChart", "Failures", "Industry Group", "Funding raised ($B)",
        "Disclosed funding by industry ($B)", 16, 232, 620, 472, 30,
    ))
    funding.append(chart(
        "columnChart", "Failures", "Failed Year", "Failed startups",
        "Failures by year", 648, 232, 616, 220, 31,
        sort=sort_by("Column", "Failures", "Failed Year", "Ascending"),
    ))
    funding.append(chart(
        "barChart", "Failures", "Country (top 12)", "Failed startups",
        "Where they were based", 648, 462, 616, 242, 32,
    ))
    write_page("funding", "Funding and timing", funding)
    pages.append("funding")

    cases_page = [
        textbox("Case browser", 16, 8, 500, 32, 0, "22pt", True),
        textbox("One row per IdeaProof write-up. Add Investors from the field list if you want the backers.", 520, 14, 744, 24, 1, "11pt", False),
    ]
    case_filters = filters + [("Failed Year", "Year failed")]
    for index, (column, title) in enumerate(case_filters):
        cases_page.append(slicer("Failures", column, title, 16 + index * 252, 48, 240, 64, 10 + index))
    cases_page.append(table_visual(
        "Failures",
        [
            ("Column", "Write-up"),
            ("Column", "Country"),
            ("Column", "Industry Group"),
            ("Column", "Failed Year"),
            ("Column", "Lifespan Years"),
            ("Measure", "Funding raised ($M)"),
            ("Column", "Prominence"),
            ("Column", "Failure Theme"),
            ("Column", "Failure Reason"),
            ("Column", "Lesson"),
            ("Column", "Url"),
        ],
        "Failure write-ups",
        16, 124, 1248, 580, 30,
    ))
    write_page("cases", "Case browser", cases_page)
    pages.append("cases")

    sectors = [
        textbox("Sector postmortems", 16, 8, 560, 32, 0, "22pt", True),
        textbox(sector_note, 16, 40, 1248, 40, 1, "11pt", False),
        card("SectorCases", "Sector cases", 16, 86, 300, 80, 10),
        card("SectorDrivers", "Driver tags", 328, 86, 300, 80, 11),
        card("SectorDrivers", "Tagged startups", 640, 86, 300, 80, 12),
        slicer("SectorDrivers", "Sector", "Sector", 952, 86, 312, 80, 13),
        chart(
            "barChart", "SectorDrivers", "Driver", "Driver tags",
            "How often each driver was flagged", 16, 178, 620, 524, 20,
        ),
        chart(
            "barChart", "SectorDrivers", "Driver", "Driver tags",
            "Drivers by sector", 648, 178, 616, 250, 21,
            series="Sector",
        ),
        table_visual(
            "SectorCases",
            [
                ("Column", "Startup"),
                ("Column", "Sector"),
                ("Column", "Lifespan Years"),
                ("Column", "Raised Label"),
                ("Column", "Why They Failed"),
                ("Column", "Takeaway"),
            ],
            "What the postmortems said",
            648, 438, 616, 264, 22,
        ),
    ]
    write_page("sectors", "Sector postmortems", sectors)
    pages.append("sectors")

    registry_page = [
        textbox("Company registry", 16, 8, 560, 32, 0, "22pt", True),
        textbox(registry_note, 16, 40, 1248, 40, 1, "11pt", False),
        card("Registry", "Registry companies", 16, 88, 300, 80, 10),
        card("Registry", "Registry funding ($B)", 328, 88, 300, 80, 11),
        slicer("Registry", "Status", "Status", 640, 88, 300, 80, 12),
        slicer("Registry", "Category Group", "Category", 952, 88, 312, 80, 13),
        chart(
            "donutChart", "Registry", "Status", "Registry companies",
            "Outcome mix", 16, 184, 400, 500, 20,
        ),
        chart(
            "barChart", "Registry", "Category Group", "Registry companies",
            "Companies by category", 432, 184, 832, 500, 21,
        ),
    ]
    write_page("registry", "Company registry", registry_page)
    pages.append("registry")

    write_json(REPORT_DIR / "definition" / "pages" / "pages.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": pages,
        "activePageName": "overview",
    })
    write_json(REPORT_DIR / "definition" / "version.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    write_json(REPORT_DIR / "definition" / "report.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY24SU10",
                "reportVersionAtImport": {"visual": "1.8.95", "report": "2.0.95", "page": "1.3.95"},
                "type": "SharedResources",
            }
        },
        "objects": {
            "section": [{
                "properties": {
                    "verticalAlignment": literal("Top"),
                }
            }]
        },
        "resourcePackages": [{
            "name": "SharedResources",
            "type": "SharedResources",
            "items": [{
                "name": "CY24SU10",
                "path": "BaseThemes/CY24SU10.json",
                "type": "BaseTheme",
            }],
        }],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
    })
    write_json(REPORT_DIR / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../Startup Failure Analysis.SemanticModel"}},
    })
    write_json(REPORT_DIR / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "Startup Failure Analysis"},
        "config": {"version": "2.0", "logicalId": "b7e1d0c4-2a55-4f83-8c16-90ab33d47e02"},
    })
    write_json(PBIP_PATH, {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": "Startup Failure Analysis.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    (ROOT / ".gitignore").write_text(
        "\n".join([
            ".pbi/localSettings.json",
            ".pbi/cache.abf",
            "**/.pbi/localSettings.json",
            "**/.pbi/cache.abf",
            "**/.pbi/unappliedChanges.json",
            "",
        ]),
        encoding="utf-8",
    )

    print("FAILURES", len(failures), "duplicate names", int(failures["Startup"].duplicated().sum()))
    print("funding non-null", funded, "sum $B", round(funding_b, 2))
    print("median funding $M", round(failures["Funding USD"].median() / 1e6, 1))
    print("median lifespan", float(failures["Lifespan Years"].median()))
    print("THEME")
    print(failures["Failure Theme"].value_counts().to_string())
    print("INDUSTRY")
    print(failures["Industry Group"].value_counts().to_string())
    print("PROMINENCE")
    print(failures["Prominence"].value_counts().to_string())
    print("OTHER THEMES")
    print(failures.loc[failures["Failure Theme"].eq("Other"), "Failure Reason"].head(25).to_string())
    print("OTHER INDUSTRIES")
    print(failures.loc[failures["Industry Group"].eq("Other"), "Industry"].value_counts().head(30).to_string())
    print("SECTOR CASES", len(cases), "DRIVERS", len(drivers), "FLAGS", driver_cols)
    print(cases["Sector"].value_counts().to_string())
    print(drivers["Driver"].value_counts().to_string())
    print("REGISTRY", len(registry_raw), status_counts)
    print("LARGEST FUNDING")
    print(failures.nlargest(8, "Funding USD")[["Startup", "Funding Label", "Funding USD"]].to_string())
    print("WROTE", PBIP_PATH)


if __name__ == "__main__":
    build()
