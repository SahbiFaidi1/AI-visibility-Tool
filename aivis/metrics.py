"""Aggregate stored answers into the standard AI-visibility metrics.

Definitions (matching what Peec, Profound, Otterly and the open-source trackers report):
  visibility      % of eligible answers in which the brand is mentioned
  share_of_voice  brand's mentioning answers / all tracked brands' mentioning answers
  avg_position    mean order of first mention among tracked brands (1 = mentioned first)
  first_rate      % of eligible answers where the brand is the first tracked brand mentioned
  sentiment       0-100 = (positive + 0.5 * neutral) / graded mentions
  citation_share  % of all cited/retrieved URLs that point at the brand's own domains

"Eligible" = successful answers to non-branded prompts. Branded prompts (those that name
the tracked brand) are still stored and shown, but excluded from the competitive ranking.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Optional

from .sentiment import sentiment_score

BRANDED = "branded"


def _pct(num: float, den: float) -> Optional[float]:
    return round(100.0 * num / den, 1) if den else None


def _brand_stats(brand: str, answers: list[dict[str, Any]], total_citations: int) -> dict[str, Any]:
    n = len(answers)
    mentioned = [a for a in answers if any(m["brand"] == brand for m in a["mentions"])]
    positions = [next(m["position"] for m in a["mentions"] if m["brand"] == brand) for a in mentioned]
    first = sum(1 for p in positions if p == 1)
    labels = [a["sentiment"].get(brand) for a in mentioned if a["sentiment"].get(brand)]
    own_cites = sum(1 for a in answers for c in a["citations"] if c.get("owner") == brand)
    total_occurrences = sum(m["count"] for a in mentioned for m in a["mentions"] if m["brand"] == brand)
    return {
        "answers": n,
        "mentioned": len(mentioned),
        "occurrences": total_occurrences,
        "visibility": _pct(len(mentioned), n),
        "avg_position": round(mean(positions), 2) if positions else None,
        "first_rate": _pct(first, n),
        "sentiment": sentiment_score(labels),
        "sentiment_counts": {k: labels.count(k) for k in ("positive", "neutral", "negative")},
        "own_citations": own_cites,
        "citation_share": _pct(own_cites, total_citations),
        "share_of_voice": None,  # filled once all brands are known
    }


def _fill_sov(table: dict[str, dict[str, Any]]) -> None:
    total = sum(s["mentioned"] for s in table.values())
    for s in table.values():
        s["share_of_voice"] = _pct(s["mentioned"], total)


def _rank(table: dict[str, dict[str, Any]]) -> list[str]:
    def key(name: str):
        s = table[name]
        return (-(s["visibility"] or 0), -(s["share_of_voice"] or 0), s["avg_position"] or 99, name.lower())
    return sorted(table, key=key)


def compute_metrics(run: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any]:
    cfg = run.get("config", {})
    brands_cfg = cfg.get("brands") or []
    brand_names = [b["name"] for b in brands_cfg]
    target = next((b["name"] for b in brands_cfg if b.get("is_target")), run.get("brand"))

    providers_cfg = {p["id"]: p for p in cfg.get("providers", [])}
    provider_ids: list[str] = []
    for a in answers:
        if a["provider_id"] not in provider_ids:
            provider_ids.append(a["provider_id"])

    ok = [a for a in answers if not a.get("error") and (a.get("text") or "").strip()]
    eligible = [a for a in ok if a["category"] != BRANDED]
    total_cites = sum(len(a["citations"]) for a in eligible)

    overall = {b: _brand_stats(b, eligible, total_cites) for b in brand_names}
    _fill_sov(overall)

    by_provider: dict[str, dict[str, Any]] = {}
    providers_out: list[dict[str, Any]] = []
    for pid in provider_ids:
        p_all = [a for a in answers if a["provider_id"] == pid]
        p_ok = [a for a in eligible if a["provider_id"] == pid]
        p_cites = sum(len(a["citations"]) for a in p_ok)
        table = {b: _brand_stats(b, p_ok, p_cites) for b in brand_names}
        _fill_sov(table)
        by_provider[pid] = {"brands": table, "ranking": _rank(table)}
        lat = [a["latency_ms"] for a in p_all if a.get("latency_ms")]
        providers_out.append({
            "id": pid,
            "label": p_all[0]["provider_label"] if p_all else providers_cfg.get(pid, {}).get("label", pid),
            "model": p_all[0]["model"] if p_all else providers_cfg.get(pid, {}).get("model"),
            "answers": len(p_all),
            "ok": sum(1 for a in p_all if not a.get("error")),
            "errors": sum(1 for a in p_all if a.get("error")),
            "avg_latency_ms": int(mean(lat)) if lat else None,
            "target_rank": (by_provider[pid]["ranking"].index(target) + 1) if target in by_provider[pid]["ranking"] else None,
        })

    # prompt x provider matrix (first repeat shown; repeats aggregated as mention rate)
    prompts: dict[str, dict[str, Any]] = {}
    for a in answers:
        row = prompts.setdefault(a["prompt_id"], {"prompt_id": a["prompt_id"], "text": a["prompt_text"],
                                                  "category": a["category"], "cells": {}})
        cell = row["cells"].setdefault(a["provider_id"], {"answer_ids": [], "mentioned": 0, "runs": 0, "positions": [],
                                                          "brands": [], "errors": 0})
        cell["answer_ids"].append(a["id"])
        if a.get("error"):
            cell["errors"] += 1
            continue
        cell["runs"] += 1
        tm = next((m for m in a["mentions"] if m["brand"] == target), None)
        if tm:
            cell["mentioned"] += 1
            cell["positions"].append(tm["position"])
        for m in a["mentions"]:
            if m["brand"] not in cell["brands"]:
                cell["brands"].append(m["brand"])
    for row in prompts.values():
        for cell in row["cells"].values():
            cell["mention_rate"] = _pct(cell["mentioned"], cell["runs"])
            cell["position"] = round(mean(cell["positions"]), 1) if cell["positions"] else None
            cell.pop("positions", None)

    # sources
    src: dict[str, dict[str, Any]] = {}
    for a in eligible:
        seen_here: set[str] = set()
        for c in a["citations"]:
            d = c["domain"]
            s = src.setdefault(d, {"domain": d, "owner": c.get("owner", "other"), "citations": 0, "answers": 0,
                                   "providers": set(), "kinds": defaultdict(int)})
            s["citations"] += 1
            s["kinds"][c.get("kind", "cited")] += 1
            s["providers"].add(a["provider_id"])
            if d not in seen_here:
                s["answers"] += 1
                seen_here.add(d)
    sources = []
    for s in src.values():
        s["providers"] = sorted(s["providers"])
        s["kinds"] = dict(s["kinds"])
        s["answer_pct"] = _pct(s["answers"], len(eligible))
        sources.append(s)
    sources.sort(key=lambda s: (-s["citations"], s["domain"]))

    ranking = _rank(overall)
    target_rank = ranking.index(target) + 1 if target in ranking else None
    leader = ranking[0] if ranking else None

    return {
        "run": {k: run.get(k) for k in ("id", "started_at", "finished_at", "status", "brand", "notes")},
        "target": target,
        "brands": brands_cfg,
        "providers": providers_out,
        "prompts": list(prompts.values()),
        "overall": overall,
        "by_provider": by_provider,
        "ranking": ranking,
        "target_rank": target_rank,
        "leader": leader,
        "sources": sources,
        "totals": {
            "answers": len(answers),
            "ok": len(ok),
            "errors": len(answers) - len(ok),
            "eligible": len(eligible),
            "branded_excluded": len(ok) - len(eligible),
            "citations": total_cites,
            "prompts": len(prompts),
            "providers": len(provider_ids),
        },
    }


def trend(runs_with_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Visibility over time for every brand, oldest first."""
    ordered = sorted(runs_with_metrics, key=lambda m: m["run"]["started_at"] or "")
    brands = ordered[-1]["brands"] if ordered else []
    series = {b["name"]: [] for b in brands}
    points = []
    for m in ordered:
        points.append({"run_id": m["run"]["id"], "started_at": m["run"]["started_at"]})
        for b in series:
            s = m["overall"].get(b)
            series[b].append(s["visibility"] if s else None)
    return {"points": points, "series": series, "target": ordered[-1]["target"] if ordered else None}
