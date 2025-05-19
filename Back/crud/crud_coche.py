# TFG2/Back/crud/crud_coche.py
from typing import List, Optional, Dict, Any
from firebase_admin import firestore 
import os
from pathlib import Path

# Importaciones de tus módulos locales
from firebase_config import get_db
from models.models_coche import CocheCreate, CocheInDB, CocheUpdate # Asegúrate que todos los modelos necesarios estén aquí
from models.models_user import UserInDBBase 

# Importar UPLOAD_DIR desde tu archivo de configuración central
# Cambia 'auth_config' por el nombre de tu archivo de configuración si es diferente (ej. 'config')
try:
    from auth_config import UPLOAD_DIR
except ImportError:
    # Fallback o manejo de error si UPLOAD_DIR no se encuentra en auth_config
    # Esto es solo un ejemplo, idealmente deberías asegurar que la importación funcione
    print("ADVERTENCIA: No se pudo importar UPLOAD_DIR desde auth_config. La eliminación de archivos podría fallar.")
    # Podrías definir un UPLOAD_DIR por defecto aquí para desarrollo, pero no es ideal para producción.
    # Por ejemplo, asumiendo una estructura estándar:
    CURRENT_FILE_DIR = Path(__file__).resolve().parent # Directorio actual (crud)
    BACK_DIR = CURRENT_FILE_DIR.parent # Directorio Back
    UPLOAD_DIR = BACK_DIR / "static_uploads" # Ruta a static_uploads
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Usando UPLOAD_DIR por defecto (fallback): {UPLOAD_DIR}")


COCHES_COLLECTION = "coches"
USUARIOS_COLLECTION = "usuarios"

def create_coche_in_db(coche_data: CocheCreate, current_user: UserInDBBase) -> Optional[CocheInDB]:
    db = get_db()
    try:
        # Para Pydantic v2+ usa model_dump(), para v1 usa dict()
        try:
            coche_doc_data = coche_data.model_dump(exclude_unset=True) # exclude_unset para no enviar campos opcionales no provistos
        except AttributeError:
            coche_doc_data = coche_data.dict(exclude_none=True) # exclude_none para no enviar campos opcionales no provistos que son None
            
        coche_doc_data["user_id"] = current_user.id 
        coche_doc_data["creado_en"] = firestore.SERVER_TIMESTAMP # Añadir timestamp de creación
        coche_doc_data["actualizado_en"] = firestore.SERVER_TIMESTAMP # Añadir timestamp de actualización inicial

        doc_ref = db.collection(COCHES_COLLECTION).document() 
        doc_ref.set(coche_doc_data)
        coche_id = doc_ref.id

        user_doc_ref = db.collection(USUARIOS_COLLECTION).document(current_user.id)
        user_doc_ref.update({"coches_ids": firestore.ArrayUnion([coche_id])})

        print(f"INFO CRUD Coche: Coche '{coche_data.marca} {coche_data.modelo}' (ID: {coche_id}) creado por usuario '{current_user.alias}' (ID: {current_user.id}).")
        
        # Para devolver el objeto CocheInDB, necesitamos todos los campos, incluyendo los timestamps resueltos
        # Firestore los devuelve como datetime.datetime tras un get(), pero al crear, no los tenemos inmediatamente.
        # Podríamos hacer un doc_ref.get() aquí, o simplemente construir con los datos que tenemos y el ID.
        # Si CocheInDB espera los timestamps, la forma más segura es hacer un get().
        # Por simplicidad, y si CocheInDB puede manejar timestamps como None o no los tiene,
        # esto funciona. Si no, considera un get().
        return CocheInDB(id=coche_id, **coche_doc_data)
    except ConnectionError as ce:
        print(f"ERROR CRUD Coche: Error de conexión con Firebase al crear coche: {ce}")
        raise # Re-lanzar para que el endpoint lo maneje como 503
    except Exception as e:
        print(f"ERROR CRUD Coche: Error creando coche en Firestore: {e}")
        # Podrías querer un log más detallado aquí: import traceback; traceback.print_exc()
        return None

