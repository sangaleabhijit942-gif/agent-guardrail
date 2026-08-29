from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from auth import router as auth_router
from thresholds import router as thresholds_router
from events import router as events_router
from reporting import router as reporting_router
from diagnostics import router as diagnostics_router

# Re-exported for callers that import these from `main` (e.g. test_main.py).
from config import INPUT_COST_PER_TOKEN, OUTPUT_COST_PER_TOKEN, KILL_THRESHOLD  # noqa: F401

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(auth_router)
app.include_router(thresholds_router)
app.include_router(events_router)
app.include_router(reporting_router)
app.include_router(diagnostics_router)
