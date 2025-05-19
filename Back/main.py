from fastapi import FastAPI, HTTPException, Depends, status, Response, File, UploadFile
# QUITA OAuth2PasswordBearer si solo se usa en dependencies.py ahora
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordRequestForm # Mantén esto si /token lo usa directamente
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List, Optional
from datetime import datetime, timedelta, timezone
# QUITA JWTError, jwt si solo se usan en dependencies.py ahora
# from jose import JWTError, jwt
import shutil
import os
from pathlib import Path
import uuid
import json
import traceback

# --- Importaciones de tus módulos locales ---
from crud import crud_user, crud_coche
from crud import crud_chat 
from models import models_user, models_coche, models_chat
from auth_config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, UPLOAD_DIR

# --- NUEVA IMPORTACIÓN DE DEPENDENCIAS ---
from dependencies import get_current_active_user # Importa la dependencia desde el nuevo archivo


# --- PRUEBAS DE IMPORTACIÓN (MANTENIDAS POR AHORA) ---
print("DEBUG (main.py): Iniciando pruebas de importación para 'routers'...")
try:
    import routers
    print(f"DEBUG (main.py): 'routers' importado exitosamente: {routers}")
    print(f"DEBUG (main.py): Contenido de 'routers' (dir(routers)): {dir(routers)}")
    if hasattr(routers, 'chat'):
        print(f"DEBUG (main.py): 'routers' TIENE el atributo 'chat': {getattr(routers, 'chat', 'No encontrado')}")
        if hasattr(routers.chat, 'router'):
            print(f"DEBUG (main.py): 'routers.chat' TIENE el atributo 'router': {getattr(routers.chat, 'router', 'No encontrado')}")
        else:
            print("DEBUG (main.py): 'routers.chat' NO tiene el atributo 'router'.")
    else:
        print("DEBUG (main.py): 'routers' NO tiene el atributo 'chat'.")
except ImportError as e_routers_direct:
    print(f"ERROR DEBUG (main.py): Falló la importación directa de 'routers': {e_routers_direct}")
    print(f"ERROR DEBUG (main.py): Traceback de error al importar 'routers':")
    traceback.print_exc()
except Exception as e_general_routers:
    print(f"ERROR DEBUG (main.py): Excepción general al intentar importar 'routers': {e_general_routers}")
    print(f"ERROR DEBUG (main.py): Traceback de excepción general al importar 'routers':")
    traceback.print_exc()
print("DEBUG (main.py): Fin de pruebas de importación para 'routers'.")
# --- FIN PRUEBAS DE IMPORTACIÓN ---


# --- Importar el router de chat (con captura de error más específica) ---
try:
    from routers import chat as chat_router 
    CHAT_ROUTER_IMPORTED = True
except ImportError as e_chat_router_import: 
    CHAT_ROUTER_IMPORTED = False
    print(f"ADVERTENCIA (main.py): No se pudo importar 'chat_router' desde 'routers'. Error: {e_chat_router_import}. Los endpoints de chat no estarán disponibles si están definidos en un router separado.")
    print(f"ADVERTENCIA (main.py): Traceback del error de importación de 'chat_router':")
    traceback.print_exc() 
except Exception as e_general_chat_router: 
    CHAT_ROUTER_IMPORTED = False
    print(f"ADVERTENCIA (main.py): Excepción general al importar 'chat_router' desde 'routers'. Error: {e_general_chat_router}. Los endpoints de chat no estarán disponibles.")
    print(f"ADVERTENCIA (main.py): Traceback de la excepción general al importar 'chat_router':")
    traceback.print_exc()


app = FastAPI(
    title="API TFG2 - Gestión de Coches, Usuarios y Chats", 
    description="Backend para la aplicación TFG2, utilizando FastAPI y Firebase.",
    version="0.1.1", 
)

