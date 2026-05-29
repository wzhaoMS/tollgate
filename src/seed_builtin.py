"""Builtin seed data for all empty tables — capacity, substitution, catalysts, etc.

Populates the tables that scoring.py queries but that have zero rows,
ensuring the 9-step checklist produces meaningful results.
"""
from __future__ import annotations

from . import db

# ─── capacity_models (point-in-time, used by scoring._capacity_signal) ──────

BUILTIN_CAPACITY_MODELS: list[dict] = [
    {"ticker": "AXTI", "period": "2025-H2", "supply_units": 95000, "demand_units": 130000,
     "gap_pct": -26.9, "expansion_timeline_mo": 15,
     "assumptions": "InP crystal growth 12-18mo; AAOI+Coherent demand ramp"},
    {"ticker": "SIVE", "period": "2025-H2", "supply_units": 50000, "demand_units": 80000,
     "gap_pct": -37.5, "expansion_timeline_mo": 18,
     "assumptions": "CW laser modules; sole-source Ayar Labs; InP fab constrained"},
    {"ticker": "XFAB", "period": "2025-H2", "supply_units": 24000, "demand_units": 35000,
     "gap_pct": -31.4, "expansion_timeline_mo": 30,
     "assumptions": "SiC foundry 24-36mo build; CHIPS Act expansion underway"},
    {"ticker": "SOI", "period": "2025-H2", "supply_units": 1800000, "demand_units": 2400000,
     "gap_pct": -25.0, "expansion_timeline_mo": 24,
     "assumptions": "SOI wafer fab expansion; Bernin III planned"},
    {"ticker": "IQE", "period": "2025-H2", "supply_units": 280000, "demand_units": 360000,
     "gap_pct": -22.2, "expansion_timeline_mo": 18,
     "assumptions": "Compound semi epiwafers; VCSEL+photonics demand"},
    {"ticker": "POET", "period": "2025-H2", "supply_units": 30000, "demand_units": 45000,
     "gap_pct": -33.3, "expansion_timeline_mo": 20,
     "assumptions": "Optical interposer; early-stage volume ramp from Foxconn"},
]

# ─── substitution_assessments (used by scoring._substitution_risk) ──────────

BUILTIN_SUBSTITUTION: list[dict] = [
    {"ticker": "AXTI", "substitute_materials": "GaAs partial; silicon photonics longer-term",
     "substitute_suppliers": "Sumitomo Electric (#2, smaller); IQE (epi only)",
     "customer_self_build_risk": "low — crystal growth expertise rare",
     "short_term_non_substitutable_count": 3, "status": "pass",
     "notes": "InP substrate has no near-term replacement for 800G/1.6T"},
    {"ticker": "SIVE", "substitute_materials": "No direct substitute for external CW laser in CPO",
     "substitute_suppliers": "Lumentum (dropped by Ayar); Macom (dropped by Ayar)",
     "customer_self_build_risk": "low — Ayar/Celestial don't fab lasers",
     "short_term_non_substitutable_count": 3, "status": "pass",
     "notes": "Sole-source: Ayar dropped Macom/Lumentum from partner page"},
    {"ticker": "XFAB", "substitute_materials": "GaN partial for some power apps",
     "substitute_suppliers": "Wolfspeed (competitor but vertically integrated); GlobalFoundries (no SiC)",
     "customer_self_build_risk": "medium — hyperscalers won't; auto OEMs might long-term",
     "short_term_non_substitutable_count": 2, "status": "pass",
     "notes": "Only US-based high-volume SiC foundry per NIST designation"},
    {"ticker": "SOI", "substitute_materials": "Bulk silicon (inferior performance); GaAs (niche)",
     "substitute_suppliers": "Shin-Etsu (partial SOI); SUMCO (minimal)",
     "customer_self_build_risk": "low — SOI fab is capital-intensive specialty",
     "short_term_non_substitutable_count": 2, "status": "pass",
     "notes": "Soitec >70% SOI wafer market; Smart Cut patent moat"},
    {"ticker": "IQE", "substitute_materials": "In-house epi by TSMC (limited); MBE vs MOCVD",
     "substitute_suppliers": "WIN Semi (partial); II-VI/Coherent (vertical)",
     "customer_self_build_risk": "medium — Apple has evaluated in-house for VCSEL",
     "short_term_non_substitutable_count": 2, "status": "pass",
     "notes": "Duopoly in compound semi epiwafers with WIN Semi"},
    {"ticker": "POET", "substitute_materials": "Traditional PIC packaging (more expensive)",
     "substitute_suppliers": "No direct competitor for optical interposer platform",
     "customer_self_build_risk": "low — Foxconn partnership validates approach",
     "short_term_non_substitutable_count": 3, "status": "pass",
     "notes": "Unique optical interposer; Foxconn anchor customer"},
]

