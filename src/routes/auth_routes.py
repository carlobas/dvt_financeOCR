from fastapi import APIRouter

app = APIRouter()

@app.get("/api/v1/auth")
async def auth():
    return {"code":"0","message": "Authentication endpoint not available for this app!"}