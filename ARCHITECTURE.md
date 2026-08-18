# Architecture

## System overview
Four independent services, each owning one responsibility. No service reaches into another's internals directly — they communicate only through the defined event schema and API contracts.

- `sdk/` — LangGraph instrumentation. Runs inside the CUSTOMER's application. Sends trace/cost events to `ingestion-api/`. Never stores data itself.
- `ingestion-api/` — Receives events, writes to ClickHouse (trace/cost data) and Supabase (config/policy lookups). Owns the canonical event schema.
- `policy-engine/` — Reads config from Supabase, reads recent event data from ClickHouse, decides kill/throttle/alert. Sends the decision back through `ingestion-api/` to the customer's SDK.
- `dashboard/` — Reads from Supabase (config) and ClickHouse (reporting queries) only. Never writes detection logic here.

## Data flow (one direction, always)
Customer's agent → sdk/ → ingestion-api/ → ClickHouse (events) + policy-engine/ (real-time decision) → back to sdk/ (kill/throttle signal) → dashboard/ (reporting, async, not on the critical path)

## Hard rule
Anything on the kill/throttle decision path (sdk/, ingestion-api/'s event handler, policy-engine/) must be reviewed by a human before merge — no AI-generated change to this path ships without a human reading the diff line by line. Dashboard/reporting code is lower-risk and can move faster.

## Multi-tenancy
Every table, every ClickHouse query, every API call MUST be scoped by `customer_id`. No exceptions. See CONVENTIONS.md Security section.