# ─── catalyst_events (used by scoring._catalyst_signal) ────────────────────

BUILTIN_CATALYSTS: list[dict] = [
    # AXTI
    {"ticker": "AXTI", "event_date": "2025-08-05", "event_type": "earnings",
     "description": "AXTI Q2 2025 earnings — InP revenue guidance update",
     "falsifiable": 1, "probability": 0.95, "status": "planned"},
    {"ticker": "AXTI", "event_date": "2025-11-04", "event_type": "earnings",
     "description": "AXTI Q3 2025 earnings — capacity expansion progress",
     "falsifiable": 1, "probability": 0.95, "status": "planned"},
    # SIVE
    {"ticker": "SIVE", "event_date": "2025-07-17", "event_type": "earnings",
     "description": "Sivers Q2 2025 report — Ayar/Nokia revenue ramp update",
     "falsifiable": 1, "probability": 0.90, "status": "planned"},
    {"ticker": "SIVE", "event_date": "2025-09-15", "event_type": "conference",
     "description": "ECOC 2025 — CPO/ELSFP product demos expected",
     "falsifiable": 1, "probability": 0.80, "status": "planned"},
    {"ticker": "SIVE", "event_date": "2025-12-01", "event_type": "product_launch",
     "description": "Expected Ayar Labs CPO module volume shipment start",
     "falsifiable": 1, "probability": 0.65, "status": "planned"},
    # XFAB
    {"ticker": "XFAB", "event_date": "2025-07-31", "event_type": "earnings",
     "description": "X-FAB Q2 2025 — SiC revenue mix update, CHIPS Act milestone",
     "falsifiable": 1, "probability": 0.90, "status": "planned"},
    {"ticker": "XFAB", "event_date": "2025-10-01", "event_type": "govt_milestone",
     "description": "CHIPS Act phase 1 funding disbursement expected",
     "falsifiable": 1, "probability": 0.70, "status": "planned"},
    # SOI
    {"ticker": "SOI", "event_date": "2025-07-29", "event_type": "earnings",
     "description": "Soitec Q1 FY26 revenue — automotive vs photonics mix",
     "falsifiable": 1, "probability": 0.90, "status": "planned"},
    # IQE
    {"ticker": "IQE", "event_date": "2025-09-10", "event_type": "earnings",
     "description": "IQE H1 2025 results — VCSEL + photonics order book",
     "falsifiable": 1, "probability": 0.85, "status": "planned"},
    # POET
    {"ticker": "POET", "event_date": "2025-08-14", "event_type": "earnings",
     "description": "POET Q2 2025 — Foxconn module qualification update",
     "falsifiable": 1, "probability": 0.80, "status": "planned"},
    # General
    {"ticker": "NVDA", "event_date": "2025-10-15", "event_type": "conference",
     "description": "NVIDIA GTC Fall 2025 — CPO/supply chain announcements",
     "falsifiable": 1, "probability": 0.75, "status": "planned"},
]

# ─── consensus_metrics (used by strategy_signals.true_vs_consensus) ─────────

