# TFG2/Back/crud/crud_chat.py
from firebase_admin import firestore
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timezone

# Importaciones de tus módulos locales
from firebase_config import get_db
from models import models_chat, models_coche, models_user
from crud import crud_coche, crud_user

# Importar FieldFilter para la sintaxis moderna de where (opcional pero recomendado)
from google.cloud.firestore_v1.base_query import FieldFilter, And


CONVERSACIONES_COLLECTION = "conversaciones"
MENSAJES_SUBCOLLECTION = "mensajes"
USUARIOS_COLLECTION = "usuarios"

# --- VERSIÓN SÍNCRONA ---
def get_or_create_conversation(
    car_id: str,
    iniciador_user: models_user.UserInDBBase
) -> Tuple[Optional[models_chat.ChatConversationDisplay], Optional[str]]:
    db = get_db()
    print(f"INFO CRUD Chat (sync): Iniciando get_or_create_conversation para car_id='{car_id}', iniciador_id='{iniciador_user.id}'")

    coche = crud_coche.get_coche_by_id_from_db(car_id)
    if not coche:
        print(f"WARN CRUD Chat (sync): Coche con ID '{car_id}' no encontrado.")
        return None, "Coche no encontrado."
    
    propietario_coche_id = coche.user_id
    if not propietario_coche_id:
        print(f"WARN CRUD Chat (sync): Coche '{car_id}' no tiene un propietario asignado.")
        return None, "El coche no tiene un propietario asignado."

    if iniciador_user.id == propietario_coche_id:
        print(f"WARN CRUD Chat (sync): Usuario '{iniciador_user.id}' intentó iniciar chat consigo mismo sobre coche '{car_id}'.")
        return None, "No puedes iniciar un chat contigo mismo sobre tu propio coche."

    participantes_ids_ordenados = sorted([iniciador_user.id, propietario_coche_id])

    # Usando FieldFilter y And para la query
    conversations_query = db.collection(CONVERSACIONES_COLLECTION).where(
        filter=And([
            FieldFilter("car_id", "==", car_id),
            FieldFilter("participantes_ids", "==", participantes_ids_ordenados)
        ])
    ).limit(1)
    
    docs_stream = conversations_query.stream()
    
    existing_convo_doc = None
    for doc in docs_stream:
        existing_convo_doc = doc
        break

    if existing_convo_doc:
        convo_data = existing_convo_doc.to_dict()
        convo_id = existing_convo_doc.id
        print(f"INFO CRUD Chat (sync): Conversación existente encontrada ID: {convo_id}")
        
        propietario_user = crud_user.get_user_by_id_from_db(propietario_coche_id)
        if not propietario_user:
            print(f"WARN CRUD Chat (sync): No se pudo obtener la información del propietario (ID: {propietario_coche_id}) del coche.")
            return None, "No se pudo obtener la información del propietario del coche."

        otro_participante_id, otro_participante_alias = (propietario_coche_id, propietario_user.alias) \
            if iniciador_user.id != propietario_coche_id else (iniciador_user.id, iniciador_user.alias)

        return models_chat.ChatConversationDisplay(
            id=convo_id,
            car_id=car_id,
            car_marca=coche.marca,
            car_modelo=coche.modelo,
            car_primera_imagen_url=coche.imagen_urls[0] if coche.imagen_urls else None,
            otro_participante_id=otro_participante_id,
            otro_participante_alias=otro_participante_alias,
            ultimo_mensaje_texto=convo_data.get("ultimo_mensaje_texto"),
            ultimo_mensaje_en=convo_data.get("ultimo_mensaje_en"),
            creado_en=convo_data.get("creado_en")
        ), None

    print(f"INFO CRUD Chat (sync): No se encontró conversación existente. Creando una nueva...")
    propietario_user = crud_user.get_user_by_id_from_db(propietario_coche_id)
    if not propietario_user:
        print(f"ERROR CRUD Chat (sync): No se pudo encontrar el propietario del coche (ID: {propietario_coche_id}) para crear la conversación.")
        return None, "No se pudo encontrar la información del propietario del coche."

    new_convo_doc_ref = db.collection(CONVERSACIONES_COLLECTION).document()
    new_convo_data_internal = models_chat.ChatConversationCreateInternal(
        car_id=car_id,
        participantes_ids=participantes_ids_ordenados,
        participantes_info=[
            {"user_id": iniciador_user.id, "alias": iniciador_user.alias},
            {"user_id": propietario_user.id, "alias": propietario_user.alias}
        ],
        creado_en=datetime.now(timezone.utc),
    )
    
    try:
        new_convo_dict_to_save = new_convo_data_internal.model_dump(exclude_none=True) 
    except AttributeError:
        new_convo_dict_to_save = new_convo_data_internal.dict(exclude_none=True) 

    new_convo_doc_ref.set(new_convo_dict_to_save)
    new_convo_id = new_convo_doc_ref.id

    batch = db.batch()
    user1_ref = db.collection(USUARIOS_COLLECTION).document(iniciador_user.id)
    batch.update(user1_ref, {"chats_ids": firestore.ArrayUnion([new_convo_id])})
    user2_ref = db.collection(USUARIOS_COLLECTION).document(propietario_user.id)
    batch.update(user2_ref, {"chats_ids": firestore.ArrayUnion([new_convo_id])})
    batch.commit()
    
    print(f"INFO CRUD Chat (sync): Nueva conversación creada ID: {new_convo_id}. Chats_ids actualizados para usuarios.")

    return models_chat.ChatConversationDisplay(
        id=new_convo_id,
        car_id=car_id,
        car_marca=coche.marca,
        car_modelo=coche.modelo,
        car_primera_imagen_url=coche.imagen_urls[0] if coche.imagen_urls else None,
        otro_participante_id=propietario_user.id,
        otro_participante_alias=propietario_user.alias,
        ultimo_mensaje_texto=None,
        ultimo_mensaje_en=None,
        creado_en=new_convo_data_internal.creado_en
    ), None

