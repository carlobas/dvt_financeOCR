from fastapi import FastAPI
from src.routes.auth_routes import app as auth_routes
from src.routes.payment_routes import app as payment_routes
from src.routes.ocr_routes import app as ocr_routes
from dotenv import load_dotenv
import os
import uvicorn

load_dotenv("./dcfinanceocr.env")

#Define los modelos de datos para las solicitudes y respuestas de la API. En este caso para el endpoint de pago

app = FastAPI()
app.include_router(auth_routes)
app.include_router(ocr_routes, tags=["ocr"])
app.include_router(payment_routes, tags=["default"])

if __name__ == "__main__":
    #uvicorn.run(app, host=os.getenv("SERVER"), port=os.getenv("SERVER_PORT"))
    pass