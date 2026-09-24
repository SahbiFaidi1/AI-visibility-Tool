"""Flask dashboard. Read-only view over the SQLite store."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, request

from ..metrics import compute_metrics, trend
from ..store import Store


def create_app(db_path: str | Path) -> Flask:
    here = Path(__file__).parent
    app = Flask(__name__, template_folder=str(here / "templates"), static_folder=str(here / "static"))
    store = Store(db_path)
    cache: dict[str, dict[str, Any]] = {}

    def metrics_for(run_id: str) -> dict[str, Any]:
        run = store.get_run(run_id)
        if not run:
            abort(404, f"run {run_id} not found")
        key = f"{run_id}:{run['status']}:{run.get('finished_at')}"
        if run["status"] == "running" or key not in cache:
            cache.clear() if len(cache) > 50 else None
            cache[key] = compute_metrics(run, store.answers(run_id))
        return cache[key]

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/runs")
    def api_runs():
        return jsonify(store.list_runs())

    @app.get("/api/run/<run_id>")
    def api_run(run_id: str):
        if run_id == "latest":
            run_id = store.latest_run_id() or ""
            if not run_id:
                return jsonify({"empty": True})
        return jsonify(metrics_for(run_id))

    @app.get("/api/run/<run_id>/answers")
    def api_answers(run_id: str):
        if not store.get_run(run_id):
            abort(404)
        return jsonify(store.answers(run_id))

    @app.get("/api/answer/<int:answer_id>")
    def api_answer(answer_id: int):
        a = store.get_answer(answer_id)
        if not a:
            abort(404)
        return jsonify(a)

    @app.get("/api/trend")
    def api_trend():
        brand = request.args.get("brand")
        runs = [r for r in store.list_runs() if r["status"] in ("done", "aborted") and (not brand or r["brand"] == brand)]
        ms = [metrics_for(r["id"]) for r in runs[:30]]
        return jsonify(trend(ms) if ms else {"points": [], "series": {}, "target": None})

    @app.delete("/api/run/<run_id>")
    def api_delete(run_id: str):
        if not store.get_run(run_id):
            abort(404)
        store.delete_run(run_id)
        cache.clear()
        return jsonify({"deleted": run_id})

    return app