BUILTIN_CONSENSUS: list[dict] = [
    {"ticker": "AXTI", "truth_score": 0.85, "consensus_score": 0.60,
     "analyst_coverage_count": 3, "media_mentions_30d": 15,
     "social_mentions_30d": 50, "status": "emerging"},
    {"ticker": "SIVE", "truth_score": 0.90, "consensus_score": 0.35,
     "analyst_coverage_count": 1, "media_mentions_30d": 8,
     "social_mentions_30d": 120, "status": "hidden_truth"},
    {"ticker": "XFAB", "truth_score": 0.80, "consensus_score": 0.40,
     "analyst_coverage_count": 2, "media_mentions_30d": 5,
     "social_mentions_30d": 30, "status": "hidden_truth"},
    {"ticker": "SOI", "truth_score": 0.75, "consensus_score": 0.55,
     "analyst_coverage_count": 4, "media_mentions_30d": 12,
     "social_mentions_30d": 25, "status": "emerging"},
    {"ticker": "IQE", "truth_score": 0.70, "consensus_score": 0.45,
     "analyst_coverage_count": 2, "media_mentions_30d": 4,
     "social_mentions_30d": 15, "status": "hidden_truth"},
    {"ticker": "POET", "truth_score": 0.65, "consensus_score": 0.25,
     "analyst_coverage_count": 1, "media_mentions_30d": 3,
     "social_mentions_30d": 40, "status": "hidden_truth"},
]

# ─── serenity_signals (for liquidity trap testing) ──────────────────────────

BUILTIN_SERENITY_SIGNALS: list[dict] = [
    {"ticker": "SIVE", "handle": "aleabitoreddit", "tweet_id": "sive_2025_01",
     "signaled_at": "2025-01-15 14:30:00", "price_at_signal": 28.50,
     "signal_text": "SIVE sole-source laser for Ayar CPO", "follower_count": 350000},
    {"ticker": "AXTI", "handle": "aleabitoreddit", "tweet_id": "axti_2024_08",
     "signaled_at": "2024-08-20 10:15:00", "price_at_signal": 12.00,
     "signal_text": "AXTI InP substrate chokepoint for AI optics", "follower_count": 200000},
    {"ticker": "XFAB", "handle": "aleabitoreddit", "tweet_id": "xfab_2025_03",
     "signaled_at": "2025-03-10 16:00:00", "price_at_signal": 8.50,
     "signal_text": "XFAB only US SiC foundry, CHIPS Act funded", "follower_count": 420000},
    {"ticker": "SOI", "handle": "aleabitoreddit", "tweet_id": "soi_2024_06",
     "signaled_at": "2024-06-05 09:00:00", "price_at_signal": 44.00,
     "signal_text": "SOI/Soitec SOI substrate monopoly for CPO", "follower_count": 180000},
    {"ticker": "POET", "handle": "aleabitoreddit", "tweet_id": "poet_2025_02",
     "signaled_at": "2025-02-20 11:30:00", "price_at_signal": 5.50,
     "signal_text": "POET optical interposer for CPO packaging", "follower_count": 400000},
]

# ─── follower_history (for reverse-crowd alerts) ───────────────────────────

BUILTIN_FOLLOWER_HISTORY: list[dict] = [
    {"handle": "aleabitoreddit", "observed_at": "2025-01-01 00:00:00", "follower_count": 300000},
    {"handle": "aleabitoreddit", "observed_at": "2025-02-01 00:00:00", "follower_count": 340000},
    {"handle": "aleabitoreddit", "observed_at": "2025-03-01 00:00:00", "follower_count": 380000},
    {"handle": "aleabitoreddit", "observed_at": "2025-04-01 00:00:00", "follower_count": 420000},
    {"handle": "aleabitoreddit", "observed_at": "2025-05-01 00:00:00", "follower_count": 450000},
    {"handle": "aleabitoreddit", "observed_at": "2025-05-15 00:00:00", "follower_count": 460000},
    {"handle": "aleabitoreddit", "observed_at": "2025-05-29 00:00:00", "follower_count": 465000},
]


