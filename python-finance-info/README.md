# Python Finance Info

A Python command-line program that takes a stock symbol and prints the current date and time, the company's full name, the stock price, and the price change in value and percent. It keeps asking for symbols until you quit. Data comes from Yahoo Finance through the `[yfinance](https://pypi.org/project/yfinance/)` library.

**Author:** Dhruv Verma, San José State University
**Assignment:** Part 1: Python Finance Info (individual homework)

## Quick start

macOS / Linux:

```bash
./run.sh              # interactive: type symbols one after another, q to quit
./run.sh ADBE MSFT    # look up these symbols once and exit
./run.sh --test       # run the unit tests (no internet needed)
```

Windows:

```bat
run.bat
run.bat ADBE MSFT
run.bat --test
```

The run script checks for Python 3.9+, creates a virtual environment in `.venv` on the first run, installs `requirements.txt`, and starts the program. Later runs reuse the environment and only reinstall when `requirements.txt` changes.

Manual alternative:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```



## Example

```
Python Finance Info - type a stock symbol (e.g. ADBE), or q to quit.

Please enter a symbol:
ADBE
Mon Oct 10 17:23:48 PDT 2016
Adobe Systems Incorporated (ADBE)
109.24 +0.60 (+0.55%)

Please enter a symbol:
<User can enter another symbol>
```



## How each requirement is met


| Requirement                              | Where it is handled                                                                                              |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Python API for financial data            | `yfinance` (Yahoo Finance), wrapped by `YahooFinanceProvider` in `finance_info/providers.py`                     |
| Take a stock symbol as input, repeatedly | `finance_info/cli.py`: interactive loop; also accepts symbols as arguments                                       |
| Current date and time                    | `format_timestamp()` in `finance_info/formatter.py`, same layout as Unix `date` (`Mon Oct 10 17:23:48 PDT 2016`) |
| Full name of the company                 | `longName`, then `shortName` from Yahoo                                                                          |
| Stock price                              | `regularMarketPrice` (falls back to `currentPrice`, then `fast_info`)                                            |
| Value change with `+`/`-`                | price minus previous close, always signed, e.g. `+0.60` / `-0.51`                                                |
| Percentage change with `+`/`-`           | change divided by previous close, e.g. `(+0.55%)`                                                                |
| Handle any error situation               | see the table below                                                                                              |




### Error handling

Every failure is turned into a short message, and the program keeps prompting for the next symbol.


| Situation                                     | What happens                                                                                                                                |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| No network, DNS failure, timeout, proxy block | Retried twice with backoff (1 s, 2 s), then: `Error: Could not reach the stock data service. Check your internet connection and try again.` |
| Yahoo rate limit (HTTP 429)                   | Retried with backoff, then a "wait a minute and try again" message                                                                          |
| Unknown symbol (e.g. `ZZZZZZ`)                | `Error: 'ZZZZZZ' is not a valid stock symbol.` (fails immediately, with no retry)                                                           |
| Malformed input (e.g. `hello world`, `$$$`)   | Rejected locally before any network call                                                                                                    |
| Empty input                                   | `Error: No symbol entered.`                                                                                                                 |
| Symbol exists but has no live price           | `Error: No current price data is available...` (reported as an error so an old closing price cannot pass as today's price)                  |
| `yfinance` not installed                      | Tells you to run `./run.sh` or `pip install -r requirements.txt`                                                                            |
| Ctrl+C, Ctrl+D, `q`, `quit`, `exit`           | Exits cleanly                                                                                                                               |
| Anything unexpected                           | Reported as an error, no stack trace, and the loop continues                                                                                |


In one-shot mode (`./run.sh ADBE MSFT`) the exit code is `0` if every lookup worked and `1` if any failed, so the program can be used from other scripts.

## Project layout

```
python-finance-info/
├── main.py                    entry point
├── finance_info/
│   ├── models.py              Quote dataclass (price, previous close, change, % change)
│   ├── errors.py              the program's own error types
│   ├── providers.py           QuoteProvider interface + Yahoo Finance adapter, retries, error translation
│   ├── formatter.py           builds the three output lines
│   └── cli.py                 interactive loop and command-line arguments
├── tests/test_finance_info.py 21 unit tests using fakes (no internet needed)
├── run.sh / run.bat           run scripts
├── requirements.txt
└── docs/
    ├── agent_design.tex       write-up source (LaTeX)
    └── agent_design.pdf       write-up (PDF)
