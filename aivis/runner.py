"""Orchestrates a tracking run: prompts x providers x repeats, in parallel, with retries."""
from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from typing import Callable, Optional

from .analysis import enrich_answer
from .config import Config, Prompt, ProviderConfig
from .models import Answer
from .providers import build_provider
from .providers.base import Provider, ProviderError
from .providers.mock import MockProvider
from .sentiment import judge_sentiment
from .store import Store

Progress = Callable[[str], None]


def _snapshot(cfg: Config, providers: list[Provider]) -> dict:
    return {
        "brands": [asdict(b) for b in cfg.brands],
        "prompts": [asdict(p) for p in cfg.prompts],
        "providers": [{"id": p.cfg.id, "type": p.cfg.type, "label": p.label, "model": p.model,
                       "web_search": p.web_search} for p in providers],
        "run": asdict(cfg.run),
        "sentiment": asdict(cfg.sentiment),
    }


def build_providers(cfg: Config, only: Optional[list[str]] = None, log: Progress = print) -> list[Provider]:
    out: list[Provider] = []
    for pc in cfg.enabled_providers:
        if only and pc.id not in only:
            continue
        try:
            p = build_provider(pc, cfg.run)
        except ProviderError as e:
            log(f"  skip {pc.id}: {e}")
            continue
        if isinstance(p, MockProvider):
            p.set_brands([b.name for b in cfg.brands], {b.name: b.domains[0] for b in cfg.brands if b.domains})
        out.append(p)
    return out


def _with_retries(fn: Callable[[], Answer], retries: int, log: Progress, label: str) -> Answer:
    delay = 2.0
    last: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:  # provider SDK errors vary; retry everything except config errors
            last = e
            if isinstance(e, ProviderError) or attempt == retries:
                break
            log(f"  retry {label} in {delay:.0f}s ({type(e).__name__}: {str(e)[:120]})")
            time.sleep(delay)
            delay *= 2
    err = f"{type(last).__name__}: {last}" if last else "unknown error"
    return Answer(provider_id="", model="", prompt_id="", prompt_text="", category="", repeat_index=0, error=err[:1000])


def run_tracking(cfg: Config, *, providers: Optional[list[str]] = None, limit: Optional[int] = None,
                 repeats: Optional[int] = None, sentiment: Optional[bool] = None, notes: Optional[str] = None,
                 log: Progress = print, store: Optional[Store] = None) -> str:
    store = store or Store(cfg.db_path)
    provs = build_providers(cfg, providers, log)
    if not provs:
        raise ProviderError("No usable providers. Check config.yaml and .env, then run `aivis check`.")
    prompts: list[Prompt] = cfg.prompts[:limit] if limit else cfg.prompts
    n_rep = repeats or cfg.run.repeats
    use_sent = cfg.sentiment.enabled if sentiment is None else sentiment

    judge: Optional[Provider] = None
    if use_sent:
        jid = cfg.sentiment.provider
        judge = next((p for p in provs if p.cfg.id == jid), None)
        if judge is None and jid:
            pc = cfg.provider(jid)
            if pc:
                try:
                    judge = build_provider(pc, cfg.run)
                    if isinstance(judge, MockProvider):
                        judge.set_brands([b.name for b in cfg.brands], {})
                except ProviderError as e:
                    log(f"  sentiment judge '{jid}' unavailable: {e}")
        if judge is None:
            log("  sentiment disabled (no judge provider available)")

    run_id = store.create_run(cfg.brand.name, _snapshot(cfg, provs), notes)
    total = len(provs) * len(prompts) * n_rep
    log(f"Run {run_id}: {len(prompts)} prompts x {len(provs)} providers x {n_rep} repeat(s) = {total} calls")

    sems = {p.cfg.id: threading.BoundedSemaphore(cfg.run.per_provider_concurrency) for p in provs}
    done = {"n": 0, "err": 0}
    lock = threading.Lock()

    def task(p: Provider, prompt: Prompt, rep: int) -> None:
        label = f"{p.cfg.id}/{prompt.id}" + (f"#{rep}" if n_rep > 1 else "")
        with sems[p.cfg.id]:
            ans = _with_retries(lambda: p.query(prompt.text), cfg.run.retries, log, label)
        ans.provider_id, ans.model = p.cfg.id, p.model
        ans.prompt_id, ans.prompt_text, ans.category, ans.repeat_index = prompt.id, prompt.text, prompt.category, rep
        enrichment = enrich_answer(ans, cfg.brands) if ans.ok else {"mentions": [], "citations": []}
        sent: dict[str, str] = {}
        if judge and ans.ok and enrichment["mentions"]:
            names = [m["brand"] for m in enrichment["mentions"]]
            try:
                with sems.get(judge.cfg.id, threading.BoundedSemaphore(2)):
                    sent = judge_sentiment(judge, ans.text, names)
            except Exception as e:
                log(f"  sentiment failed for {label}: {type(e).__name__}: {str(e)[:100]}")
        store.save_answer(run_id, p.label, ans, prompt.id, prompt.category, rep, enrichment, sent)
        with lock:
            done["n"] += 1
            if ans.error:
                done["err"] += 1
            status = "ERR " + ans.error[:80] if ans.error else f"{len(enrichment['mentions'])} brands, {len(enrichment['citations'])} sources, {ans.latency_ms} ms"
            log(f"[{done['n']}/{total}] {label}: {status}")

    status = "done"
    try:
        with ThreadPoolExecutor(max_workers=cfg.run.concurrency) as pool:
            futures = [pool.submit(task, p, pr, r) for p in provs for pr in prompts for r in range(n_rep)]
            for f in as_completed(futures):
                exc = f.exception()
                if exc:
                    log("  worker crashed: " + "".join(traceback.format_exception_only(type(exc), exc)).strip())
    except KeyboardInterrupt:
        status = "aborted"
        log("Interrupted; saving what we have.")
    if status == "done" and done["err"] == total:
        status = "failed"
    store.finish_run(run_id, status)
    log(f"Finished {run_id} ({status}): {done['n'] - done['err']} ok, {done['err']} errors")
    return run_id


def check_providers(cfg: Config, only: Optional[list[str]] = None, log: Progress = print) -> dict[str, str]:
    """Live smoke test of each enabled provider. Returns id -> status."""
    results: dict[str, str] = {}
    for pc in cfg.enabled_providers:
        if only and pc.id not in only:
            continue
        try:
            p = build_provider(pc, cfg.run)
        except ProviderError as e:
            results[pc.id] = f"NOT CONFIGURED  {e}"
            log(f"  {pc.id:<14} NOT CONFIGURED  {e}")
            continue
        t0 = time.perf_counter()
        try:
            reply = p.ping()
            ms = int((time.perf_counter() - t0) * 1000)
            results[pc.id] = f"OK  {p.model or ''} ({ms} ms) -> {reply!r}"
            log(f"  {pc.id:<14} OK  {p.label} {p.model or ''} {ms} ms  web_search={'on' if p.web_search else 'off'}")
        except Exception as e:
            results[pc.id] = f"FAILED  {type(e).__name__}: {str(e)[:200]}"
            log(f"  {pc.id:<14} FAILED  {type(e).__name__}: {str(e)[:200]}")
    return results
