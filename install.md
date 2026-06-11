[DESARROLLO]
crear y activar entorno 
python3 -m venv env_dcfinancialocr 
python -m pip install fastapi 
python -m pip install uvicorn 
pip install --pre mariadb[binary,pool]

FastAPI Files https://fastapi.tiangolo.com/tutorial/request-files/ 
pip install python-multipart

[INSTALACION]
# Ubuntu 26
# Instala python y venv
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev -y
sudo apt update && sudo apt install python3-pip python3-venv
sudo apt install pipx
sudo apt install pipenv
# Crea y activa el entorno virtual
# DVT Digital Champions Financial OCR dvt_dcfinancialocr
sudo mkdir /dvt_apps
sudo mkdir /dvt_apps/environments
sudo mkdir /dvt_apps/fastapi
sudo mkdir /dvt_apps/fastapi/dvt_dcfinancialocr
# ===================================================
# Copiar app en /dvt_apps/fastapi/dvt_dcfinancialocr
# ===================================================
cd /dvt_apps/environments
sudo python3 -m venv dvt_dcfinancialocr
source dvt_dcfinancialocr

# Instalar UVICORN, FastAPI y dependencias como mariadb y python-multipart para los ficheros
# Posicionado en /dvt_apps/environments
cd /dvt_apps/environments
sudo ./dvt_dcfinancialocr/bin/pip install fastapi uvicorn
sudo ./dvt_dcfinancialocr/bin/pip install --pre mariadb[binary,pool]
sudo ./dvt_dcfinancialocr/bin/pip install python-multipart
## Dependencias del OCR
sudo ./dvt_dcfinancialocr/bin/pip install paddleocr==2.7.3
sudo ./dvt_dcfinancialocr/bin/pip install paddlepaddle==2.6.2
sudo ./dvt_dcfinancialocr/bin/pip install "numpy<2.0"
sudo ./dvt_dcfinancialocr/bin/pip install pillow
sudo ./dvt_dcfinancialocr/bin/pip install pymupdf
## Dependencias del LLama server
sudo ./dvt_dcfinancialocr/bin/pip install httpx
sudo ./dvt_dcfinancialocr/bin/pip install python-dotenv

# ===================================================
# Probar app
# ===================================================
cd /dvt_apps/fastapi/dvt_dcfinancialocr
uvicorn main:app --host=0.0.0.0 --port=8080 --reload
wget http://127.0.0.1:8080/api/v1/finance
# ===================================================
{
    "code": "0",
    "message": "API services UP and running!!!"
}
# ===================================================

# ===================================================
# Crear un servicio para la aplicación
# ===================================================
sudo nano /etc/systemd/system/fastapi-dcfinancialocr.service

[Unit]
Description=ES DVT Digital Champions Financial API
After=network.target

[Service]
User=root
WorkingDirectory=/dvt_apps/fastapi/dvt_dcfinancialocr
ExecStart=/dvt_apps/environments/dvt_dcfinancialocr/bin/uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target

# ===================================================================
# Arrancar el servicio y lo habilita para el arranque de la máquina
# ===================================================================
sudo systemctl start fastapi-dcfinancialocr.service
sudo systemctl start fastapi-dcfinancialocr.service
