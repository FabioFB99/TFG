# TFG2/Back/crud/crud_user.py

from firebase_config import get_db
from models.models_user import UserCreate, UserDisplay, UserInDBBase, UserUpdate # Asegúrate que UserUpdate esté aquí
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional, List # Asegúrate de importar List si no está ya
from firebase_admin import firestore 

USUARIOS_COLLECTION = "usuarios"
COCHES_COLLECTION = "coches" 

def create_user_in_db(user_data: UserCreate) -> Optional[UserDisplay]:
    """
    Crea un nuevo usuario en Firestore.
    Hashea la contraseña antes de guardarla.
    Verifica si el alias ya existe.
    """
    db = get_db()
    try:
        users_ref = db.collection(USUARIOS_COLLECTION)
        # Comprobar si el alias ya existe
        existing_user_query = users_ref.where("alias", "==", user_data.alias).limit(1).stream()
        if any(doc.exists for doc in existing_user_query): # Más explícito para verificar si algún documento existe
            print(f"ADVERTENCIA CRUD User: El alias '{user_data.alias}' ya está en uso.")
            # Podrías lanzar una excepción aquí para que el endpoint lo maneje mejor
            # raise ValueError(f"El alias '{user_data.alias}' ya está en uso.")
            return None 
        
        hashed_password = generate_password_hash(user_data.contrasena)
        # Definir los campos explícitamente para el modelo UserInDBBase
        # Asegurarse que todos los campos de UserInDBBase que no tienen default
        # o que no son Optional[None] están aquí.
        user_doc_data = {
            "alias": user_data.alias,
            "nombre": user_data.nombre,
            "apellido": user_data.apellido,
            "hashed_contrasena": hashed_password,
            "coches_ids": [],  # Valor inicial para la lista de coches
            "chats_ids": []    # Valor inicial para la lista de chats
        }
        # Crear un nuevo documento con un ID generado automáticamente
        doc_ref = db.collection(USUARIOS_COLLECTION).document()
        doc_ref.set(user_doc_data)
        print(f"INFO CRUD User: Usuario '{user_data.alias}' creado con ID: {doc_ref.id} en Firestore.")
        
        # Devolver el modelo UserDisplay
        return UserDisplay(
            id=doc_ref.id, # Usar el ID del documento creado
            alias=user_data.alias,
            nombre=user_data.nombre,
            apellido=user_data.apellido,
            coches_ids=[], # Coincidir con lo guardado
            chats_ids=[]   # Coincidir con lo guardado
        )
    except ConnectionError as ce:
        print(f"ERROR CRUD User: Error de conexión con Firebase al crear usuario: {ce}")
        raise # Re-lanzar para que sea manejado por el endpoint
    except Exception as e:
        print(f"ERROR CRUD User: Error creando usuario '{user_data.alias}' en Firestore: {e}")
        # import traceback
        # traceback.print_exc()
        return None

def get_user_by_alias_from_db(alias: str) -> Optional[UserInDBBase]:
    """
    Obtiene un usuario de Firestore por su alias.
    """
    db = get_db()
    try:
        users_ref = db.collection(USUARIOS_COLLECTION)
        query_results = users_ref.where("alias", "==", alias).limit(1).stream()
        for doc in query_results:
            if doc.exists: # Comprobar si el documento realmente existe
                user_data = doc.to_dict()
                # Asegurarse de que todos los campos necesarios para UserInDBBase estén
                # o tengan defaults en el modelo.
                # Por ejemplo, si coches_ids o chats_ids no están, Pydantic podría fallar.
                user_data.setdefault("coches_ids", []) # Añadir default si no existe
                user_data.setdefault("chats_ids", [])  # Añadir default si no existe
                print(f"INFO CRUD User: Usuario encontrado por alias '{alias}': ID {doc.id}")
                return UserInDBBase(id=doc.id, **user_data)
        print(f"INFO CRUD User: No se encontró usuario con alias '{alias}'.")
        return None
    except ConnectionError as ce:
        print(f"ERROR CRUD User: Error de conexión con Firebase buscando alias '{alias}': {ce}")
        raise
    except Exception as e:
        print(f"ERROR CRUD User: Error obteniendo usuario por alias '{alias}': {e}")
        return None

def authenticate_user(alias: str, contrasena: str) -> Optional[UserInDBBase]:
    """
    Autentica a un usuario.
    """
    user_in_db = get_user_by_alias_from_db(alias)
    if not user_in_db:
        return None # Usuario no encontrado
    if not check_password_hash(user_in_db.hashed_contrasena, contrasena):
        print(f"AUTH_FAIL: Contraseña incorrecta para el alias '{alias}'.")
        return None # Contraseña incorrecta
    print(f"AUTH_SUCCESS: Usuario '{alias}' autenticado correctamente.")
    return user_in_db

