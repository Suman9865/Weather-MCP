from fastapi import FastAPI
from main import get_alerts, get_forecast

app = FastAPI()

@app.get("/alerts/{state}")
async def alerts(state: str):
    result = await get_alerts(state)
    return {"result": result}

@app.get("/forecast")
async def forecast(lat: float, lon: float):
    result = await get_forecast(lat, lon)
    return {"result": result}