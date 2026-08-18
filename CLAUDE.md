# Instructions for AI assistants working in this repo

Read ARCHITECTURE.md and CONVENTIONS.md before making any change. Follow them exactly.

## This is not a typical CRUD app
This product intercepts and can KILL a customer's live production AI agent workflow. A bug here doesn't just show a wrong number on a screen — it can wrongly terminate a customer's real business process, or fail to catch a real runaway (both are product-breaking failures). Treat every change to `sdk/`, `ingestion-api/`, and `policy-engine/` with the caution you'd use on payment processing code.

## Before writing code
- State which of the 4 services (sdk/, ingestion-api/, policy-engine/, dashboard/) you're changing and why.
- If the change touches the kill/throttle decision path, flag this explicitly and stop for human review before proceeding — do not merge or deploy autonomously.
- If a file would exceed 150-200 lines after your change, split it instead.

## Never do these things
- Never invent a new database table or column without it being explicitly requested — ask first.
- Never remove a `customer_id` filter from a query, even if it "looks redundant."
- Never add a new dependency without checking CONVENTIONS.md's allowlist rule.
- Never claim a fix works without the test evidence to show it.

## When in doubt
Stop and ask, rather than guessing on anything touching security, multi-tenancy, or the kill/throttle logic.