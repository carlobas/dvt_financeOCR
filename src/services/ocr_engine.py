import sys
import re
import json
import logging
import asyncio
import cv2
import numpy as np
import fitz
import httpx
from pathlib import Path
from paddleocr import PaddleOCR
from os import getenv
from dotenv import load_dotenv

load_dotenv("../dcfinanceocr.env")

logging.disable(logging.WARNING)
OCR = PaddleOCR(use_angle_cls=True, lang="es", show_log=False)

LLM_HOST    = getenv("LLM_HOST")
LLM_ALIAS   = getenv("LLM_ALIAS")
LLM_TIMEOUT = float(getenv("LLM_TIMEOUT")) if getenv("LLM_TIMEOUT") else 60.0

FORMATOS_SOPORTADOS = {".jpg", ".jpeg", ".png", ".pdf"}

# Keywords por concepto para el regex
CONCEPTOS_KEYWORDS = {
    "Taxi":               ["taxi", "licencia", "taxímetro", "vtc"],
    "Gasolina":           ["gasolina", "diesel", "combustible", "gasolinera", "repsol", "cepsa", "bp", "shell"],
    "Peaje":              ["peaje", "autopista", "autovía"],
    "Parking":            ["parking", "aparcamiento", "garaje"],
    "Transporte público": ["metro", "autobús", "autobus", "renfe", "cercanías", "tren", "emt", "tmb"],
    "Alojamiento":        ["hotel", "hostal", "alojamiento", "habitación"],
    "Restaurante":        ["restaurante", "bar", "cafetería", "café", "menú"],
    "Material de oficina":["papelería", "oficina", "impresión"],
}


# ──────────────────────────────────────────────────────────────
# OCR
# ──────────────────────────────────────────────────────────────

def preprocesar(img: np.ndarray) -> np.ndarray:
    gris    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gris    = cv2.bilateralFilter(gris, 11, 17, 17)
    binaria = cv2.adaptiveThreshold(
        gris, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10
    )
    return binaria


def ocr_sobre_imagen(img: np.ndarray) -> list[dict]:
    img_proc  = preprocesar(img)
    resultado = OCR.ocr(img_proc, cls=True)
    bloques   = []
    if resultado and resultado[0]:
        for bloque in resultado[0]:
            texto, confianza = bloque[1]
            if confianza > 0.45:
                bloques.append({
                    "texto":     texto.strip(),
                    "confianza": round(float(confianza), 3)
                })
    return bloques