def get_coche_by_id_from_db(coche_id: str) -> Optional[CocheInDB]:
    db = get_db()
    try:
        doc_ref = db.collection(COCHES_COLLECTION).document(coche_id)
        doc = doc_ref.get()
        if doc.exists:
            coche_data = doc.to_dict()
            return CocheInDB(id=doc.id, **coche_data)
        print(f"INFO CRUD Coche: Coche con ID '{coche_id}' no encontrado.")
        return None
    except Exception as e:
        print(f"ERROR CRUD Coche: Error obteniendo coche '{coche_id}' de Firestore: {e}")
        return None

def get_all_coches_from_db(skip: int = 0, limit: int = 20) -> List[CocheInDB]:
    db = get_db()
    coches_list: List[CocheInDB] = []
    try:
        # Considera añadir un campo de timestamp para ordenar por más recientes si es necesario
        docs_query = db.collection(COCHES_COLLECTION).order_by("marca").offset(skip).limit(limit) 
        docs = docs_query.stream()
        for doc in docs:
            coche_data = doc.to_dict()
            coches_list.append(CocheInDB(id=doc.id, **coche_data))
        return coches_list
    except Exception as e:
        print(f"ERROR CRUD Coche: Error obteniendo todos los coches de Firestore: {e}")
        return []

def get_coches_by_user_id_from_db(user_id: str, skip: int = 0, limit: int = 20) -> List[CocheInDB]:
    db = get_db()
    coches_list: List[CocheInDB] = []
    try:
        print(f"--- DEBUG CRUD COCHE (get_coches_by_user_id): Buscando coches para user_id: {user_id} ---")
        docs_query = db.collection(COCHES_COLLECTION).where("user_id", "==", user_id).order_by("marca").offset(skip).limit(limit)
        docs = docs_query.stream()
        count = 0
        for doc in docs:
            count +=1
            coche_data = doc.to_dict()
            coches_list.append(CocheInDB(id=doc.id, **coche_data))
        print(f"--- DEBUG CRUD COCHE (get_coches_by_user_id): Encontrados {count} coches para user_id: {user_id} ---")
        return coches_list
    except Exception as e:
        print(f"ERROR CRUD Coche: Error obteniendo coches para el usuario '{user_id}': {e}")
        return []

def update_coche_in_db(coche_id: str, coche_update_data: CocheUpdate, current_user_id: str) -> Optional[CocheInDB | str]:
    db = get_db()
    try:
        coche_ref = db.collection(COCHES_COLLECTION).document(coche_id)
        coche_doc = coche_ref.get()

        if not coche_doc.exists:
            print(f"ADVERTENCIA CRUD Coche: Intento de actualizar coche no existente ID: {coche_id}")
            return None

        coche_actual_data = coche_doc.to_dict()
        if coche_actual_data.get("user_id") != current_user_id:
            print(f"ADVERTENCIA CRUD Coche: Usuario {current_user_id} intentó actualizar coche {coche_id} que no le pertenece.")
            return "UNAUTHORIZED"

        try: # Pydantic v2+
            update_data_dict = coche_update_data.model_dump(exclude_unset=True)
        except AttributeError: # Pydantic v1
            update_data_dict = coche_update_data.dict(exclude_none=True)

        if not update_data_dict: # Si no hay campos para actualizar (todos eran None o no se enviaron)
            print(f"INFO CRUD Coche: No hay datos válidos para actualizar en el coche {coche_id}.")
            # Devolver el coche sin cambios o un mensaje específico
            return CocheInDB(id=coche_id, **coche_actual_data) # Devuelve el coche actual

        update_data_dict["actualizado_en"] = firestore.SERVER_TIMESTAMP # Actualizar timestamp

        coche_ref.update(update_data_dict)
        updated_coche_doc = coche_ref.get() # Obtener el documento actualizado para devolverlo
        print(f"INFO CRUD Coche: Coche {coche_id} actualizado por usuario {current_user_id}.")
        return CocheInDB(id=updated_coche_doc.id, **updated_coche_doc.to_dict())
    except Exception as e:
        print(f"ERROR CRUD Coche: Error actualizando coche {coche_id} en Firestore: {e}")
        return None

