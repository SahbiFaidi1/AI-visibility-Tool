# AI Visibility Tracker

See how your brand ranks against competitors inside AI search engines: ChatGPT, Claude, Gemini, Perplexity, Mistral, and any OpenAI-compatible model (Grok, DeepSeek, OpenRouter, a local Ollama...).

The tool asks each engine the questions a real buyer would ask, then measures who gets mentioned, in what order, how favourably, and which websites the engines rely on. That is the same methodology used by commercial trackers such as Peec AI, Profound and Otterly; here you bring your own API keys and keep the data.

```
aivis run --summary

 #  Brand               Visibility    SoV   Pos  Sent  Cites
 1  Toyota                   75.0%  21.4%  1.80  83.3   4.2%
 2  Tesla                    62.5%  17.9%  2.10  70.0  12.5% <- you
 3  BMW                      50.0%  14.3%  2.75  62.5   0.0%
 ...
```

## What it measures

| Metric | Definition |
|---|---|
| **Visibility** | % of answers in which the brand is mentioned |
| **Share of voice** | brand's mentions / all tracked brands' mentions |
| **Average position** | order of first mention among tracked brands (1 = mentioned first) |
| **First rate** | % of answers where the brand is the first one mentioned |
| **Sentiment** | 0–100, judged by an LLM per mention: all positive = 100, neutral = 50, negative = 0 |
| **Citation share** | % of all cited or retrieved URLs that point at the brand's own domains |
| **Sources** | which domains the engines cite, how often, and whether they belong to you or a competitor |

Everything is broken down per engine, so you can see that you rank #1 in Perplexity but #6 in ChatGPT. Runs are stored in SQLite, so visibility over time is charted as you re-run.

Prompts that name your own brand (category `branded`) are stored and shown but excluded from the ranking, because you will always be mentioned in them.

## Quick start

```bash
git clone https://github.com/SahbiFaidi1/AI-visibility-Tool.git
cd AI-visibility-Tool
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"        # or: pip install -r requirements.txt

aivis init                         # creates config.yaml and .env from the examples
```

1. Edit `config.yaml`: your brand, competitors, the prompts to ask, and which providers to use.
2. Put API keys in `.env` for the providers you enabled.
3. Verify and run:

```bash
aivis check                 # one tiny live call per provider; tells you what is misconfigured
aivis run --summary         # full run, prints the ranking table
aivis dashboard             # http://127.0.0.1:5000
```

No keys yet? Enable the `mock` provider in `config.yaml` and run; it fabricates plausible answers so you can see the whole pipeline and dashboard working.

## Configuration

`config.example.yaml` is fully commented. The important parts:

```yaml
brand:
  name: Tesla
  aliases: [Tesla Motors]
  domains: [tesla.com]

competitors:
  - name: Mercedes-Benz
    aliases: [Mercedes, Mercedes Benz]
    domains: [mercedes-benz.com]

prompts:
  - text: which electric car brands are the most reliable
    category: discovery
  - text: is a Tesla worth buying compared to other EVs
    category: branded

providers:
  - id: chatgpt
    type: openai
    model: gpt-5.5
  - id: claude
    type: anthropic
    model: claude-sonnet-5
  - id: grok
    type: openai_compatible
    base_url: https://api.x.ai/v1
    api_key_env: XAI_API_KEY
    model: grok-4

run:
  repeats: 1           # ask each prompt N times; LLM answers vary
  concurrency: 4

sentiment:
  enabled: true
  provider: chatgpt    # which provider judges sentiment
```

Every provider entry is one column in the report. `model` is passed straight through, so switching models is a one-line change. `aivis providers` lists the adapter types.

### Provider adapters

| type | Engine | Web search | How |
|---|---|---|---|
| `openai` | ChatGPT | yes | Responses API + `web_search` tool |
| `anthropic` | Claude | yes | Messages API + `web_search_20250305` server tool |
| `gemini` | Gemini | yes | Google Search grounding |
| `perplexity` | Perplexity | always | Agent API (`responses.create`); `api: chat` for legacy Sonar |
| `mistral` | Mistral / Le Chat | yes | Conversations API + `web_search` connector |
| `openai_compatible` | anything | engine-dependent | chat completions against `base_url` |
| `mock` | – | – | offline fake answers for testing |

Web search matters: without it the model answers from training data, which is not what users see in ChatGPT search, Perplexity or Google AI Mode. Set `web_search: false` on a provider if you deliberately want the "no browsing" baseline.

Default model names were checked against provider docs on 2026-09-24. If a provider renames a model, change it in `config.yaml`; `aivis check` will tell you immediately.

## Commands

| Command | Purpose |
|---|---|
| `aivis init` | create `config.yaml` and `.env` |
| `aivis check [-p id...]` | live-test each enabled provider |
| `aivis run [-p id...] [-n N] [-r N] [--no-sentiment] [--summary]` | run prompts; `-n` limits prompts for a smoke test |
| `aivis runs` | list stored runs |
| `aivis show [run_id]` | print the ranking table |
| `aivis export [run_id] -f csv\|json` | export one row per answer x brand |
| `aivis dashboard [--port 5000]` | web dashboard |
| `aivis providers` | list adapter types |

Add `-c path/to/config.yaml` before the command to use a different config (one per brand you track).

## Dashboard

- KPI tiles for your brand: rank, visibility, share of voice, position, sentiment, citation share
- Competitive ranking chart and a brand x engine heat map
- Prompt matrix: for every prompt and engine, whether you were mentioned and at what position; click a cell to read the full answer with brands highlighted and every source linked
- Sources table: which domains the engines rely on, tagged as yours or a competitor's
- Visibility over time across runs

## Adding a provider

Subclass `aivis.providers.base.Provider`, implement `_query(prompt) -> (text, citations, raw)` and `_complete(prompt) -> str`, and add one line to `REGISTRY` in `aivis/providers/__init__.py`. About 40 lines; see `openai_compatible.py` for the smallest example.

## Costs and rate limits

One run = prompts x providers x repeats calls, plus one judge call per answer that mentions a tracked brand when sentiment is on. Web search adds a per-search fee on most providers. `run.per_provider_concurrency` throttles parallel requests per engine; failures are retried with backoff and stored as errors rather than aborting the run.

## Development

```bash
pip install -e ".[all,dev]"
pytest
```

Tests cover mention detection, metrics, and a full run through the mock provider up to the dashboard API.

## Repository history

Version 1 (June 2025) was a single-engine prototype with committed result files. Version 2 is a rewrite. A Mistral API key was committed in v1 and remains in git history; it must be treated as compromised and revoked.
