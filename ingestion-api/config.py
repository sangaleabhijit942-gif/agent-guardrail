# Pricing and default threshold constants shared across the ingestion API.
# NOTE: these rates are hardcoded per-million-token prices, not sourced from a
# model price table — cost (and therefore the kill point) assumes these rates.

INPUT_COST_PER_TOKEN = 1 / 1_000_000
OUTPUT_COST_PER_TOKEN = 5 / 1_000_000
KILL_THRESHOLD = 0.01
