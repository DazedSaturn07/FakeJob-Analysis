"""Build the editable Job Market Power BI project from notebook 03 exports.

Run: python power_bi/build_report.py
Open Job_Market_Quality.pbip in Desktop, refresh, inspect and save as PBIX.
Use --rebuild only when deliberately replacing the generated definitions.
"""
import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
REPORT = HERE / "Job_Market_Quality.Report"
MODEL = HERE / "Job_Market_Quality.SemanticModel"
BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
NAVY, TEAL, AMBER, INK, MUTED, PAPER = "#142B45", "#087F8C", "#C48327", "#243B53", "#65768A", "#F3F6FA"
PAGES = [
    ("overview", "Overview", "Job posting clarity"),
    ("pay", "Pay & clarity", "What candidates can see"),
    ("entry", "Entry expectations", "Experience behind junior titles"),
    ("repeats", "Repeated text", "Separate observations from job identities"),
    ("detail", "Job detail", "Review the evidence"),
    ("method", "Method & checks", "Definitions you can explain"),
]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lit(value):
    text = str(value).lower() if isinstance(value, bool) else str(value) + ("D" if isinstance(value, float) else "L") if isinstance(value, (int, float)) else "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def color(value):
    return {"solid": {"color": lit(value)}}


def obj(**values):
    return [{"properties": values}]


def field(table, column, measure=False, alias=None):
    return {"Measure" if measure else "Column": {"Expression": {"SourceRef": {"Source": alias} if alias else {"Entity": table}}, "Property": column}}


def measure(name):
    return field("ReportMeasures", name, True)


def projection(expression, label):
    part = expression.get("Measure", expression.get("Column"))
    return {"field": expression, "queryRef": part["Expression"]["SourceRef"]["Entity"] + "." + part["Property"], "displayName": label}


def filter_value(name, table, column, value, is_measure=False, comparison=0):
    return {"name": name, "field": field(table, column, is_measure), "type": "Advanced", "howCreated": "User",
            "filter": {"Version": 2, "From": [{"Name": "f", "Entity": table, "Type": 0}], "Where": [{"Condition": {
                "Comparison": {"ComparisonKind": comparison, "Left": field(table, column, is_measure, "f"), "Right": lit(value)["expr"]}}}]}}