def _ocr_imagen_bytes(contenido: bytes) -> dict:
    arr = np.frombuffer(contenido, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen.")
    bloques = ocr_sobre_imagen(img)
    lineas  = [b["texto"] for b in bloques]
    return {
        "tipo":           "imagen",
        "total_lineas":   len(lineas),
        "bloques":        bloques,
        "texto_completo": "\n".join(lineas)
    }


def _ocr_pdf_bytes(contenido: bytes) -> dict:
    doc     = fitz.open(stream=contenido, filetype="pdf")
    paginas = []
    for i, page in enumerate(doc):
        mat       = fitz.Matrix(2, 2)
        pix       = page.get_pixmap(matrix=mat)
        img_bytes = np.frombuffer(pix.samples, dtype=np.uint8)
        img       = img_bytes.reshape(pix.height, pix.width, pix.n)
        if pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        elif pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        bloques = ocr_sobre_imagen(img)
        lineas  = [b["texto"] for b in bloques]
        paginas.append({
            "pagina":       i + 1,
            "total_lineas": len(lineas),
            "bloques":      bloques,
            "texto":        "\n".join(lineas)
        })
    doc.close()
    return {
        "tipo":           "pdf",
        "total_paginas":  len(paginas),
        "paginas":        paginas,
        "texto_completo": "\n\n".join(p["texto"] for p in paginas)
    }


def procesar_bytes(contenido: bytes, filename: str) -> dict:
    ext = "." + filename.split(".")[-1].lower()
    if ext not in FORMATOS_SOPORTADOS:
        raise ValueError(f"Formato '{ext}' no soportado.")
    return _ocr_pdf_bytes(contenido) if ext == ".pdf" else _ocr_imagen_bytes(contenido)


# ──────────────────────────────────────────────────────────────
# Extracción de campos — capa 1: Regex
# ──────────────────────────────────────────────────────────────

def limpiar_texto(texto: str) -> str:
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = re.sub(r"[^\w\s.,;:\-€$%/ÁÉÍÓÚáéíóúñÑüÜ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _regex_importe(texto: str) -> float | None:
    # Primero: cerca de palabra clave (más fiable)
    m = re.search(
        r'(?i)(?:total|importe|neto|cobrado|a\s*pagar|precio)[:\s]*[€$]?\s*([\d]+[.,][\d]{2})',
        texto
    )
    if m:
        return float(m.group(1).replace(",", "."))

    # Fallback: mayor importe numérico del texto (heurística)
    todos = re.findall(r'\b([\d]{1,4}[.,][\d]{2})\b', texto)
    if todos:
        return max(float(v.replace(",", ".")) for v in todos)

    return None


def _regex_fecha(texto: str) -> str | None:
    m = re.search(r'\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b', texto)
    return m.group(1) if m else None


def _regex_concepto(texto: str) -> str | None:
    texto_lower = texto.lower()
    for concepto, keywords in CONCEPTOS_KEYWORDS.items():
        if any(kw in texto_lower for kw in keywords):
            return concepto
    return None


def extraer_con_regex(texto_completo: str) -> dict:
    texto_limpio = limpiar_texto(texto_completo)
    importe      = _regex_importe(texto_limpio)
    fecha        = _regex_fecha(texto_limpio)
    concepto     = _regex_concepto(texto_limpio)

    return {
        "texto_limpio":       texto_limpio,
        "importe":            importe,
        "importe_confianza":  0.90 if importe  is not None else 0.0,
        "fecha":              fecha,
        "fecha_confianza":    0.90 if fecha     is not None else 0.0,
        "concepto":           concepto,
        "concepto_confianza": 0.90 if concepto  is not None else 0.0,
    }


# ──────────────────────────────────────────────────────────────
# Extracción de campos — capa 2: LLM (fallback auxiliar)
# ──────────────────────────────────────────────────────────────

_PROMPT_SISTEMA = """
Eres un asistente que analiza textos de tickets y facturas españolas con posibles errores de OCR.
Responde ÚNICAMENTE en este formato exacto, sin añadir nada más:

IMPORTE: <número decimal con punto, ej: 12.95>
FECHA: <fecha tal como aparece en el ticket>
CONCEPTO: <concepto del gasto>

Si no puedes identificar un valor con seguridad, escribe: NO IDENTIFICADO
""".strip()


def _parsear_llm(texto_llm: str) -> dict:
    def extraer(patron):
        m = re.search(patron, texto_llm, re.IGNORECASE)
        if not m:
            return None
        v = m.group(1).strip()
        return None if "NO IDENTIFICADO" in v.upper() else v

    importe_raw = extraer(r'IMPORTE:\s*([^\n]+)')
    fecha       = extraer(r'FECHA:\s*([^\n]+)')
    concepto    = extraer(r'CONCEPTO:\s*([^\n]+)')

    importe = None
    if importe_raw:
        try:
            importe = float(importe_raw.replace(",", ".").replace("€", "").strip())
        except ValueError:
            pass

    return {"importe": importe, "fecha": fecha, "concepto": concepto}


async def _llamar_llm(texto_limpio: str, campos_faltantes: list[str]) -> dict:
    lista_conceptos = "\n".join(f"- {c}" for c in CONCEPTOS_KEYWORDS) + "\n- Otro"

    prompt = (
        f"Texto del ticket:\n{texto_limpio}\n\n"
        f"Identifica: {', '.join(campos_faltantes)}\n\n"
        f"Conceptos posibles para CONCEPTO:\n{lista_conceptos}"
    )

    payload = {
        "model":       LLM_ALIAS,
        "messages":    [
            {"role": "system", "content": _PROMPT_SISTEMA},
            {"role": "user",   "content": prompt}
        ],
        "max_tokens":  128,
        "temperature": 0.1,
        "stream":      False
    }

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            r = await client.post(f"{LLM_HOST}/v1/chat/completions", json=payload)
            r.raise_for_status()
        texto_llm = r.json()["choices"][0]["message"]["content"]
        logging.info(f"LLM response: {texto_llm}")
        return _parsear_llm(texto_llm)
    except Exception as e:
        logging.error(f"Error LLM: {e}")
        return {}


# ──────────────────────────────────────────────────────────────
# Orquestador: regex → LLM si hace falta
# ──────────────────────────────────────────────────────────────

async def extraer_campos(texto_completo: str) -> dict:
    campos = extraer_con_regex(texto_completo)

    faltantes = [
        campo.upper()
        for campo in ["importe", "fecha", "concepto"]
        if campos[campo] is None
    ]

    if faltantes:
        logging.info(f"Regex no identificó: {faltantes} → activando LLM")
        llm = await _llamar_llm(campos["texto_limpio"], faltantes)

        for campo in ["importe", "fecha", "concepto"]:
            if campos[campo] is None and llm.get(campo) is not None:
                campos[campo]                    = llm[campo]
                campos[f"{campo}_confianza"] = 0.70  # LLM < regex

    return campos


# ──────────────────────────────────────────────────────────────
# Entry point para la API (async) — usado por ocr_routes.py
# ──────────────────────────────────────────────────────────────

async def procesar_completo(contenido: bytes, filename: str) -> dict:
    ocr            = procesar_bytes(contenido, filename)
    ocr["campos"]  = await extraer_campos(ocr.get("texto_completo", ""))
    return ocr


# ──────────────────────────────────────────────────────────────
# Constructor de respuesta final — usado por ocr_routes.py
# ──────────────────────────────────────────────────────────────

def construir_respuesta(codigo: str, mensaje: str, ocr: dict | None = None) -> dict:
    respuesta = {"codigo": codigo, "mensaje": mensaje, "importe": None, "tickets": []}

    if ocr and "campos" in ocr:
        c = ocr["campos"]
        respuesta["importe"] = c.get("importe")
        respuesta["tickets"] = [{
            "importe":  c.get("importe"),
            "concepto": c.get("concepto"),
            "fecha":    c.get("fecha")
        }]

    return respuesta


# ──────────────────────────────────────────────────────────────
# CLI para pruebas manuales
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:  python3 ocr_engine.py <archivo>")
        print("Formatos: .jpg  .jpeg  .png  .pdf")
        sys.exit(1)

    async def _main():
        ruta = Path("images") / sys.argv[1]
        with open(ruta, "rb") as f:
            contenido = f.read()
        resultado = await procesar_completo(contenido, ruta.name)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))

    try:
        asyncio.run(_main())
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)S