def send_chat_message(
    conversation_id: str,
    sender_user: models_user.UserInDBBase,
    contenido: str
) -> Tuple[Optional[models_chat.ChatMessageDisplay], Optional[str]]:
    db = get_db()
    convo_ref = db.collection(CONVERSACIONES_COLLECTION).document(conversation_id)
    convo_doc = convo_ref.get()

    if not convo_doc.exists:
        print(f"WARN CRUD Chat (sync): Conversación ID '{conversation_id}' no encontrada al intentar enviar mensaje.")
        return None, "Conversación no encontrada."

    convo_data = convo_doc.to_dict()
    if sender_user.id not in convo_data.get("participantes_ids", []):
        print(f"WARN CRUD Chat (sync): Usuario '{sender_user.id}' no es participante de la conversación '{conversation_id}'.")
        return None, "No eres participante de esta conversación."

    message_doc_ref = convo_ref.collection(MENSAJES_SUBCOLLECTION).document()
    message_data_in_db = models_chat.ChatMessageInDB(
        sender_id=sender_user.id,
        contenido=contenido,
        timestamp=datetime.now(timezone.utc)
    )
    
    try:
        message_dict_to_save = message_data_in_db.model_dump()
    except AttributeError:
        message_dict_to_save = message_data_in_db.dict()

    message_doc_ref.set(message_dict_to_save)
    message_id = message_doc_ref.id

    convo_ref.update({
        "ultimo_mensaje_en": message_data_in_db.timestamp,
        "ultimo_mensaje_texto": contenido[:150]
    })
    print(f"INFO CRUD Chat (sync): Mensaje enviado a conversación '{conversation_id}' por '{sender_user.alias}'. Último mensaje actualizado.")

    return models_chat.ChatMessageDisplay(
        id=message_id,
        conversation_id=conversation_id,
        sender_id=sender_user.id,
        sender_alias=sender_user.alias,
        contenido=contenido,
        timestamp=message_data_in_db.timestamp
    ), None

