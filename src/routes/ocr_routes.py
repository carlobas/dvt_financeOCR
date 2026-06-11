from fastapi import APIRouter,FastAPI, File, Form, UploadFile
from typing import Annotated
import uvicorn
from pydantic import BaseModel
import asyncio
import mariadb
from ..services.ocr_engine import procesar_completo, construir_respuesta

app = APIRouter()

class ocr_details(BaseModel):
    idusuario: str
    paymentmethod: int
    ticket: UploadFile = File(...)

@app.post("/api/v1/finance/ocr/getInfoFromOCR")
async def get_info_from_ocr(idusuario: str = Form(...), paymentmethod: int = Form(...), ticket: UploadFile = File(...)):
    card_payment = 0 #Allowed by default for cash payments (7), to be checked for company cards (8 & 9)

    try:
        contents = await ticket.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return {"code":"5","message": "Error occurred while reading the uploaded file"}

    try:
        file_size = len(contents)
        print(f"Received file: {ticket.filename} with size: {file_size} bytes")
    except Exception as e:
        print(f"Error occurred while processing the uploaded file: {e}")
        return {"code":"5","message": "Error occurred while processing the uploaded file"}

    if paymentmethod in [7,8,9]:
        if paymentmethod != 7:
            card_payment = checkUserCard(idusuario, paymentmethod)
            if card_payment == 2:
                return {"code":"2","message": "User not allowed to use company card for this payment!"}
            if card_payment == 3:
                return {"code":"3","message": "User is allowed to use company card but card info is missing or not updated in the system"}
            if card_payment == 4:
                return {"code":"4","message": "Error occurred while checking user card information"}
    else:
        return {"code":"1","message": "Payment method not allowed or recognized"}
    
    if card_payment == 0:
        #El pago es con efectivo o con una tarjeta que el usuario tiene permitido usar, se procesa el ticket OCR
        #Hacemos la petición al OCR
        pass
    
    
#***************************************************************
#Return if user is allowed to use company card
#To be confirmed: 7 is cash, 8 & 9 company cards (VISA & SOLRED)
#***************************************************************
def checkUserCard(idusuario:str, paymentmethod:int):
    result = 2 #Allowed by default for cash payments (7), to be checked for company cards (8 & 9)
    has_card = False
    has_this_card = False
    card_type = ""
    if paymentmethod == 9:
        card_type = "SOLRED"
    DATABASE_URL = "mariadb://finuser:cD@xpov2yVxT@10.10.8.58/DC_FINANCIAL"


    try:
        conn = mariadb.connect(DATABASE_URL)
        cursor = conn.cursor()
        # Execute async query
        sql = "SELECT ID_TYPE FROM CARD_HOLDER WHERE COD_USUARIO = ?"
        cursor.execute(sql, (idusuario,))
        cursor = cursor.fetchall()
        #Controlamos que el usuario tenga tarjeta de empresa y que sea o no el caso concreto de SOLRED
        for row in cursor:
            has_card = True
            print(f"type: {row[0]}")
            if row[0] == card_type:
                has_this_card = True 
                break 
    except mariadb.Error as e:
        result = 4 
        print (f"Error connecting to MariaDB Platform: {e}")
    finally:
        conn.close()

    if not has_card:
        result = 2 #usuario NO tiene tarjeta de empresa 
    elif has_card and paymentmethod == 9 and not has_this_card:
        result = 3 #Usuario tiene tarjeta, pero no SOLRED y el cargo es con SOLRED
    else:
        result = 0 #Usuario tiene tarjeta y es compatible con el cargo

    return result