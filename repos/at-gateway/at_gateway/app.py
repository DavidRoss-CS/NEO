from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import uuid

app = FastAPI(title="at-gateway")

class MarketSignal(BaseModel):
    instrument: str
    price: float | str
    signal: str
    strength: float

@app.post("/webhook/tradingview")
async def webhook(body: MarketSignal):
    if not body.instrument:
        raise HTTPException(status_code=400, detail="invalid")
    return {"status":"accepted","trace_id":str(uuid.uuid4())}
