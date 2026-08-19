from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

class TraceEvent(BaseModel):
    node_name: str
    step: int
    message: str

@app.post("/events")
async def receive_event(event: TraceEvent):
    print(f"[RECEIVED] {datetime.utcnow().isoformat()} | Node: {event.node_name} | Step: {event.step} | {event.message}")
    return {"status": "ok"}