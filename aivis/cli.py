"""Command-line entry point: `aivis <command>` or `python -m aivis <command>`."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, load_config

PKG_ROOT = Path(__file__).resolve().parent.parent


def _cfg(args):
    try:
        return load_config(args.config)
    except ConfigError as e:
        sys.exit(f"config error: {e}")


def cmd_init(args) -> None:
    for src, dst in (("config.example.yaml", args.config), (".env.example", ".env")):
        s, d = PKG_ROOT / src, Path(dst)
        if d.exists():
            print(f"  keep   {d} (exists)")
        elif s.exists():
            shutil.copy(s, d)
            print(f"  create {d}")
    print("Edit config.yaml (brand, competitors, prompts, providers) and put your API keys in .env.")
    print("Then run:  aivis check   and   aivis run")


def cmd_check(args) -> None:
    from .runner import check_providers
    cfg = _cfg(args)
    print(f"Checking {len(cfg.enabled_providers)} enabled provider(s)...")
    res = check_providers(cfg, args.providers)
    bad = [k for k, v in res.items() if not v.startswith("OK")]
    print(f"\n{len(res) - len(bad)} ok, {len(bad)} not usable.")
    if bad:
        sys.exit(1)


def cmd_run(args) -> None:
    from .runner import run_tracking
    from .providers.base import ProviderError
    cfg = _cfg(args)
    try:
        run_id = run_tracking(cfg, providers=args.providers, limit=args.limit, repeats=args.repeats,
                              sentiment=False if args.no_sentiment else None, notes=args.notes)
    except ProviderError as e:
        sys.exit(str(e))
    print(f"\nView it:  aivis dashboard   (run id {run_id})")
    if args.summary:
        _print_summary(cfg, run_id)


def _print_summary(cfg, run_id: str) -> None:
    from .metrics import compute_metrics
    from .store import Store
    store = Store(cfg.db_path)
    m = compute_metrics(store.get_run(run_id), store.answers(run_id))
    print(f"\n{'#':>2} {'Brand':<20} {'Visibility':>10} {'SoV':>7} {'Pos':>5} {'Sent':>5} {'Cites':>6}")
    for i, b in enumerate(m["ranking"], 1):
        s = m["overall"][b]
        mark = " <- you" if b == m["target"] else ""
        print(f"{i:>2} {b:<20} {_f(s['visibility']):>9}% {_f(s['share_of_voice']):>6}% {_f(s['avg_position']):>5} {_f(s['sentiment']):>5} {_f(s['citation_share']):>5}%{mark}")


def _f(v) -> str:
    return "-" if v is None else str(v)


def cmd_runs(args) -> None:
    from .store import Store
    cfg = _cfg(args)
    runs = Store(cfg.db_path).list_runs()
    if not runs:
        print("No runs yet. Try:  aivis run")
        return
    print(f"{'Run id':<22} {'Started (UTC)':<20} {'Status':<8} {'Answers':>7} {'OK':>5}  Brand")
    for r in runs:
        print(f"{r['id']:<22} {r['started_at'][:19]:<20} {r['status']:<8} {r['n_answers']:>7} {r['n_ok']:>5}  {r['brand']}")


def cmd_show(args) -> None:
    from .store import Store
    cfg = _cfg(args)
    store = Store(cfg.db_path)
    run_id = args.run_id or store.latest_run_id()
    if not run_id or not store.get_run(run_id):
        sys.exit("run not found")
    _print_summary(cfg, run_id)


def cmd_export(args) -> None:
    from .metrics import compute_metrics
    from .store import Store
    cfg = _cfg(args)
    store = Store(cfg.db_path)
    run_id = args.run_id or store.latest_run_id()
    run = store.get_run(run_id) if run_id else None
    if not run:
        sys.exit("run not found")
    answers = store.answers(run_id)
    out = Path(args.out or f"exports/{run_id}.{args.format}")
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        out.write_text(json.dumps({"metrics": compute_metrics(run, answers), "answers": answers}, indent=2))
    else:
        with out.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["run_id", "provider", "model", "prompt_id", "category", "prompt", "repeat", "brand", "mentioned",
                        "position", "count", "sentiment", "citations", "own_domain_citations", "latency_ms", "error"])
            brands = [b["name"] for b in run["config"].get("brands", [])]
            for a in answers:
                by_brand = {m["brand"]: m for m in a["mentions"]}
                for b in brands:
                    m = by_brand.get(b)
                    w.writerow([run_id, a["provider_id"], a["model"], a["prompt_id"], a["category"], a["prompt_text"],
                                a["repeat_index"], b, int(bool(m)), m["position"] if m else "", m["count"] if m else 0,
                                a["sentiment"].get(b, ""), len(a["citations"]),
                                sum(1 for c in a["citations"] if c.get("owner") == b), a["latency_ms"], a["error"] or ""])
    print(f"wrote {out}")


def cmd_dashboard(args) -> None:
    from .dashboard.app import create_app
    cfg = _cfg(args)
    app = create_app(cfg.db_path)
    print(f"Dashboard on http://{args.host}:{args.port}  (db: {cfg.db_path})")
    app.run(host=args.host, port=args.port, debug=args.debug)


def cmd_providers(args) -> None:
    from .providers import REGISTRY, provider_class
    print(f"{'type':<18} {'engine':<18} {'web search':<11} {'default model':<24} sdk")
    for t in REGISTRY:
        c = provider_class(t)
        print(f"{t:<18} {c.label:<18} {'yes' if c.supports_web_search else 'no':<11} {c.default_model or '-':<24} {c.sdk_package or '-'}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="aivis", description="Track how your brand ranks in AI search engines.")
    ap.add_argument("-c", "--config", default="config.yaml", help="path to config.yaml")
    ap.add_argument("--version", action="version", version=f"aivis {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create config.yaml and .env from the examples").set_defaults(fn=cmd_init)

    p = sub.add_parser("check", help="live-test every enabled provider with a tiny prompt")
    p.add_argument("-p", "--providers", nargs="*", help="only these provider ids")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("run", help="run all prompts against all enabled providers")
    p.add_argument("-p", "--providers", nargs="*", help="only these provider ids")
    p.add_argument("-n", "--limit", type=int, help="only the first N prompts (smoke test)")
    p.add_argument("-r", "--repeats", type=int, help="override run.repeats")
    p.add_argument("--no-sentiment", action="store_true", help="skip the sentiment judge")
    p.add_argument("--notes", help="free-text note stored with the run")
    p.add_argument("--summary", action="store_true", help="print the ranking table when done")
    p.set_defaults(fn=cmd_run)

    sub.add_parser("runs", help="list stored runs").set_defaults(fn=cmd_runs)

    p = sub.add_parser("show", help="print the ranking table for a run (default: latest)")
    p.add_argument("run_id", nargs="?")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("export", help="export a run to CSV or JSON")
    p.add_argument("run_id", nargs="?")
    p.add_argument("-f", "--format", choices=["csv", "json"], default="csv")
    p.add_argument("-o", "--out")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("dashboard", help="serve the web dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--debug", action="store_true")
    p.set_defaults(fn=cmd_dashboard)

    sub.add_parser("providers", help="list supported provider types").set_defaults(fn=cmd_providers)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