def build_model():
    tables = []
    boolean = {"salary_numeric_present", "experience_numeric_present"}
    integers = {"year", "quarter", "month", "day", "is_weekend", "posting_age_days", "description_word_count", "flag_count", "flag_id"}
    decimals = {"salary_min", "salary_max", "salary_median", "experience_min_years", "experience_max_years"}
    for path in sorted((ROOT / "notebooks/data/exports").glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as stream:
            names = next(csv.reader(stream))
        columns, conversions = [], []
        for name in names:
            dtype = "boolean" if name in boolean else "int64" if name.endswith("_key") and name != "canonical_job_key" or name in integers else "double" if name in decimals or name.endswith("_score") else "dateTime" if name in {"full_date", "created_at", "scored_at"} else "string"
            mtype = {"boolean": "type logical", "int64": "Int64.Type", "double": "type number", "dateTime": "type datetime", "string": "type text"}[dtype]
            if name == "full_date":
                mtype = "type date"
            col = {"name": name, "dataType": dtype, "sourceColumn": name, "summarizeBy": "none"}
            if dtype == "dateTime":
                col["formatString"] = "dd MMM yyyy" if name == "full_date" else "dd MMM yyyy HH:mm"
            if name == "full_date":
                col["isKey"] = True
                col["annotations"] = [{"name": "UnderlyingDateTimeDataType", "value": "Date"}]
            if name == "month_name":
                col["sortByColumn"] = "month"
            if name.endswith("_key") or name in {"payload_hash", "flag_id", "created_at", "scored_at"}:
                col["isHidden"] = True
            columns.append(col)
            conversions.append('{"' + name + '", ' + mtype + '}')
        expression = [
            "let",
            '    Source = Csv.Document(File.Contents(DataFolder & "/' + path.name + '"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
            "    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
            '    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),',
            '    Typed = Table.TransformColumnTypes(EmptyAsNull, {' + ", ".join(conversions) + '}, "en-US")',
            "in", "    Typed",
        ]
        tables.append({"name": path.stem, "columns": columns, "partitions": [{"name": path.stem, "mode": "import", "source": {"type": "m", "expression": expression}}]})
    if len(tables) != 12:
        raise ValueError("Run notebooks 01–03 first: expected 12 exported tables.")
    postings = next(table for table in tables if table["name"] == "fact_job_posting")
    for name, dtype, expression in [
        ("Quality band", "string", "LOOKUPVALUE(fact_job_quality[quality_band], fact_job_quality[job_key], fact_job_posting[job_key])"),
        ("Pay disclosure", "string", 'IF(fact_job_posting[salary_numeric_present], "Numeric pay disclosed", "No numeric pay")'),
        ("Experience evidence", "string", 'IF(fact_job_posting[experience_numeric_present], "Numeric phrase found", "Not parsed")'),
    ]:
        postings["columns"].append({"type": "calculated", "name": name, "dataType": dtype, "expression": expression, "summarizeBy": "none"})
    # Expose a stable key for selection and drill-through, hide technical keys elsewhere.
    next(c for t in tables if t["name"] == "dim_job" for c in t["columns"] if c["name"] == "job_key")["isHidden"] = False
    measures = []
    text = (HERE / "measures.dax").read_text(encoding="utf-8")
    text = re.sub(r"^//.*$", "", text, flags=re.M).strip()
    for definition in re.split(r"\n\s*\n(?=[^\s].*?=)", text):
        name, expression = definition.split("=", 1)
        name = name.strip()
        measures.append({"name": name, "expression": expression.strip(), "formatString": "0.0%" if "%" in name else "0.00" if name == "Average JD Quality" else "#,0", "displayFolder": "Clarity measures"})
    extras = {
        "Missing Pay Postings": ("CALCULATE([Total Postings], KEEPFILTERS(fact_job_posting[salary_numeric_present] = FALSE()))", "#,0"),
        "Experience Coverage %": ("DIVIDE(CALCULATE([Total Postings], KEEPFILTERS(fact_job_posting[experience_numeric_present] = TRUE())), [Total Postings])", "0.0%"),
        "Remote Permission %": ('DIVIDE(CALCULATE([Total Postings], KEEPFILTERS(fact_job_posting[workplace_type] = "remote")), [Total Postings])', "0.0%"),
        "Repeat Share %": ("DIVIDE([Repost Events], [Total Postings])", "0.0%"),
        "Review Share %": ("DIVIDE([Quality Review Jobs], [Distinct Jobs])", "0.0%"),
        "One Job Selected": ("IF(COUNTROWS(ALLSELECTED(dim_job[job_key])) = 1, 1, 0)", "0"),
        "Selected Title": ('IF([One Job Selected] = 1, SELECTEDVALUE(dim_job[title_normalized]), "Choose a job ID")', None),
        "Top 10 Repeating Companies": ("VAR ThisCompany = SELECTEDVALUE(dim_company[company_key])\nVAR TopCompanies = TOPN(10, ALLSELECTED(dim_company), [Repost Events], DESC, dim_company[company_key], ASC)\nRETURN IF([Repost Events] > 0 && CONTAINS(TopCompanies, dim_company[company_key], ThisCompany), 1, 0)", "0"),
        "Job Description": ('IF([One Job Selected] = 1, CONCATENATEX(TOPN(1, fact_job_posting, fact_job_posting[published_date_key], DESC, fact_job_posting[source_job_id], DESC), LEFT(fact_job_posting[description_clean], 6000), ""))', None),
        "Salary Numeric Rows": ("CALCULATE([Total Postings], KEEPFILTERS(fact_job_posting[salary_numeric_present] = TRUE()))", "#,0"),
        "Mapped Role Filter": ('IF(SELECTEDVALUE(dim_role[canonical_role_name]) <> "Unclassified", 1, 0)', "0"),
    }
    for name, (expression, fmt) in extras.items():
        entry = {"name": name, "expression": expression, "displayFolder": "Report controls" if name in {"One Job Selected", "Selected Title", "Top 10 Repeating Companies", "Job Description"} else "Clarity measures"}
        if fmt:
            entry["formatString"] = fmt
        measures.append(entry)
    next(m for m in measures if m["name"] == "Quality Band").pop("formatString", None)
    tables.append({"name": "ReportMeasures", "columns": [{"name": "Placeholder", "dataType": "int64", "sourceColumn": "Placeholder", "isHidden": True}], "partitions": [{"name": "ReportMeasures", "mode": "import", "source": {"type": "m", "expression": "#table(type table [Placeholder=Int64.Type], {{1}})"}}], "measures": measures})
    relationships = []
    for link in json.loads((HERE / "relationships.json").read_text())["relationships"]:
        relationships.append({"name": link["to_table"] + "_" + link["to_column"] + "_" + link["from_table"],
                              "fromTable": link["to_table"], "fromColumn": link["to_column"],
                              "toTable": link["from_table"], "toColumn": link["from_column"],
                              "fromCardinality": "many", "toCardinality": "one", "crossFilteringBehavior": "oneDirection", "isActive": True})
    model = {"name": "Job_Market_Quality", "compatibilityLevel": 1600, "model": {
        "culture": "en-US", "sourceQueryCulture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3",
        # Set the generic DataFolder parameter in Desktop before refresh.
        # Published definitions must not contain the author's local folder path.
        "expressions": [{"name": "DataFolder", "kind": "m", "expression": '"C:/data/FakeJob-Analysis/notebooks/data/exports" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'}],
        "tables": tables, "relationships": relationships, "annotations": [{"name": "__PBI_TimeIntelligenceEnabled", "value": "0"}]}}
    write(MODEL / "definition.pbism", {"version": "4.0", "settings": {}})
    write(MODEL / "model.bim", model)


class Page:
    def __init__(self, key, label, title, number):
        self.key, self.label, self.visuals, self.slicers = key, label, [], []
        self.data = {"$schema": BASE + "page/2.0.0/schema.json", "name": key, "displayName": label, "width": 1440, "height": 900,
                     "displayOption": "FitToPage", "objects": {"background": obj(color=color(PAPER), transparency=lit(0)), "outspace": obj(color=color(PAPER))}, "visualInteractions": []}
        self.text("brand", "JOB MARKET", 24, 28, 180, 45, 17, TEAL, True)
        self.text("brand_sub", "QUALITY ANALYSIS", 24, 68, 180, 40, 10, MUTED)
        self.text("title", title, 228, 24, 1180, 65, 27, NAVY, True)
        self.text("period", "Historical LinkedIn snapshot  |  24 March–20 April 2024 UTC  |  Full source", 230, 87, 1160, 35, 11, MUTED)
        for index, (target, target_label, _) in enumerate(PAGES):
            self.button("nav_" + target, f"0{index+1}  {target_label}", 24, 154 + index * 62, 172, 46, "PageNavigation", target, target == key)
        self.button("reset", "Reset this page", 24, 748, 172, 42, "Bookmark", "reset_" + key)
        self.text("scope", "One historical snapshot.\nRules support review.\nThey do not prove fraud.", 24, 808, 174, 80, 9, MUTED)
        self.text("footer", f"{number:02d}   {label.upper()}    /    Posting observations and exact text groups are different populations.", 230, 862, 1160, 30, 10, MUTED)

    def add(self, name, kind, x, y, w, h, title=None, fields=None, objects=None, filters=None, container=None):
        vid = self.key + "_" + name
        vc = {"background": obj(show=lit(True), color=color("#FFFFFF"), transparency=lit(0)),
              "border": obj(show=lit(False)), "general": obj(altText=lit(title or name))}
        if title:
            vc["title"] = obj(show=lit(True), text=lit(title), fontSize=lit(12), bold=lit(True), fontColor=color(INK), titleWrap=lit(True))
        if container:
            vc.update(container)
        visual = {"visualType": kind, "objects": objects or {}, "visualContainerObjects": vc, "drillFilterOtherVisuals": True}
        if fields:
            visual["query"] = {"queryState": {role: {"projections": [projection(expression, label) for expression, label in values]} for role, values in fields.items()}}
        result = {"$schema": BASE + "visualContainer/2.4.0/schema.json", "name": vid,
                  "position": {"x": x, "y": y, "z": len(self.visuals), "width": w, "height": h, "tabOrder": len(self.visuals)}, "visual": visual}
        if filters:
            result["filterConfig"] = {"filters": filters}
        self.visuals.append(result)
        return result

    def text(self, name, text, x, y, w, h, size=12, ink=INK, bold=False):
        paragraphs = [{"textRuns": [{"value": line, "textStyle": {"fontFamily": "Segoe UI", "fontSize": str(size) + "pt", "color": ink, "fontWeight": "bold" if bold else "normal"}}]} for line in text.split("\n")]
        return self.add(name, "textbox", x, y, w, h, objects={"general": obj(paragraphs=paragraphs)}, container={"background": obj(show=lit(False)), "visualHeader": obj(show=lit(False))})

    def button(self, name, label, x, y, w, h, action, target, selected=False):
        def states(**properties):
            return [{"properties": {"show": lit(True)}}, {"selector": {"id": "default"}, "properties": properties}]
        link = {"show": lit(True), "type": lit(action)}
        if action != "Back":
            link["navigationSection" if action == "PageNavigation" else "bookmark"] = lit(target)
        return self.add(name, "actionButton", x, y, w, h, objects={
            "text": states(text=lit(label), fontColor=color("#FFFFFF" if selected else INK), fontSize=lit(10), horizontalAlignment=lit("left")),
            "fill": states(fillColor=color(TEAL if selected else "#E5ECF3")), "shape": obj(tileShape=lit("rectangle")), "icon": obj(show=lit(False)), "outline": obj(show=lit(False))
        }, container={"visualLink": obj(**link), "background": obj(show=lit(False)), "visualHeader": obj(show=lit(False))})

    def card(self, name, title, x, y, w=280, h=110):
        return self.add(re.sub(r"[^a-zA-Z0-9]", "_", name), "cardVisual", x, y, w, h, title,
                        fields={"Data": [(measure(name), title)]},
                        objects={"value": [{"selector": {"id": "default"}, "properties": {"fontSize": lit(27), "fontColor": color(TEAL), "labelDisplayUnits": lit(1)}}],
                                 "outline": [{"selector": {"id": "default"}, "properties": {"show": lit(False)}}],
                                 "label": [{"selector": {"id": "default"}, "properties": {"show": lit(False)}}],
                                 "layout": [{"selector": {"id": "default"}, "properties": {"paddingUniform": lit(0)}}]})

    def slicer(self, name, table, column, title, x, y, w):
        result = self.add(name, "slicer", x, y, w, 75, title, fields={"Values": [(field(table, column), title)]},
                          objects={"data": obj(mode=lit("Dropdown")), "header": obj(show=lit(False)), "selection": obj(singleSelect=lit(False), selectAllCheckboxEnabled=lit(True)),
                                   "general": obj(selfFilterEnabled=lit(True)), "items": obj(fontSize=lit(11), fontColor=color(INK))},
                          container={"padding": obj(top=lit(6), bottom=lit(6), left=lit(8), right=lit(8))})
        self.slicers.append(result)
        return result

    def chart(self, name, kind, table, column, values, x, y, w, h, title, filters=None, ascending=False):
        result = self.add(name, kind, x, y, w, h, title,
                          fields={"Category": [(field(table, column), column.replace("_", " ").title())], "Y": [(measure(value), label) for value, label in values]},
                          objects={"categoryAxis": obj(fontSize=lit(10), showAxisTitle=lit(False), maxSize=lit(45)), "valueAxis": obj(fontSize=lit(10), showAxisTitle=lit(False)),
                                   "legend": obj(show=lit(len(values) > 1)), "general": obj(responsive=lit(True))}, filters=filters)
        result["visual"]["query"]["sortDefinition"] = {"sort": [{"field": field(table, column) if ascending else measure(values[0][0]), "direction": "Ascending" if ascending else "Descending"}]}
        return result

    def table(self, name, columns, x, y, w, h, title, filters=None):
        return self.add(name, "tableEx", x, y, w, h, title, fields={"Values": columns}, filters=filters,
                        objects={"columnHeaders": obj(fontSize=lit(10), fontColor=color(NAVY), wordWrap=lit(True)),
                                 "values": obj(fontSize=lit(10), wordWrap=lit(False)), "grid": obj(gridVertical=lit(False)),
                                 "total": obj(totals=lit(False))})

    def save(self):
        folder = REPORT / "definition/pages" / self.key
        write(folder / "page.json", self.data)
        mobile_y = 12
        for visual in self.visuals:
            write(folder / "visuals" / visual["name"] / "visual.json", visual)
        # Mobile prioritises headline figures before filters and long comparisons.
        mobile_visuals = sorted(self.visuals, key=lambda v: (
            0 if v["name"] == self.key + "_title" else
            1 if v["visual"]["visualType"] == "cardVisual" else
            2 if v["visual"]["visualType"] == "slicer" else
            4 if v["name"] == self.key + "_reset" else 3,
            v["position"]["y"], v["position"]["x"]))
        for visual in mobile_visuals:
            short_name = visual["name"][len(self.key) + 1:]
            if short_name.startswith("nav_") or short_name in {"brand", "brand_sub", "scope", "footer", "period", "back"}:
                continue
            kind = visual["visual"]["visualType"]
            height = 70 if short_name == "title" else 46 if short_name == "reset" else 80 if kind == "slicer" else 110 if kind == "cardVisual" else 270 if "Chart" in kind else 220 if kind == "tableEx" else 200
            mobile = {"$schema": BASE + "visualContainerMobileState/1.0.0/schema.json",
                      "position": {"x": 8, "y": mobile_y, "z": len(self.visuals), "width": 304, "height": height}}
            if short_name == "title":
                mobile["objects"] = {"general": obj(paragraphs=[{"textRuns": [{"value": self.label, "textStyle": {"fontFamily": "Segoe UI", "fontSize": "20pt", "color": NAVY, "fontWeight": "bold"}}]}])}
            write(folder / "visuals" / visual["name"] / "mobile.json", mobile)
            mobile_y += height + 10
        # Reset restores fixed visual filters, page drill-through and slicer state.
        states = {v["name"]: {"singleVisual": {}} for v in self.visuals}
        for visual in self.visuals:
            saved = [{"name": f["name"], "type": f["type"], "expression": f["field"], "filter": f["filter"], "howCreated": 1}
                     for f in visual.get("filterConfig", {}).get("filters", []) if "filter" in f]
            if saved:
                states[visual["name"]]["filters"] = {"byExpr": saved}
        for visual in self.slicers:
            states[visual["name"]]["singleVisual"] = {"objects": {"merge": {"general": obj(selfFilterEnabled=lit(True), filter={"filter": {"Version": 2, "From": [], "Where": []}})}}}
        section = {"visualContainers": states}
        write(REPORT / "definition/bookmarks" / ("reset_" + self.key + ".bookmark.json"), {
            "$schema": BASE + "bookmark/1.4.0/schema.json", "name": "reset_" + self.key, "displayName": "Reset " + self.label,
            "options": {"suppressData": False, "suppressDisplay": True, "suppressActiveSection": True, "applyOnlyToTargetVisuals": False},
            "explorationState": {"version": "1.3", "activeSection": self.key, "sections": {self.key: section}}})


def build_pages():
    pages = [Page(key, label, title, i) for i, (key, label, title) in enumerate(PAGES, 1)]
    for page in pages[:4]:
        page.slicer("role", "dim_role", "canonical_role_name", "Role", 230, 132, 332)
        page.slicer("seniority", "fact_job_posting", "seniority_title", "Title seniority", 580, 132, 240)
        page.slicer("employment", "fact_job_posting", "employment_type", "Employment type", 838, 132, 260)
        page.slicer("date", "dim_date", "full_date", "Posting date", 1116, 132, 292)
    p = pages[0]
    for i, (name, title) in enumerate([("Total Postings", "Posting observations"), ("Distinct Jobs", "Exact job-text groups"), ("Average JD Quality", "Average clarity score / 100"), ("Salary Transparency %", "Numeric pay disclosure")]):
        p.card(name, title, 230 + i * 299, 228, 281)
    p.chart("daily", "lineChart", "dim_date", "full_date", [("Total Postings", "Observations")], 230, 360, 692, 268, "Posting observations by listed date", ascending=True)
    p.chart("role_volume", "clusteredBarChart", "dim_role", "canonical_role_name", [("Distinct Jobs", "Exact groups")], 940, 360, 468, 268, "Mapped technology roles only",
            [filter_value("mapped_roles_only", "ReportMeasures", "Mapped Role Filter", 1, True)])
    p.chart("pay", "clusteredBarChart", "fact_job_posting", "Pay disclosure", [("Total Postings", "Observations")], 230, 648, 572, 186, "Is numeric compensation visible?")
    p.text("reading", "READING THE SNAPSHOT\n123,849 observations across 28 listed dates; 20 April is partial.\nCounts reflect snapshot coverage, not changes in market demand.\nRole mapping covers selected technology titles; other jobs remain Unclassified.", 820, 650, 588, 185, 12, MUTED)

    p = pages[1]
    for i, (name, title) in enumerate([("Salary Transparency %", "Numeric pay disclosed"), ("Missing Pay Postings", "No numeric pay"), ("Experience Coverage %", "Numeric experience parsed"), ("Remote Permission %", "Remote permission confirmed")]):
        p.card(name, title, 230+i*299, 228, 281)
    p.chart("bands", "clusteredBarChart", "fact_job_posting", "Quality band", [("Distinct Jobs", "Exact groups")], 230, 360, 572, 240, "Distribution of rule-based clarity bands")
    p.chart("role_pay", "clusteredBarChart", "dim_role", "canonical_role_name", [("Salary Transparency %", "Disclosure")], 820, 360, 588, 240, "Salary disclosure by mapped role")
    p.table("pay_periods", [(field("fact_job_posting", c), label) for c, label in [("salary_currency", "Currency"), ("salary_period", "Pay period")]] +
            [(measure("Total Postings"), "Observations"), (measure("Salary Numeric Rows"), "Numeric pay"), (measure("Salary Transparency %"), "Disclosure")],
            230, 620, 572, 212, "Keep currency and pay period separate")
    p.chart("skills", "clusteredBarChart", "dim_skill", "skill_name", [("Jobs with Skill", "Jobs mentioning skill")], 820, 620, 588, 212, "Recognised skills among visible jobs")
    skill = p.visuals[-1]
    for target in p.visuals:
        if target["name"] != skill["name"]:
            p.data["visualInteractions"].append({"source": skill["name"], "target": target["name"], "type": "NoFilter"})

    p = pages[2]
    for i, (name, title) in enumerate([("Entry-Level Jobs", "Explicit entry-title groups"), ("Entry Jobs Requiring 2+ Years", "Groups with parsed 2+ years"), ("Entry 2+ Years %", "Share of entry-title groups"), ("Jobs with Entry Review Flags", "Representative jobs flagged")]):
        p.card(name, title, 230+i*299, 228, 281)
    p.chart("role_entry", "clusteredBarChart", "dim_role", "canonical_role_name",
            [("Entry-Level Jobs", "Entry groups"), ("Entry Jobs Requiring 2+ Years", "Parsed 2+ years")], 230, 360, 692, 245, "Entry-title experience expectations")
    p.text("entry_note", "A REVIEW QUESTION\nDoes the stated experience fit the title?\nOnly explicit junior title keywords and numeric experience phrases are checked.\nAn unparsed description is unknown, not zero experience.", 940, 360, 468, 245, 13, MUTED)
    filters = [filter_value("entry_title", "fact_job_posting", "seniority_title", "entry"), filter_value("two_years", "fact_job_posting", "experience_min_years", 2, comparison=2)]
    p.table("entry_rows", [(field("dim_job", "job_key"), "Job ID"), (field("fact_job_posting", "source_job_id"), "Source ID"), (field("fact_job_posting", "title_raw"), "Posting title"),
            (field("fact_job_posting", "experience_min_years"), "Min years"), (measure("Average JD Quality"), "Score")],
            230, 624, 1178, 208, "Entry postings with parsed 2+ years — right-click Job ID to investigate", filters)

    p = pages[3]
    for i, (name, title) in enumerate([("Total Postings", "Posting observations"), ("Distinct Jobs", "Exact job-text groups"), ("Repost Events", "Extra repeated observations"), ("Repeat Share %", "Repeated observation share")]):
        p.card(name, title, 230+i*299, 228, 281)
    p.chart("companies", "clusteredBarChart", "dim_company", "company_name", [("Repost Events", "Repeated observations")], 230, 360, 572, 274,
            "Ten companies with most exact repeats", [filter_value("top_companies", "ReportMeasures", "Top 10 Repeating Companies", 1, True)])
    p.table("repeated_jobs", [(field("dim_job", "job_key"), "Job ID"), (field("dim_job", "title_normalized"), "Title"), (measure("Total Postings"), "Observations"), (measure("Repost Events"), "Repeats")],
            820, 360, 588, 274, "Repeated groups — right-click Job ID to inspect", [filter_value("repeated_only", "ReportMeasures", "Repost Events", 0, True, 1)])
    p.visuals[-1]["visual"]["objects"]["columnHeaders"][0]["properties"]["autoSizeColumnWidth"] = lit(False)
    p.visuals[-1]["visual"]["objects"]["columnWidth"] = [
        {"selector": {"metadata": name}, "properties": {"value": lit(float(width))}}
        for name, width in [("dim_job.job_key", 50), ("dim_job.title_normalized", 280),
                            ("ReportMeasures.Total Postings", 110), ("ReportMeasures.Repost Events", 95)]]
    p.text("repeat_note", "HOW TO INTERPRET EXACT REPEATS\nMatching company, title, location and cleaned description define a group.\nRepeated rows can reflect collection patterns or legitimate reuse. They do not establish a vacancy's current status or deceptive behaviour.\nEditing a description can evade exact matching; identical text can also describe distinct opportunities.", 230, 658, 1178, 175, 13, MUTED)

    p = pages[4]
    p.slicer("job", "dim_job", "job_key", "Select one job ID, or drill through from a table", 230, 132, 570)
    p.button("back", "Back to source page", 1118, 134, 290, 45, "Back", "")
    p.card("Average JD Quality", "Representative clarity score", 230, 228, 280)
    p.card("Total Postings", "Observations for selection", 528, 228, 280)
    p.card("Visible Flags", "Rule flags", 826, 228, 280)
    p.card("Repost Events", "Repeated observations", 1124, 228, 284)
    guard = lambda n: [filter_value(n, "ReportMeasures", "One Job Selected", 1, True)]
    p.table("posting", [(field("fact_job_posting", c), label) for c, label in
            [("source_job_id", "Source ID"), ("title_raw", "Title"), ("salary_min", "Min pay"), ("salary_max", "Max pay"), ("salary_median", "Median pay"), ("salary_currency", "Currency"), ("salary_period", "Period"), ("experience_min_years", "Years")]],
            230, 360, 1178, 152, "Posting evidence — select exactly one job", guard("one_job_evidence"))
    p.table("flags", [(field("fact_job_flag", c), label) for c, label in [("rule_code", "Rule"), ("observed_value", "Observed"), ("expected_value", "Expected"), ("evidence_text", "Reason")]],
            230, 532, 1178, 140, "Rules for this exact job group", guard("one_job_flags"))
    p.table("description", [(measure("Job Description"), "Latest observed description (up to 6,000 characters)")], 230, 692, 1178, 143, "Description evidence", guard("one_job_description"))
    p.visuals[-1]["visual"]["objects"]["values"] = obj(fontSize=lit(10), wordWrap=lit(True))
    p.data["filterConfig"] = {"filters": [{"name": "job_drill", "field": field("dim_job", "job_key"), "type": "Categorical", "howCreated": "Drillthrough"}]}
    p.data["pageBinding"] = {"name": "job_drillthrough", "type": "Drillthrough", "acceptsFilterContext": "Default",
                             "parameters": [{"name": "job_key", "boundFilter": "job_drill", "fieldExpr": field("dim_job", "job_key")}]}

    p = pages[5]
    p.text("source", "SOURCE & POPULATION\n123,849 postings from one historical LinkedIn snapshot.\nThe first-5,000 learning slice is not used in this report.\nOne job identity is an exact company/title/location/description group.", 230, 145, 575, 172, 13, INK)
    p.text("rules", "SIX VISIBLE COMPONENTS\nCompleteness 30% · Experience 20% · Salary 15%\nLocation 10% · Role/skills 15% · Exact repetition 10%\nThe score is a heuristic review aid, not a trained model or employer rating.", 825, 145, 583, 172, 13, INK)
    p.table("bands", [(field("fact_job_posting", "Quality band"), "Band"), (measure("Distinct Jobs"), "Job groups"), (measure("Average JD Quality"), "Average score")],
            230, 340, 575, 247, "Score bands — thresholds 85, 70 and 50")
    p.text("limitations", "INTERPRETATION LIMITS\nMissing experience is unknown. Unclassified roles are outside the limited title vocabulary.\nRemote is confirmed only by remote_allowed=1; blank does not mean on-site.\nNumeric pay includes min, max or median. Never combine currencies or pay periods into an average salary.", 825, 340, 583, 247, 13, MUTED)
    p.text("checks", "VALIDATION & REFRESH\nSource → notebooks → 12 shared CSVs → independent MySQL checks → report model.\nClear all filters when comparing report totals with the notebook summary.\nAfter rerunning notebooks, refresh this report; all tables must come from the same population and score version.\nRead the report guide for verified values and the evidence from this build.", 230, 615, 1178, 210, 13, MUTED)
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if (HERE / "Job_Market_Quality.pbip").exists() and not args.rebuild:
        raise SystemExit("Project already exists. Save manual edits before an intentional --rebuild.")
    build_model()
    pages = build_pages()
    for page in pages:
        page.save()
    write(HERE / "Job_Market_Quality.pbip", {"version": "1.0", "artifacts": [{"report": {"path": REPORT.name}}], "settings": {"enableAutoRecovery": True}})
    write(REPORT / "definition.pbir", {"version": "4.0", "datasetReference": {"byPath": {"path": "../" + MODEL.name}}})
    write(REPORT / "definition/version.json", {"$schema": BASE + "versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write(REPORT / "definition/pages/pages.json", {"$schema": BASE + "pagesMetadata/1.0.0/schema.json", "pageOrder": [p.key for p in pages], "activePageName": "overview"})
    write(REPORT / "definition/bookmarks/bookmarks.json", {"$schema": BASE + "bookmarksMetadata/1.0.0/schema.json", "items": [{"name": "reset_" + p.key} for p in pages]})
    theme = {"name": "Job Market", "dataColors": [TEAL, NAVY, AMBER, "#779CB5", "#B05855", "#7F8B99"],
             "background": PAPER, "foreground": INK, "tableAccent": TEAL,
             "textClasses": {"title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": INK},
                             "label": {"fontFace": "Segoe UI", "fontSize": 11, "color": MUTED},
                             "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 28, "color": TEAL}}}
    write(HERE / "theme/job_integrity_theme.json", theme)
    write(REPORT / "StaticResources/RegisteredResources/JobMarket.json", theme)
    write(REPORT / "definition/report.json", {"$schema": BASE + "report/3.1.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU02", "type": "SharedResources", "reportVersionAtImport": {"visual": "1.8.89", "page": "1.3.89", "report": "2.0.89"}},
                            "customTheme": {"name": "JobMarket.json", "type": "RegisteredResources", "reportVersionAtImport": {"visual": "1.8.89", "page": "1.3.89", "report": "2.0.89"}}},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources", "items": [{"name": "CY24SU02", "path": "BaseThemes/CY24SU02.json", "type": "BaseTheme"}]},
                             {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "JobMarket.json", "path": "JobMarket.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True}})
    print("Built", HERE / "Job_Market_Quality.pbip", "with", len(pages), "pages and", sum(len(p.visuals) for p in pages), "native visuals.")


if __name__ == "__main__":
    main()
