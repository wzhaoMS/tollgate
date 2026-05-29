"""Load the seed chokepoint-database.csv into SQLite + write keyword dictionary."""
from __future__ import annotations
import csv
import json
from pathlib import Path
from .config import DATA_DIR
from . import db

ROOT = Path(__file__).resolve().parent.parent
SEED_CSV = ROOT / "chokepoint-database.csv"

# Smart-money X accounts + customer URLs + EDGAR keyword dictionary,
# derived from initial research subagent output. Committed as JSON so
# scrapers can read it directly without re-running research each time.
KEYWORD_DICT = {
    "supplier_lock": [
        "sole source", "single source", "sole supplier", "primary supplier",
        "strategic supplier", "dependent on", "critical material",
        "exclusively supplied", "sole manufacturer", "sole provider",
        "limited sources", "principal supplier", "concentrated supplier base",
        "supplier concentration", "supply dependent", "reliant on", "only source",
        "qualified sole source", "exclusive supplier agreement",
    ],
    "capacity_signals": [
        "capacity expansion", "wafer starts", "long-term supply agreement",
        "purchase commitment", "take-or-pay", "offtake", "capacity constraint",
        "capacity limitation", "yield improvement", "production ramp",
        "manufacturing capacity", "wafer allocation", "supply constraint",
        "tight supply", "constrained supply", "advanced node capacity",
        "leading-edge capacity", "node transition", "foundry capacity",
        "backlog", "long lead time", "allocation",
    ],
    "ai_chokepoint_themes": [
        "indium phosphide", "InP wafer", "co-packaged optics", "CPO",
        "external light source", "ELSFP", "silicon photonics", "SiC foundry",
        "SOI wafer", "HBM", "advanced packaging", "CoWoS", "chiplet", "UCIe",
        "die-to-die interconnect", "3D packaging", "optical I/O",
        "integrated photonics", "high-bandwidth memory",
    ],
    "govt_backstop": [
        "CHIPS Act", "CHIPS and Science", "Department of Energy", "DoE grant",
        "federal grant", "federal funding", "loan guarantee", "Defense Production Act",
        "DPA Title III", "Title III", "government award", "government grant",
        "direct funding", "preliminary memorandum of terms", "PMT",
        "Inflation Reduction Act", "investment tax credit", "Section 48D",
        "subsidy", "state incentive", "matching funds", "appropriation",
    ],
}


def _row_from_csv(rec: dict) -> dict:
    def _num(v):
        if v is None or v == "" or v == "unknown":
            return None
        try:
            return float(v)
        except ValueError:
            return None

    def _int(v):
        n = _num(v)
        return int(n) if n is not None else None

    return {
        "ticker": rec["Ticker"].strip(),
        "chokepoint": rec.get("Chokepoint") or None,
        "end_customer": rec.get("End_Customer") or None,
        "evidence_grade": (rec.get("Evidence_Grade") or "U")[:1],
        "evidence_source_url": rec.get("Evidence_Source_URL") or None,
        "capacity": rec.get("Capacity") or None,
        "demand_proxy": rec.get("Demand_Proxy") or None,
        "capacity_gap_pct": _num(rec.get("Capacity_Gap_Pct")),
        "expansion_timeline_mo": _int(rec.get("Expansion_Timeline_Mo")),
        "substitutes": rec.get("Substitutes") or None,
        "market_cap_usd": _num(rec.get("Market_Cap_USD")),
        "revenue_ttm_usd": _num(rec.get("Revenue_TTM_USD")),
        "ev_sales": _num(rec.get("EV_Sales")),
        "next_catalyst": rec.get("Next_Catalyst") or None,
        "catalyst_score": _int(rec.get("Catalyst_Score")),
        "crowdedness": (rec.get("Crowdedness") or "unknown").lower(),
        "capital_structure_flag": rec.get("Capital_Structure_Flag") or "unknown",
        "time_to_truth_days": _int(rec.get("Time_to_Truth_Days")),
        "decision": rec.get("Decision") or "Watch",
        "last_updated": rec.get("Last_Updated") or None,
    }


def load_seed_csv() -> int:
    db.init()
    n = 0
    with SEED_CSV.open(encoding="utf-8") as f, db.connect() as cx:
        for rec in csv.DictReader(f):
            db.upsert_chokepoint(cx, _row_from_csv(rec))
            n += 1
    return n


def write_keyword_dict() -> Path:
    out = DATA_DIR / "keywords.json"
    out.write_text(json.dumps(KEYWORD_DICT, indent=2), encoding="utf-8")
    return out


def main() -> None:
    db.init()
    n = load_seed_csv()
    p = write_keyword_dict()
    print(f"Seeded {n} chokepoint rows into {db.DB_PATH}")  # type: ignore[attr-defined]
    print(f"Wrote keyword dictionary -> {p}")


if __name__ == "__main__":
    main()