def delete_coche_from_db(coche_id: str, current_user_id: str) -> Optional[bool | str]:
    db = get_db()
    try:
        coche_ref = db.collection(COCHES_COLLECTION).document(coche_id)
        coche_doc = coche_ref.get()

        if not coche_doc.exists:
            print(f"ADVERTENCIA CRUD Coche: Intento de eliminar coche no existente ID: {coche_id}")
            return False # Indica que no se encontró o no se eliminó

        coche_data = coche_doc.to_dict()
        if coche_data.get("user_id") != current_user_id:
            print(f"ADVERTENCIA CRUD Coche: Usuario {current_user_id} intentó eliminar coche {coche_id} que no le pertenece.")
            return "UNAUTHORIZED"

        # 1. Obtener las URLs de las imágenes ANTES de eliminar el documento
        image_urls_to_delete = coche_data.get("imagen_urls", [])

        # 2. Eliminar el documento del coche de Firestore
        coche_ref.delete()
        print(f"INFO CRUD Coche: Documento del coche {coche_id} eliminado de Firestore.")

        # 3. Eliminar el ID del coche de la lista coches_ids del usuario
        user_doc_ref = db.collection(USUARIOS_COLLECTION).document(current_user_id)
        user_doc_ref.update({"coches_ids": firestore.ArrayRemove([coche_id])})
        print(f"INFO CRUD Coche: ID del coche {coche_id} eliminado de la lista del usuario {current_user_id}.")
            
        # 4. Eliminar los archivos físicos de las imágenes del servidor
        if image_urls_to_delete and UPLOAD_DIR: # Asegurarse que UPLOAD_DIR esté disponible
            print(f"INFO CRUD Coche: Intentando eliminar {len(image_urls_to_delete)} archivos de imagen asociados al coche {coche_id} desde '{UPLOAD_DIR}'...")
            for url in image_urls_to_delete:
                try:
                    if "/uploaded_images/" in url:
                        filename = url.split("/uploaded_images/")[-1]
                        # from urllib.parse import unquote # Descomentar si es necesario
                        # filename = unquote(filename)
                        
                        file_path_to_delete = UPLOAD_DIR / filename
                        
                        if file_path_to_delete.is_file():
                            os.remove(file_path_to_delete)
                            print(f"INFO CRUD Coche: Archivo de imagen '{filename}' eliminado de '{file_path_to_delete}'.")
                        else:
                            print(f"ADVERTENCIA CRUD Coche: Archivo de imagen '{filename}' no encontrado en '{file_path_to_delete}' para eliminar.")
                    else:
                        print(f"ADVERTENCIA CRUD Coche: URL de imagen no tiene el formato esperado para extraer nombre de archivo: {url}")
                except Exception as e_file:
                    print(f"ERROR CRUD Coche: Error al intentar eliminar el archivo de imagen {url}: {e_file}")
        elif not UPLOAD_DIR:
             print(f"ADVERTENCIA CRUD Coche: UPLOAD_DIR no está configurado, no se pueden eliminar archivos de imagen para coche {coche_id}.")

        return True # Eliminación de la base de datos fue exitosa
    except Exception as e:
        print(f"ERROR CRUD Coche: Error general eliminando coche {coche_id} de Firestore o sus archivos: {e}")
        # import traceback # Para depuración más profunda
        # traceback.print_exc()
        return None # Indica un error interno más general que un simple "no encontrado"