```

The design keeps each concern in its own module. The user interface only receives a `Quote` or one of the error types in `errors.py`, so `yfinance`, curl and HTTP details stay inside the provider. Swapping Yahoo for another data source means writing one new class with a `get_quote(symbol)` method.

## Tests

```bash
./run.sh --test
# or
python -m unittest discover -s tests -v
```

The tests cover the output format against the assignment example, sign handling (a zero change prints as `+0.00`), symbol validation, invalid symbols, network failures with retry and backoff, recovery after a transient failure, rate limits, missing price data, and an interactive session that keeps going after several kinds of errors.

## Write-up: designing this as an AI agent

*Also available as a PDF:* `[docs/agent_design.pdf](docs/agent_design.pdf)` *(LaTeX source:* `[docs/agent_design.tex](docs/agent_design.tex)`*).
Chapter references are to Pressman & Maxim, Software Engineering: A Practitioner's Approach, 9th edition, Chapters 1 to 15.*

**The agent.** A user asks in plain language, for example "How did Adobe and Microsoft do today?" A language model works out what is being asked, resolves company names to ticker symbols, calls a `get_quote` tool for each one, and writes the answer. The `get_quote` tool is the deterministic provider layer from this program. The model chooses which data to fetch, and every price in the answer comes from that tool.

1. **Process: Agile increments with prototype checkpoints (Ch. 3 §3.4 Scrum; Ch. 4).**
  Each sprint delivers a working prototype. Sprint 1 is the CLI in this repo. Sprint 2 adds the tool-calling agent on top of it. Sprint 3 adds a second data provider and compliance controls. Sprint 4 adds the REST and MCP interfaces. Every sprint ends with prototype evaluation and a go/no-go decision (§4.5 and §4.6) and a retrospective (§3.4.5). AI tools draft user stories and acceptance criteria from the brief, and the team reviews and edits them in sprint planning.
2. **Requirements: user stories, scenarios and negotiated non-functional requirements (Ch. 7 §7.3 to §7.8; Ch. 8 §8.2).**
  For example: "As an investor, I want to ask for a quote by company name so I don't need to know the ticker." Acceptance criteria are written as Given/When/Then and become test cases. Scenarios cover the unhappy paths: offline, unknown symbol, and ambiguous names (for "Apple", the agent asks the user to pick the company). Non-functional requirements are negotiated with stakeholders (§7.6): answer in under 3 s for most requests, show a timestamp with every cached price, and give no buy/sell advice. Requirements monitoring (§7.7) keeps checking these in production.
3. **Architecture: layers with a deterministic core (Ch. 10 §10.3, §10.5, §10.7).**
  There are five layers: interfaces (CLI, chat, REST, MCP), agent orchestration (LLM planner, prompts, guardrails), tools (`get_quote`, `resolve_ticker`, `compare`), provider adapters, and a cache. Arithmetic and formatting stay in ordinary code because the model can get numbers wrong. Each architectural decision is recorded (§10.5). The alternative "one big prompt that does everything" is compared with tool-calling using ATAM-style trade-off analysis (§10.7). Tool-calling wins on reliability and testability.
4. **Component design: modular, loosely coupled components (Ch. 9 §9.3.4 to §9.3.7; Ch. 11 §11.2).**
  The agent depends only on a `QuoteProvider` interface (Dependency Inversion). A new data vendor is a new class, with no edits to the agent (Open-Closed). Each module has one job (high cohesion). Modules communicate only through the `Quote` object and named error types (low coupling). API keys and HTTP details stay inside the adapters (information hiding). This repo already follows that structure.
5. **Patterns: use proven ones and avoid known anti-patterns (Ch. 14 §14.1 to §14.5).**
  Adapter wraps each data vendor. Strategy lets the system switch providers on failure. Facade gives the agent a single quote service to call. Cache-aside handles repeated lookups. Retry with exponential backoff (already in this repo) and a circuit breaker (a common industry pattern) handle failing providers. The design avoids the Blob anti-pattern (§14.5), here a single "god prompt" that parses, calculates and formats in one place.
6. **Resilience: reliability as a quality factor (Ch. 15 §15.2.1, ISO 25010: fault tolerance, recoverability, availability).**
  Every external call has a timeout. Only transient errors such as timeouts are retried, and a bad symbol fails immediately. A circuit breaker stops calls to a failing provider and switches to the backup. If every provider is down, the agent can return the last cached price, clearly labelled "as of 10:31 ET". If the LLM service is down, the agent can fall back to the plain CLI path. A guardrail checks that every number in the model's reply matches a tool result, which stops invented figures. Workers are stateless so they can scale horizontally.
7. **Compliance and security: quality includes legal risk (Ch. 15 §15.3.4 negligence and liability, §15.3.5 quality and security).**
  The agent gives information only, with no buy/sell recommendations, and every answer shows the data source, any delay and a short disclaimer. Yahoo data via `yfinance` is meant for personal and educational use. A production system needs a licensed market-data feed and the exchanges' display agreements. If a regulated firm ran the agent, its replies would be communications with the public (for example FINRA Rule 2210) and would need to be retained under the firm's record-keeping obligations. API keys go in a secrets manager with least-privilege access. Every prompt, tool call and response is written to an audit log. Text returned by tools is handled strictly as data, which guards against prompt injection. No personal account data is collected.
8. **Interoperability: easy for other systems to use (ISO 25010 compatibility, §15.2.1; Ch. 10 §10.4).**
  Tools are described with JSON Schema so any function-calling model can use them. They are also exposed through an MCP server, so other AI assistants can call them, and through a versioned REST API with an OpenAPI spec. Data uses standard formats: ISO 8601 timestamps with time zone, ISO 4217 currency codes, prices as decimal strings, and exchange-suffixed symbols such as `RELIANCE.NS`. Quote events can optionally be published to a message bus for downstream systems.
9. **Quality assurance with AI tools in the loop (Ch. 15 §15.4; Ch. 6 §6.1).**
  Unit tests run against fake providers (this repo has 21). Contract tests run against recorded provider responses. An agent evaluation set of golden questions measures ticker-resolution accuracy, refusal of advice requests, and whether the numbers are correct. All of these gate every merge in CI. AI coding tools (e.g. Claude, Copilot) write code and tests, but each change is reviewed by a person and must pass the suite, the same as a teammate's pull request. Tracing and metrics (OpenTelemetry: latency, error rate, provider failovers) feed requirements monitoring and future sprint planning.


## Data notice

Quotes come from Yahoo Finance via `yfinance`, an independent open-source project. The data may be delayed and is for educational use only, with no investment advice given.