# --- Configuración de CORS ---
origins = [
    "http://127.0.0.1:5001", 
    "http://localhost:5001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuración para servir archivos estáticos (imágenes subidas) ---
if UPLOAD_DIR and UPLOAD_DIR.is_dir(): 
    app.mount("/uploaded_images", StaticFiles(directory=UPLOAD_DIR), name="uploaded_images")
    print(f"INFO (main.py): StaticFiles montado para /uploaded_images desde {UPLOAD_DIR}")
else:
    print(f"ERROR (main.py): UPLOAD_DIR ('{UPLOAD_DIR}') no es un directorio válido o no existe. StaticFiles no montado.")


# --- oauth2_scheme SE MUEVE a dependencies.py ---
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") 

# --- Funciones Auxiliares para JWT y Autenticación ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    if "alias" in data and "sub" not in to_encode:
        to_encode["sub"] = data["alias"]
    elif "sub" not in to_encode:
        if "user_id" in data:
            to_encode["sub"] = data["user_id"]
        else:
            raise ValueError("El payload del token debe contener 'sub', 'alias', o 'user_id' para generar 'sub'.")

    # Importar jwt aquí si se quitó de las importaciones globales al principio
    from jose import jwt
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- get_current_active_user SE MUEVE a dependencies.py ---
# async def get_current_active_user(token: str = Depends(oauth2_scheme)) -> models_user.UserInDBBase:
#     ... (código de la función eliminado de aquí)


# --- Endpoint de prueba ---
@app.get("/", tags=["General"])
def read_root():
    try:
        from firebase_config import get_db
        db_client = get_db() 
        if db_client: 
            return {"message": "Bienvenido a la API de TFG2. Conexión con Firebase OK."}
        else:
            return {"message": "Bienvenido a la API de TFG2. ATENCIÓN: No se pudo obtener cliente de Firebase."}
    except Exception as e:
        return {"message": f"Bienvenido a la API de TFG2. Error al verificar Firebase: {e}"}

# --- Endpoints para la Gestión de Usuarios ---
@app.post(
    "/usuarios/",
    response_model=models_user.UserDisplay,
    status_code=status.HTTP_201_CREATED,
    tags=["Usuarios"],
    summary="Crear un nuevo usuario (Registro)"
)
def create_new_user(user_input: models_user.UserCreate):
    try:
        created_user = crud_user.create_user_in_db(user_input)
        if not created_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo crear el usuario. El alias podría ya estar en uso.")
    except ConnectionError as e:
        print(f"ERROR endpoint /usuarios/ (POST): Error de conexión con Firebase - {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"El servicio de base de datos no está disponible: {e}")
    except Exception as e:
        print(f"ERROR endpoint /usuarios/ (POST): Error inesperado al crear usuario - {e}")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ocurrió un error interno al crear el usuario.")
    return created_user

@app.get("/usuarios/me", response_model=models_user.UserDisplay, tags=["Usuarios"], summary="Obtener datos del usuario actual")
async def read_users_me(current_user: models_user.UserInDBBase = Depends(get_current_active_user)):
    return current_user

@app.put(
    "/usuarios/me",
    response_model=models_user.UserDisplay, 
    tags=["Usuarios"],
    summary="Actualizar el perfil del usuario actual (nombre, apellido, alias opcional)"
)
async def update_current_user_profile(
    user_update_payload: models_user.UserUpdate,
    current_user: models_user.UserInDBBase = Depends(get_current_active_user)
):
    try:
        updated_user_in_db = crud_user.update_user_in_db(user_id=current_user.id, user_update_data=user_update_payload)
        if updated_user_in_db is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se pudo actualizar el perfil del usuario. Usuario no encontrado o error interno."
            )
        return models_user.UserDisplay.model_validate(updated_user_in_db)
    except ValueError as ve: 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"ERROR endpoint /usuarios/me (PUT): Error actualizando perfil - {e}")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar el perfil.")

@app.delete(
    "/usuarios/me",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Usuarios"],
    summary="Eliminar la cuenta del usuario actual y todos sus datos asociados"
)
async def delete_current_user_account(
    current_user: models_user.UserInDBBase = Depends(get_current_active_user)
):
    try:
        success = crud_user.delete_user_from_db(user_id=current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="No se pudo eliminar la cuenta. Usuario no encontrado o error durante la eliminación."
            )
    except Exception as e:
        print(f"ERROR endpoint /usuarios/me (DELETE): Error eliminando cuenta - {e}")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar la cuenta.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Endpoints para Autenticación ---
@app.post("/token", response_model=models_user.Token, tags=["Autenticación"], summary="Obtener Token de Acceso (Form Data)")
async def login_for_access_token_form(form_data: OAuth2PasswordRequestForm = Depends()):
    user = crud_user.authenticate_user(alias=form_data.username, contrasena=form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Alias o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"alias": user.alias, "user_id": user.id}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=models_user.Token, tags=["Autenticación"], summary="Obtener Token de Acceso (JSON)")
async def login_for_access_token_json(user_credentials: models_user.UserLogin):
    user = crud_user.authenticate_user(alias=user_credentials.alias, contrasena=user_credentials.contrasena)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Alias o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"alias": user.alias, "user_id": user.id}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