def get_messages_for_conversation(
    conversation_id: str,
    current_user_id: str,
    limit: int = 50
) -> Tuple[Optional[List[models_chat.ChatMessageDisplay]], Optional[str]]:
    db = get_db()
    convo_ref = db.collection(CONVERSACIONES_COLLECTION).document(conversation_id)
    convo_doc = convo_ref.get()

    if not convo_doc.exists:
        print(f"WARN CRUD Chat (sync): Conversación ID '{conversation_id}' no encontrada al obtener mensajes.")
        return None, "Conversación no encontrada."

    convo_data = convo_doc.to_dict()
    if current_user_id not in convo_data.get("participantes_ids", []):
        print(f"WARN CRUD Chat (sync): Usuario '{current_user_id}' intentó acceder a mensajes de conversación '{conversation_id}' sin ser participante.")
        return None, "No tienes acceso a los mensajes de esta conversación."

    messages_query = convo_ref.collection(MENSAJES_SUBCOLLECTION).order_by(
        "timestamp", direction=firestore.Query.ASCENDING
    ).limit(limit)
    
    message_docs_stream = messages_query.stream()
    
    messages_display_list: List[models_chat.ChatMessageDisplay] = []
    sender_aliases_cache: Dict[str, str] = {}

    for doc in message_docs_stream:
        msg_data = doc.to_dict()
        msg_sender_id = msg_data.get("sender_id")
        sender_alias = "Desconocido"

        if msg_sender_id:
            if msg_sender_id in sender_aliases_cache:
                sender_alias = sender_aliases_cache[msg_sender_id]
            else:
                user = crud_user.get_user_by_id_from_db(msg_sender_id)
                if user:
                    sender_alias = user.alias
                    sender_aliases_cache[msg_sender_id] = sender_alias
        
        messages_display_list.append(models_chat.ChatMessageDisplay(
            id=doc.id,
            conversation_id=conversation_id,
            sender_id=msg_sender_id,
            sender_alias=sender_alias,
            contenido=msg_data.get("contenido"),
            timestamp=msg_data.get("timestamp")
        ))
    print(f"INFO CRUD Chat (sync): Obtenidos {len(messages_display_list)} mensajes para conversación '{conversation_id}'.")
    return messages_display_list, None

# --- VERSIÓN SÍNCRONA CON QUERY SIMPLIFICADA ---
def get_user_conversations(
    user_id: str
) -> List[models_chat.ChatConversationDisplay]:
    db = get_db()
    print(f"DEBUG CRUD Chat (get_user_conversations): Buscando conversaciones para user_id='{user_id}' SIN order_by") # Log
    
    # Query solo con el filtro array_contains
    conversations_query = db.collection(CONVERSACIONES_COLLECTION).where(
        filter=FieldFilter("participantes_ids", "array_contains", user_id) # Usando FieldFilter
    )
    # --- LÍNEA COMENTADA PARA LA PRUEBA ---
    # .order_by("ultimo_mensaje_en", direction=firestore.Query.DESCENDING) 
    
    convo_docs_stream = conversations_query.stream()
    user_conversations_display: List[models_chat.ChatConversationDisplay] = []
    count = 0 # Para contar cuántos documentos devuelve la query
    
    for doc in convo_docs_stream:
        count += 1
        convo_data = doc.to_dict()
        convo_id = doc.id
        car_id_for_convo = convo_data.get("car_id")

        car_marca, car_modelo, car_primera_imagen_url = None, None, None
        if car_id_for_convo:
            coche = crud_coche.get_coche_by_id_from_db(car_id_for_convo)
            if coche:
                car_marca = coche.marca
                car_modelo = coche.modelo
                car_primera_imagen_url = coche.imagen_urls[0] if coche.imagen_urls else None
        
        otro_participante_id_found = None
        otro_participante_alias_found = "Desconocido"
        
        participantes_info_list = convo_data.get("participantes_info", [])
        for p_info in participantes_info_list:
            if p_info.get("user_id") != user_id:
                otro_participante_id_found = p_info.get("user_id")
                otro_participante_alias_found = p_info.get("alias", "Desconocido")
                break
        
        if not otro_participante_id_found: # Fallback si participantes_info no está bien formada
            for pid_convo in convo_data.get("participantes_ids", []):
                if pid_convo != user_id:
                    otro_participante_id_found = pid_convo
                    otro_user_obj = crud_user.get_user_by_id_from_db(otro_participante_id_found)
                    if otro_user_obj:
                        otro_participante_alias_found = otro_user_obj.alias
                    break
        
        if otro_participante_id_found: 
            user_conversations_display.append(models_chat.ChatConversationDisplay(
                id=convo_id,
                car_id=car_id_for_convo,
                car_marca=car_marca,
                car_modelo=car_modelo,
                car_primera_imagen_url=car_primera_imagen_url,
                otro_participante_id=otro_participante_id_found,
                otro_participante_alias=otro_participante_alias_found,
                ultimo_mensaje_texto=convo_data.get("ultimo_mensaje_texto"),
                ultimo_mensaje_en=convo_data.get("ultimo_mensaje_en"),
                creado_en=convo_data.get("creado_en")
            ))
    print(f"DEBUG CRUD Chat (get_user_conversations): Query devolvió {count} documentos. Procesados {len(user_conversations_display)} para display.")
    return user_conversations_display