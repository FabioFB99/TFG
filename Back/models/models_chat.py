# Back/models/models_chat.py
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict
from datetime import datetime

# --- Modelos para Mensajes ---

class ChatMessageBase(BaseModel):
    """Modelo base para el contenido de un mensaje."""
    contenido: str = Field(..., min_length=1, max_length=1000, description="Contenido textual del mensaje.")

class ChatMessageCreate(ChatMessageBase):
    """
    Modelo para la creación de un nuevo mensaje.
    El sender_id y conversation_id se determinarán en el backend.
    """
    pass # Hereda 'contenido' de ChatMessageBase

class ChatMessageInDB(ChatMessageBase):
    """Modelo de cómo se almacena un mensaje en la subcolección de Firestore."""
    sender_id: str = Field(..., description="ID del usuario que envió el mensaje.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp de cuándo se envió el mensaje.")
    # podrías añadir 'leido_por: List[str] = []' si quieres seguimiento de lectura por participante

class ChatMessageDisplay(ChatMessageInDB):
    """Modelo para mostrar un mensaje en la API, incluyendo su ID y el alias del remitente."""
    id: str = Field(..., description="ID único del mensaje asignado por Firestore.")
    conversation_id: str = Field(..., description="ID de la conversación a la que pertenece el mensaje.")
    sender_alias: Optional[str] = Field(None, description="Alias del usuario que envió el mensaje.")

    class Config:
        from_attributes = True
        # use_enum_values = True # Si tuvieras Enums


# --- Modelos para Conversaciones ---

class ChatConversationBase(BaseModel):
    """Modelo base para una conversación, centrado en el coche."""
    car_id: str = Field(..., description="ID del coche sobre el que trata la conversación.")

class ChatConversationCreateInternal(ChatConversationBase):
    """
    Modelo interno para crear una nueva conversación en la base de datos.
    Los participantes y timestamps se manejan en el CRUD.
    """
    participantes_ids: List[str] = Field(..., min_items=2, max_items=2, description="Lista con los IDs de los dos usuarios participantes.")
    participantes_info: List[Dict[str, str]] = Field(..., description="Lista de diccionarios con 'user_id' y 'alias' de los participantes.")
    creado_en: datetime = Field(default_factory=datetime.utcnow)
    ultimo_mensaje_en: Optional[datetime] = None
    ultimo_mensaje_texto: Optional[str] = Field(None, max_length=150) # Un extracto del último mensaje

class ChatConversationInDB(ChatConversationCreateInternal):
    """Modelo de cómo se almacena una conversación en Firestore, incluyendo su ID."""
    id: str = Field(..., description="ID único de la conversación asignado por Firestore.")

class ChatConversationDisplay(BaseModel):
    """
    Modelo para mostrar una conversación en la API.
    Enriquecido con información útil para la UI.
    """
    id: str = Field(..., description="ID de la conversación.")
    car_id: str = Field(..., description="ID del coche.")
    
    # Información del coche (para mostrar en la lista de chats)
    car_marca: Optional[str] = None
    car_modelo: Optional[str] = None
    car_primera_imagen_url: Optional[HttpUrl] = None # Usamos HttpUrl si es una URL completa

    # Información de los participantes
    # participantes_ids: List[str] # Podrías incluirla si el frontend la necesita directamente
    
    # Información específica del "otro" participante desde la perspectiva del usuario actual
    otro_participante_id: str = Field(..., description="ID del otro usuario en la conversación.")
    otro_participante_alias: str = Field(..., description="Alias del otro usuario en la conversación.")
    
    # Información del último mensaje
    ultimo_mensaje_texto: Optional[str] = Field(None, description="Extracto del último mensaje.")
    ultimo_mensaje_en: Optional[datetime] = Field(None, description="Timestamp del último mensaje.")
    
    # Podrías añadir un contador de mensajes no leídos para el usuario actual si implementas esa lógica
    # no_leidos_count: Optional[int] = 0
    
    creado_en: datetime

    class Config:
        from_attributes = True
        # use_enum_values = True # Si tuvieras Enums

# Modelo para la solicitud de iniciar una conversación (lo que envía el frontend)
class InitiateChatRequest(BaseModel):
    car_id: str