# --- NUEVA FUNCIÓN AÑADIDA ---
def get_user_by_id_from_db(user_id: str) -> Optional[UserInDBBase]:
    """
    Obtiene un usuario de Firestore por su ID de documento.
    """
    db = get_db()
    try:
        user_ref = db.collection(USUARIOS_COLLECTION).document(user_id)
        user_doc = user_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            # Asegurar defaults para listas si no existen en el documento
            user_data.setdefault("coches_ids", [])
            user_data.setdefault("chats_ids", [])
            print(f"INFO CRUD User: Usuario encontrado por ID '{user_id}'.")
            return UserInDBBase(id=user_doc.id, **user_data) # id ya es user_doc.id
        else:
            print(f"WARN CRUD User: No se encontró usuario con ID '{user_id}'.")
            return None
    except Exception as e:
        print(f"ERROR CRUD User: Error obteniendo usuario por ID '{user_id}': {e}")
        return None
# --- FIN NUEVA FUNCIÓN ---


def update_user_in_db(user_id: str, user_update_data: UserUpdate) -> Optional[UserInDBBase]:
    """Actualiza los datos de un usuario en Firestore (nombre, apellido, y opcionalmente alias)."""
    db = get_db()
    try:
        user_ref = db.collection(USUARIOS_COLLECTION).document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            print(f"ADVERTENCIA CRUD User: Intento de actualizar usuario no existente ID: {user_id}")
            return None

        update_data_dict = user_update_data.model_dump(exclude_unset=True) 

        if not update_data_dict: 
            print(f"INFO CRUD User: No hay datos proporcionados para actualizar en el usuario {user_id}.")
            current_data = user_doc.to_dict()
            current_data.setdefault("coches_ids", [])
            current_data.setdefault("chats_ids", [])
            return UserInDBBase(id=user_id, **current_data)

        # Si se intenta actualizar el alias, verificar que no esté ya en uso por otro usuario
        if "alias" in update_data_dict and update_data_dict["alias"] != user_doc.to_dict().get("alias"):
            existing_user_query = db.collection(USUARIOS_COLLECTION).where("alias", "==", update_data_dict["alias"]).limit(1).stream()
            if any(doc.exists for doc in existing_user_query):
                print(f"ADVERTENCIA CRUD User: Intento de actualizar a un alias ('{update_data_dict['alias']}') que ya está en uso.")
                # Podrías lanzar una excepción aquí para que el endpoint lo maneje
                # raise ValueError(f"El alias '{update_data_dict['alias']}' ya está en uso.")
                # O devolver un código/mensaje de error específico. Por ahora, no actualizamos y devolvemos None.
                # O mejor, devolver el usuario sin el cambio de alias.
                # Por simplicidad, aquí evitamos la actualización si el alias está duplicado.
                # Esto podría mejorarse devolviendo un error más específico.
                raise ValueError(f"El alias '{update_data_dict['alias']}' ya está en uso por otro usuario.")


        user_ref.update(update_data_dict)
        updated_user_doc = user_ref.get() 
        updated_data_full = updated_user_doc.to_dict()
        updated_data_full.setdefault("coches_ids", [])
        updated_data_full.setdefault("chats_ids", [])
        print(f"INFO CRUD User: Usuario {user_id} actualizado con: {update_data_dict}")
        return UserInDBBase(id=updated_user_doc.id, **updated_data_full)

    except ValueError as ve: # Capturar el ValueError del alias duplicado
        print(f"ERROR CRUD User: {ve}")
        raise # Re-lanzar para que el endpoint lo maneje
    except Exception as e:
        print(f"ERROR CRUD User: Error actualizando usuario {user_id} en Firestore: {e}")
        return None

def delete_user_from_db(user_id: str) -> bool:
    """
    Elimina un usuario y todos sus coches asociados de Firestore.
    Usa un batch para intentar hacer las eliminaciones de coches de forma más eficiente.
    """
    db = get_db()
    try:
        user_ref = db.collection(USUARIOS_COLLECTION).document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            print(f"ADVERTENCIA CRUD User: Intento de eliminar usuario no existente ID: {user_id}")
            return False 

        user_data = user_doc.to_dict()
        coches_ids_a_eliminar = user_data.get("coches_ids", [])

        batch = db.batch()

        if coches_ids_a_eliminar:
            for coche_id in coches_ids_a_eliminar:
                # Aquí necesitarías la lógica para eliminar también las imágenes de los coches
                # Esta función delete_coche_from_db_internal no existe, es un placeholder
                # Deberías llamar a tu crud_coche.delete_coche_from_db o una versión interna
                # que maneje la eliminación del documento y sus archivos de imagen.
                # Por ahora, solo eliminamos el documento del coche.
                # ¡IMPORTANTE! Esto no eliminará las imágenes físicas de los coches.
                coche_ref_to_delete = db.collection(COCHES_COLLECTION).document(coche_id)
                batch.delete(coche_ref_to_delete)
                print(f"INFO CRUD User: Coche {coche_id} (de usuario {user_id}) marcado para eliminación en batch.")
        
        batch.delete(user_ref)
        print(f"INFO CRUD User: Usuario {user_id} marcado para eliminación en batch.")

        batch.commit()
        
        print(f"INFO CRUD User: Usuario {user_id} y sus documentos de coches asociados eliminados exitosamente.")
        # NOTA: Las imágenes físicas de los coches NO se eliminan con esta lógica.
        # Deberías integrar la lógica de crud_coche.delete_coche_from_db para cada coche.
        return True
        
    except Exception as e:
        print(f"ERROR CRUD User: Error eliminando usuario {user_id} y/o sus coches de Firestore: {e}")
        return False