# Back/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional

# Importaciones de tus módulos locales
# Asegúrate de que estas rutas sean correctas desde la perspectiva de dependencies.py
# Si dependencies.py está en Back/, estas importaciones deberían funcionar:
from models import models_user  # Asumiendo que Back/models/ es un paquete
from crud import crud_user      # Asumiendo que Back/crud/ es un paquete
from auth_config import SECRET_KEY, ALGORITHM # auth_config.py está en Back/

# Define oauth2_scheme aquí, ya que get_current_active_user depende de él.
# El tokenUrl debe coincidir con el endpoint de login en main.py que genera el token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # o "/token" si usas el endpoint de formulario

async def get_current_active_user(token: str = Depends(oauth2_scheme)) -> models_user.UserInDBBase:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales (token inválido o expirado)",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        identifier: Optional[str] = payload.get("sub") # 'sub' debería ser el alias del usuario
        if identifier is None:
            print("ERROR (dependencies.py): Falta el 'sub' (alias) en el payload del token.")
            raise credentials_exception
    except JWTError as e:
        print(f"ERROR (dependencies.py): Error decodificando token JWT: {e}")
        raise credentials_exception
    
    user = crud_user.get_user_by_alias_from_db(alias=identifier)
    if user is None:
        print(f"ERROR (dependencies.py): Usuario '{identifier}' del token no encontrado en la BD.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, # O 401
            detail=f"Usuario '{identifier}' no encontrado."
        )
    return user