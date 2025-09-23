# Agentic Trading Architecture - Seed Context

## Overview
This system is a **multi-repo, event-driven trading architecture** designed for futures, FX, and crypto execution.
It is meant to serve as a **scaffold/skeleton** that evolves into a full agentic trading system, with multiple AI agents contributing to analysis, execution, monitoring, and strategy iteration.

Key goals:
- Multi-agent orchestration (GPT, Claude, DeepSeek, etc.)
- Real-time ingestion of market data (TradingView webhooks, PineScript JSON, screenshots, other APIs)
- Trade execution and risk management across **prop firms**, **retail brokers**, and **exchanges**
- Observability: logs, metrics, runbooks, and deterministic replay

---

## Repo Layout
The system is organized into **multiple repos** under a single umbrella:

- **at-gateway/**
  Entry point for external data and execution requests.
  Responsibilities: ingest market events, validate input, publish NATS events.

- **at-core/**
  Core contracts, schemas, and shared services.
  Responsibilities: define event types, canonical data models, risk primitives, and system-wide constants.

- **at-agents/**
  Strategy and decision-making agents.
  Responsibilities: consume events, run analysis, generate signals, propose trades.

- **at-exec-sim/**
  Execution + simulation environment.
  Responsibilities: simulate trade fills, interact with broker/exchange adapters, measure slippage and latency.

- **at-obs/**
  Observability stack.
  Responsibilities: Prometheus metrics, Grafana dashboards, structured logging, audit trails, incident runbooks.

---

## Principles
1. **Contracts First**
   - All repos consume and produce NATS events defined in **at-core**.
   - No cross-repo imports.
   - Every repo has its own tests and docs.

2. **Tests First**
   - Each repo includes unit tests + integration test stubs.
   - Deterministic test fixtures for replaying market conditions.

3. **Observability Everywhere**
   - Structured logging via JSON.
   - Prometheus metrics in each service.
   - Runbooks accompany every new feature.

4. **Small Increments**
   - Work is chunked into PR-sized changes.
   - Every new feature updates:
     - README.md
     - API_SPEC / CONTRACTS.md
     - TEST_STRATEGY.md
     - RUNBOOK.md

---

## Tech Stack
- **FastAPI** for service APIs
- **Pydantic v2** for data validation
- **NATS** for async pub/sub events
- **Prometheus** for metrics
- **pytest** for testing
- **Docker (optional)** for local orchestration
- **MCP** for agent-service interoperability

---

## Conventions
- File naming: `ALL_CAPS.md` for docs, `snake_case.py` for Python code.
- No hard-coded configs: everything comes from `.env` or config files.
- Every repo has a **/docs** folder with contracts and runbooks.
- Logging is always structured JSON, never plain text.
- Every event type has:
  - Schema in **at-core**
  - Test fixture in repo
  - Logging + metrics when produced/consumed

---

## Example Flow
1. A TradingView webhook hits **at-gateway**.
2. Gateway validates, transforms, and publishes a `SignalEvent` to NATS.
3. One or more **agents** consume the event, analyze context, and emit a `TradeProposalEvent`.
4. **at-exec-sim** simulates execution or routes to broker adapters.
5. **at-obs** tracks latencies, error rates, trade outcomes, and logs everything.

---

## Roadmap Hints
- Start with skeleton repos + contracts in **at-core**.
- Add gateway service for ingest.
- Add 1–2 agents with placeholder logic.
- Add simulation/execution harness.
- Layer in observability + metrics.
- Expand with agent orchestration + memory.