# --- Endpoint para Subir Imágenes ---
@app.post("/upload-image/", tags=["Imágenes"], summary="Subir una imagen (requiere autenticación)")
async def create_upload_image(
    file: UploadFile = File(...),
    current_user: models_user.UserInDBBase = Depends(get_current_active_user) 
):
    allowed_content_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido: {file.content_type}. Permitidos: {', '.join(allowed_content_types)}"
        )

    file_extension = Path(file.filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    
    if not UPLOAD_DIR or not UPLOAD_DIR.is_dir(): 
        print(f"ERROR (upload-image): UPLOAD_DIR ('{UPLOAD_DIR}') no es válido.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de configuración del servidor para la subida de archivos.")
        
    file_location = UPLOAD_DIR / unique_filename

    try:
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
    except Exception as e:
        print(f"ERROR al guardar archivo '{unique_filename}' en '{file_location}': {e}")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo guardar el archivo en el servidor.")
    finally:
        await file.close() 

    image_url_path = f"/uploaded_images/{unique_filename}"
    base_backend_url = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000") 
    full_image_url = f"{base_backend_url}{image_url_path}"

    print(f"INFO: Imagen subida por '{current_user.alias}' a '{full_image_url}'")
    return {"message": "Imagen subida con éxito", "image_url": full_image_url}

# --- Endpoints para la Gestión de Coches ---
@app.post(
    "/coches/",
    response_model=models_coche.CocheDisplay, 
    status_code=status.HTTP_201_CREATED,
    tags=["Coches"],
    summary="Crear un nuevo coche para el usuario autenticado"
)
async def create_new_coche(
    coche_in: models_coche.CocheCreate,
    current_user: models_user.UserInDBBase = Depends(get_current_active_user)
):
    try:
        created_coche_in_db = crud_coche.create_coche_in_db(coche_data=coche_in, current_user=current_user)
        if created_coche_in_db is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo crear el coche debido a un error interno.")
        return models_coche.CocheDisplay.model_validate(created_coche_in_db)
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Servicio de base de datos no disponible: {e}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al crear el coche: {str(e)}")

@app.get(
    "/coches/{coche_id}",
    response_model=models_coche.CocheDisplay,
    tags=["Coches"],
    summary="Obtener un coche específico por su ID (público)"
)
async def read_coche_by_id(coche_id: str): 
    db_coche_in_db = crud_coche.get_coche_by_id_from_db(coche_id)
    if db_coche_in_db is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coche no encontrado")
    return models_coche.CocheDisplay.model_validate(db_coche_in_db)

@app.get(
    "/coches/",
    response_model=List[models_coche.CocheDisplay],
    tags=["Coches"],
    summary="Obtener una lista de todos los coches (público, con paginación)"
)
async def read_all_coches(skip: int = 0, limit: int = 100): 
    coches_in_db = crud_coche.get_all_coches_from_db(skip=skip, limit=limit)
    return [models_coche.CocheDisplay.model_validate(c) for c in coches_in_db]

@app.get(
    "/usuarios/me/coches/",
    response_model=List[models_coche.CocheDisplay],
    tags=["Coches"],
    summary="Obtener todos los coches del usuario actualmente autenticado"
)
async def read_my_coches(
    current_user: models_user.UserInDBBase = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 100
):
    coches_in_db = crud_coche.get_coches_by_user_id_from_db(user_id=current_user.id, skip=skip, limit=limit)
    return [models_coche.CocheDisplay.model_validate(c) for c in coches_in_db]

@app.put(
    "/coches/{coche_id}",
    response_model=models_coche.CocheDisplay,
    tags=["Coches"],
    summary="Actualizar un coche existente (requiere ser propietario)"
)
async def update_existing_coche(
    coche_id: str,
    coche_update: models_coche.CocheUpdate,
    current_user: models_user.UserInDBBase = Depends(get_current_active_user)
):
    try:
        updated_coche_result_in_db = crud_coche.update_coche_in_db(
            coche_id=coche_id,
            coche_update_data=coche_update,
            current_user_id=current_user.id
        )
        if updated_coche_result_in_db is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coche no encontrado o error al actualizar.")
        if updated_coche_result_in_db == "UNAUTHORIZED":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para modificar este coche.")
        if not isinstance(updated_coche_result_in_db, models_coche.CocheInDB):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Respuesta inesperada del servicio de actualización.")
        return models_coche.CocheDisplay.model_validate(updated_coche_result_in_db)
    except HTTPException: 
        raise
    except Exception as e:
        print(f"ERROR endpoint /coches/{coche_id} (PUT): Error actualizando coche - {e}")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar el coche.")

@app.delete(
    "/coches/{coche_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Coches"],
    summary="Eliminar un coche existente (requiere ser propietario)"
)
async def delete_existing_coche(
    coche_id: str,
    current_user: models_user.UserInDBBase = Depends(get_current_active_user)
):
    try:
        delete_result = crud_coche.delete_coche_from_db(coche_id=coche_id, current_user_id=current_user.id)

        if delete_result == "UNAUTHORIZED":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para eliminar este coche.")
        if delete_result is False: 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coche no encontrado.")
        if delete_result is None: 
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo eliminar el coche debido a un error interno.")
    except HTTPException: 
        raise
    except Exception as e:
        print(f"ERROR endpoint /coches/{coche_id} (DELETE): Error eliminando coche - {e}")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar el coche.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- INCLUIR EL ROUTER DE CHAT ---
if CHAT_ROUTER_IMPORTED and chat_router:
    app.include_router(chat_router.router) 
    print("INFO (main.py): Router de Chat incluido.")
else:
    print("INFO (main.py): Router de Chat NO incluido (no se importó o es None).")


# --- Ejecución con Uvicorn (para desarrollo) ---
if __name__ == "__main__":
    import uvicorn
    if UPLOAD_DIR:
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            print(f"INFO (main.py __main__): Directorio de subida UPLOAD_DIR ({UPLOAD_DIR}) asegurado.")
        except Exception as e:
            print(f"ERROR (main.py __main__): No se pudo asegurar el directorio de subida {UPLOAD_DIR}. Error: {e}")
    else:
        print(f"ERROR (main.py __main__): UPLOAD_DIR no está definido. La subida de archivos fallará.")
            
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True, 
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )