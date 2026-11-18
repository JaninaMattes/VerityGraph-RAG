# CLAUDE.md

How I want you to work in this repository.

## The project

An inbound carrier sales agent for a freight brokerage, built on the HappyRobot platform. A
carrier calls (web call), the agent checks the MC number with FMCSA, confirms the carrier with a
one-time code, searches the legacy TMS for a load, negotiates within the rate ceiling and hands
the deal to a senior rep (mocked). Every step is logged to Twin and shown in an ops App.

| Path | What |
| --- | --- |
| `app/`, `fake_tms/`, `tests/` | Integration service (Python, FastAPI). Deploys to Render from `main` |
| `happyrobot/workflows/` | Source of truth for the platform nodes: prompts, tool contracts, Python node code, tests |
| `happyrobot/twin/migrations/` | Twin tables and views (`001`–`006`), safe to run again |
| `frontend/` | Ops App (Next.js). Deploy with `make app-deploy` (mirrors into the HappyRobot App repository) |
| `docs/` | Requirements, ADRs, QA, deliverables, platform notes |

The brief is `docs/use_case/FDE_Technical_Challenge_Inbound_Carrier_Sales.pdf`. Decisions are in
`docs/architecture/FDE_Technical_Challenge_Architecture_Decisions.md` (ADRs). When the brief and
a document disagree, the brief wins; tell me.

## Rules

- **Never commit, push, rewrite history or deploy** unless I ask for that exact step. Leave
  changes in the working tree; I review and commit them myself.
- **Ask before** anything that is hard to undo or that other people see: publishing a workflow
  version, writing or deleting Twin rows or tables, alert rules, emails, deleting files.
- **Secrets stay local.** Never write keys, tokens, phone numbers, email addresses or codes into
  the repository, a log line or a test. `.env`, `frontend/.env.local` and `.private-notes` are
  local only.
- **Never reveal the rate ceiling.** `max_rate` stays in the service; no response, log line,
  prompt, document or App screen may show it or let it be worked out.
- **Check the requirement first.** Before you change behaviour, quote the line of the brief or
  the ADR it serves. Do not add scope the brief does not ask for without asking me.
- **Verify, then report.** Run the checks below before you say something works. Report failures
  with their output. If you could not check something, say so.

## Code

- Keep it simple: KISS, DRY and SOLID. Prefer the smallest change that solves the problem. No
  new dependency, layer or abstraction without a reason I can read in one sentence.
- Business rules that must be exact (eligibility, verification, ceiling, negotiation, booking)
  live in deterministic code in the service. The voice agent asks; the service decides.
- Match the existing style: type hints, `ruff` and `mypy` clean (line length 100), small pure
  functions in `app/domain`, adapters in `app/infrastructure`.
- TMS field widths match the live wire. FMCSA is geoblocked, so it is mocked locally
  (`FMCSA_MOCK=true`); production refuses the mock and the console code channel.
- A node's code on the platform comes from `happyrobot/workflows/`. Change the file first, test
  it, then copy it to the node.

## Docstrings and comments

- A docstring says what the function or module does, its inputs, its result and any behaviour a
  caller must know (errors, limits, side effects). A reader must understand it without reading
  the implementation.
- Keep them short and complete. Explain *why* in one sentence when the reason is not obvious.
- No change history in code: no dates, run IDs, version numbers or "live call" stories. That
  belongs in the ADRs, the QA document or the commit message.
- Docstrings and comments are written as project documentation. They never mention who or what
  wrote them.

## Tests

- Every behaviour change gets a test. Test classes with GIVEN/WHEN/THEN docstrings, in
  `tests/unit`, `tests/integration`, `tests/scenarios` or `tests/live`.
- App tests use `node:test` with the same GIVEN/WHEN/THEN names, next to the module
  (`frontend/src/lib/carrier-sales/*.test.ts`).
- Checks:

  | Part | Command |
  | --- | --- |
  | Service (lint, types, tests) | `make check` |
  | Twin views on PostgreSQL (Docker) | `make test-sql` |
  | Live TMS and FMCSA, read-only | `make test-live` |
  | Ops App (lint, tests, build, types) | `make app-check` |


## Writing

- Replies and procedures in ASD-STE100 (Simplified Technical English): short sentences, active
  voice, one instruction per step, one term for one meaning.
- Documents for the customer use the customer's words, not code terms.
- Lead with the answer. Give a recommendation, not a list of every option.