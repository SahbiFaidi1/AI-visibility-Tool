"""Full pipeline with the mock provider: config -> run -> store -> metrics -> dashboard API."""
import textwrap

import pytest

from aivis.config import load_config
from aivis.metrics import compute_metrics
from aivis.runner import check_providers, run_tracking
from aivis.store import Store

CONFIG = """
brand:
  name: Tesla
  domains: [tesla.com]
competitors:
  - name: BMW
    domains: [bmw.com]
  - name: Mercedes-Benz
    aliases: [Mercedes]
    domains: [mercedes-benz.com]
  - name: Toyota
    domains: [toyota.com]
prompts:
  - text: which electric car brands are the most reliable
  - text: best luxury car brands
    category: discovery
  - text: is a Tesla worth it
    category: branded
providers:
  - id: mock-a
    type: mock
  - id: mock-b
    type: mock
  - id: chatgpt
    type: openai
    enabled: false
run:
  repeats: 2
  concurrency: 4
sentiment:
  enabled: true
  provider: mock-a
storage:
  db: data/test.db
"""


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(CONFIG))
    return load_config(p)


def test_config_loads(cfg):
    assert cfg.brand.name == "Tesla" and cfg.brand.is_target
    assert [b.name for b in cfg.competitors] == ["BMW", "Mercedes-Benz", "Toyota"]
    assert len(cfg.prompts) == 3 and cfg.prompts[2].category == "branded"
    assert [p.id for p in cfg.enabled_providers] == ["mock-a", "mock-b"]
    assert cfg.db_path.name == "test.db"


def test_check_and_run_and_metrics(cfg):
    logs = []
    res = check_providers(cfg, log=logs.append)
    assert all(v.startswith("OK") for v in res.values()), res

    run_id = run_tracking(cfg, log=logs.append)
    store = Store(cfg.db_path)
    run = store.get_run(run_id)
    assert run["status"] == "done"
    answers = store.answers(run_id)
    assert len(answers) == 3 * 2 * 2  # prompts x providers x repeats
    assert all(a["error"] is None for a in answers)
    branded = [a for a in answers if a["category"] == "branded"]
    assert all(any(m["brand"] == "Tesla" for m in a["mentions"]) for a in branded)

    m = compute_metrics(run, answers)
    assert m["target"] == "Tesla"
    assert m["totals"]["eligible"] == 8 and m["totals"]["branded_excluded"] == 4
    assert set(m["overall"]) == {"Tesla", "BMW", "Mercedes-Benz", "Toyota"}
    sov = sum(s["share_of_voice"] or 0 for s in m["overall"].values())
    assert 99 <= sov <= 101
    assert set(m["by_provider"]) == {"mock-a", "mock-b"}
    assert len(m["prompts"]) == 3
    assert m["ranking"] and m["target_rank"] in range(1, 5)
    assert m["sources"] and all("answer_pct" in s for s in m["sources"])
    # sentiment was judged for at least one mention
    assert any(a["sentiment"] for a in answers)


def test_dashboard_api(cfg):
    from aivis.dashboard.app import create_app

    run_id = run_tracking(cfg, log=lambda s: None, sentiment=False)
    app = create_app(cfg.db_path)
    client = app.test_client()
    assert client.get("/").status_code == 200
    runs = client.get("/api/runs").get_json()
    assert runs[0]["id"] == run_id
    data = client.get("/api/run/latest").get_json()
    assert data["run"]["id"] == run_id and data["target"] == "Tesla"
    aid = data["prompts"][0]["cells"]["mock-a"]["answer_ids"][0]
    ans = client.get(f"/api/answer/{aid}").get_json()
    assert ans["text"] and "mentions" in ans
    t = client.get("/api/trend").get_json()
    assert t["points"] and "Tesla" in t["series"]
    assert client.get("/api/run/nope").status_code == 404


def test_run_filters_and_limit(cfg):
    run_id = run_tracking(cfg, providers=["mock-b"], limit=1, repeats=1, sentiment=False, log=lambda s: None)
    answers = Store(cfg.db_path).answers(run_id)
    assert len(answers) == 1 and answers[0]["provider_id"] == "mock-b"
