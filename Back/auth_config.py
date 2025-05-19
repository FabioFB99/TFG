# Back/auth_config.py
import os
from dotenv import load_dotenv
from pathlib import Path # <--- AÑADIDO

load_dotenv() # Carga variables de .env si existe

# ¡CAMBIA ESTA CLAVE SECRETA EN UN PROYECTO REAL!
# Puedes generarla con: openssl rand -hex 32
SECRET_KEY = os.getenv("SECRET_KEY", "contrasenia_muy_segura_cambiar_en_produccion") # Cambiado el valor por defecto
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)) # Convertir a int

# --- Definición de UPLOAD_DIR ---
# Asumimos que auth_config.py está en la raíz de la carpeta 'Back'
# y static_uploads también estará dentro de 'Back'
CURRENT_FILE_DIR = Path(__file__).resolve().parent # Directorio donde está auth_config.py (Back/)
UPLOAD_DIR = CURRENT_FILE_DIR / "static_uploads"

# Asegurarse de que el directorio exista al cargar la configuración
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"INFO (auth_config): Directorio de subida UPLOAD_DIR asegurado en: {UPLOAD_DIR}")
except OSError as e:
    print(f"ERROR (auth_config): No se pudo crear el directorio de subida en {UPLOAD_DIR}. Error: {e}")
    # Considera lanzar una excepción aquí o manejar el error de forma más robusta
    # si la creación del directorio es crítica para el inicio de la aplicación.
# --- Fin de Definición de UPLOAD_DIR ---