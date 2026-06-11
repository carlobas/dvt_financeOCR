from fastapi import APIRouter
from pydantic import BaseModel

class payment_details(BaseModel):
    idusuario: str
    paymentmethod: str

app = APIRouter()

@app.get("/api/v1/finance/")
async def get_status():
    return {"code":"0","message": "API services UP and running!!!"}