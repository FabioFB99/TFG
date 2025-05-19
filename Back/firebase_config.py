import firebase_admin
from firebase_admin import credentials, firestore
import os

# Construye la ruta al archivo de credenciales relativo a este script
# __file__ es la ruta del archivo actual (firebase_config.py)
# os.path.dirname(__file__) es el directorio donde está firebase_config.py (es decir, TFG2/Back/)
# os.path.join(...) une las partes para formar la ruta completa a serviceAccountKey.json
SERVICE_ACCOUNT_KEY_PATH = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')

db = None # Variable global para el cliente de Firestore

def initialize_firebase():
    global db
    # Solo inicializa si no hay ya una app de Firebase inicializada
    if not firebase_admin._apps:
        try:
            # Verifica si el archivo de credenciales existe antes de intentar usarlo
            if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
                # Lanza un error claro si no se encuentra el archivo
                raise FileNotFoundError(
                    f"El archivo 'serviceAccountKey.json' no se encontró en la ruta esperada: {SERVICE_ACCOUNT_KEY_PATH}. "
                    "Asegúrate de que el archivo existe y está en la carpeta 'Back'."
                )

            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
            firebase_admin.initialize_app(cred)
            db = firestore.client() # Obtiene el cliente de Firestore
            print("INFO:     Firebase Admin SDK inicializado correctamente.")
        except FileNotFoundError as fnf_error:
            print(f"ERROR:    {fnf_error}")
            # Puedes decidir si la aplicación debe fallar aquí. Por ahora, solo imprimimos.
        except Exception as e:
            # Captura cualquier otra excepción durante la inicialización
            print(f"ERROR:    Error inicializando Firebase Admin SDK: {e}")
            # Considera registrar el error de forma más robusta (logging)
    else:
        # Si ya está inicializado, simplemente asignamos db si aún no lo está
        if db is None:
            db = firestore.client()
        print("INFO:     Firebase Admin SDK ya estaba inicializado.")

# Llama a la inicialización cuando este módulo (firebase_config.py) se importa por primera vez.
initialize_firebase()

# Función para obtener el cliente de la base de datos de forma segura.
def get_db():
    if db is None:
        # Esto podría pasar si la inicialización falló.
        # Intentar reinicializar podría ser una opción, o simplemente lanzar un error.
        print("ERROR:    El cliente de Firestore (db) es None. La inicialización de Firebase pudo haber fallado.")
        # Lanza una excepción para que las partes del código que dependen de db sepan que no está disponible.
        raise ConnectionError("La conexión con Firebase no está establecida. Revisa los logs de inicialización.")
    return db