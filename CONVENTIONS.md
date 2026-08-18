# Conventions

## File size
- Max 150-200 lines per file. If a file grows past this, split it — one file, one responsibility.
- No file should both fetch data AND contain business logic AND render UI. Split by concern.

## Component/module structure (enforce this exact order in every file)
1. Imports
2. Types/interfaces
3. Constants/config
4. Main logic (function or component)
5. Error handling (try/catch/finally — never omit, especially in policy-engine/ and ingestion-api/)
6. Exports

## Security & multi-tenancy (non-negotiable, especially given this product's kill-switch nature)
- Every Supabase query MUST filter by `customer_id`. Never `SELECT *` without an explicit tenant filter.
- Enable Row Level Security (RLS) on every Supabase table before it stores real data — no exceptions, no "we'll add it later."
- No API keys, database passwords, or tokens in frontend code, committed files, or logs. Use `.env` only (see `.env.example` from Step 3).
- No `localStorage` for anything sensitive (tokens, customer data).

## Dependencies — allowlist approach
- Allowed without asking: native `fetch`, standard library, whatever's already in `package.json`/`requirements.txt`.
- Requires a human decision before installing: any new package over ~50KB, anything that adds a new external service dependency, any HTTP client beyond native fetch (no axios), any utility library beyond what's already used (no lodash unless already present).
- Reason: every dependency is a thing that can break the kill-switch path or introduce a supply-chain risk in a product that touches customer production systems.

## Testing gate (pre-deploy, non-negotiable)
- `policy-engine/` and `ingestion-api/` require passing tests before merge — specifically test the kill/throttle decision logic with known-good and known-bad trace patterns.
- Run full test suite + build before any deploy to production. No exceptions for "small" changes to the decision path.

## AI-assisted development boundary
- AI (Claude, Copilot, etc.) may write: UI code in `dashboard/`, utility/helper functions, test files, documentation.
- AI may NOT independently decide: database schema changes, RLS policy changes, kill/throttle threshold logic, anything touching customer data isolation — these require explicit human design first, AI implements only after a human has specified exactly what to build.