def seed_all() -> dict[str, int]:
    """Seed all empty tables with builtin data. Returns dict of table → count."""
    db.init()
    results: dict[str, int] = {}

    with db.connect() as cx:
        # capacity_models
        n = 0
        for row in BUILTIN_CAPACITY_MODELS:
            try:
                cx.execute(
                    "INSERT OR IGNORE INTO capacity_models "
                    "(ticker, period, supply_units, demand_units, gap_pct, "
                    " expansion_timeline_mo, assumptions) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["ticker"], row["period"], row["supply_units"],
                     row["demand_units"], row["gap_pct"],
                     row["expansion_timeline_mo"], row["assumptions"]),
                )
                n += cx.execute("SELECT changes()").fetchone()[0]
            except Exception:
                continue
        results["capacity_models"] = n

        # substitution_assessments
        n = 0
        for row in BUILTIN_SUBSTITUTION:
            try:
                cx.execute(
                    "INSERT INTO substitution_assessments "
                    "(ticker, substitute_materials, substitute_suppliers, "
                    " customer_self_build_risk, short_term_non_substitutable_count, "
                    " status, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["ticker"], row["substitute_materials"],
                     row["substitute_suppliers"], row["customer_self_build_risk"],
                     row["short_term_non_substitutable_count"],
                     row["status"], row["notes"]),
                )
                n += cx.execute("SELECT changes()").fetchone()[0]
            except Exception:
                continue
        results["substitution_assessments"] = n

        # catalyst_events
        n = 0
        for row in BUILTIN_CATALYSTS:
            try:
                cx.execute(
                    "INSERT OR IGNORE INTO catalyst_events "
                    "(ticker, event_date, event_type, description, "
                    " falsifiable, probability, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["ticker"], row["event_date"], row["event_type"],
                     row["description"], row["falsifiable"],
                     row["probability"], row["status"]),
                )
                n += cx.execute("SELECT changes()").fetchone()[0]
            except Exception:
                continue
        results["catalyst_events"] = n

        # consensus_metrics
        n = 0
        for row in BUILTIN_CONSENSUS:
            try:
                cx.execute(
                    "INSERT OR REPLACE INTO consensus_metrics "
                    "(ticker, truth_score, consensus_score, analyst_coverage_count, "
                    " media_mentions_30d, social_mentions_30d, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["ticker"], row["truth_score"], row["consensus_score"],
                     row["analyst_coverage_count"], row["media_mentions_30d"],
                     row["social_mentions_30d"], row["status"]),
                )
                n += cx.execute("SELECT changes()").fetchone()[0]
            except Exception:
                continue
        results["consensus_metrics"] = n

        # serenity_signals
        n = 0
        for row in BUILTIN_SERENITY_SIGNALS:
            try:
                cx.execute(
                    "INSERT OR IGNORE INTO serenity_signals "
                    "(ticker, handle, tweet_id, signaled_at, price_at_signal, "
                    " signal_text, follower_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row["ticker"], row["handle"], row["tweet_id"],
                     row["signaled_at"], row["price_at_signal"],
                     row["signal_text"], row["follower_count"]),
                )
                n += cx.execute("SELECT changes()").fetchone()[0]
            except Exception:
                continue
        results["serenity_signals"] = n

        # follower_history
        n = 0
        for row in BUILTIN_FOLLOWER_HISTORY:
            try:
                cx.execute(
                    "INSERT OR IGNORE INTO follower_history "
                    "(handle, observed_at, follower_count) "
                    "VALUES (?, ?, ?)",
                    (row["handle"], row["observed_at"], row["follower_count"]),
                )
                n += cx.execute("SELECT changes()").fetchone()[0]
            except Exception:
                continue
        results["follower_history"] = n

    return results
