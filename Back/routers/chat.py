# Back/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List

# Importaciones de tus módulos locales
from models import models_chat, models_user
from crud import crud_chat
from dependencies import get_current_active_user # Importar desde el archivo de dependencias

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    responses={404: {"description": "Not found"}},
)

# --- ENDPOINT DE PRUEBA (puede seguir siendo async si no hace I/O) ---
@router.get("/test-router", summary="Endpoint de prueba para el router de chat")
async def test_chat_router(): # Dejamos este como async ya que no hace I/O bloqueante
    return {"message": "El router de Chat está funcionando correctamente!"}
# --- FIN ENDPOINT DE PRUEBA ---


@router.post("/conversations/initiate", 
             response_model=models_chat.ChatConversationDisplay,
             summary="Iniciar o obtener una conversación sobre un coche")
# QUITA async
def initiate_or_get_conversation_endpoint(
    car_id: str = Query(..., description="ID del coche para iniciar la conversación", example="some_car_id_here"),
    current_user: models_user.UserInDBBase = Depends(get_current_active_user) # get_current_active_user puede seguir siendo async
):
    # QUITA await de la llamada al CRUD si el CRUD es síncrono
    conversation, error = crud_chat.get_or_create_conversation( # Asume que crud_chat.get_or_create_conversation es ahora síncrona
        car_id=car_id,
        iniciador_user=current_user
    )
    if error:
        if "contigo mismo" in error:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
        if "Coche no encontrado" in error or "propietario asignado" in error or "propietario del coche" in error:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error) 
        
    if not conversation: 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo crear o encontrar la conversación por un error desconocido.")
    
    return conversation


@router.post("/conversations/{conversation_id}/messages", 
             response_model=models_chat.ChatMessageDisplay,
             summary="Enviar un mensaje a una conversación")
# QUITA async
def post_message_to_conversation_endpoint(
    conversation_id: str,
    message: models_chat.ChatMessageCreate,
    current_user: models_user.UserInDBBase = Depends(get_current_active_user)
):
    # QUITA await
    sent_message, error = crud_chat.send_chat_message( # Asume que crud_chat.send_chat_message es ahora síncrona
        conversation_id=conversation_id,
        sender_user=current_user,
        contenido=message.contenido
    )
    if error:
        if "no eres participante" in error.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)
        if "no encontrada" in error.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    if not sent_message: 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo enviar el mensaje por un error desconocido.")
    return sent_message


@router.get("/conversations/{conversation_id}/messages", 
            response_model=List[models_chat.ChatMessageDisplay],
            summary="Obtener mensajes de una conversación específica")
# QUITA async
def get_conversation_messages_endpoint(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200, description="Número máximo de mensajes a devolver"),
    current_user: models_user.UserInDBBase = Depends(get_current_active_user)
):
    # QUITA await
    messages, error = crud_chat.get_messages_for_conversation( # Asume que crud_chat.get_messages_for_conversation es ahora síncrona
        conversation_id=conversation_id,
        current_user_id=current_user.id,
        limit=limit
    )
    if error:
        if "no tienes acceso" in error.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)
        else: 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
    
    return messages if messages is not None else []


@router.get("/conversations/me", 
            response_model=List[models_chat.ChatConversationDisplay],
            summary="Obtener todas las conversaciones del usuario actual")
# QUITA async
def get_my_conversations_endpoint(
    current_user: models_user.UserInDBBase = Depends(get_current_active_user)
):
    # QUITA await
    conversations = crud_chat.get_user_conversations(user_id=current_user.id) # Asume que crud_chat.get_user_conversations es ahora síncrona
    return conversations