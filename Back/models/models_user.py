from pydantic import BaseModel, Field, EmailStr # EmailStr para validación de email si lo necesitas
from typing import List, Optional

# --- Modelos para Usuario ---

class UserBase(BaseModel):
    # Asumiendo que el alias será el "username" principal y debe ser único
    alias: str = Field(..., min_length=3, max_length=50, description="Alias único del usuario")
    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre del usuario")
    apellido: str = Field(..., min_length=1, max_length=100, description="Apellido del usuario")
    # email: Optional[EmailStr] = None # Si quieres añadir email y validarlo

class UserCreate(UserBase):
    # La contraseña se recibe en texto plano al crear el usuario, luego se hashea
    contrasena: str = Field(..., min_length=6, description="Contraseña del usuario (mínimo 6 caracteres)")
class UserUpdate(BaseModel):
    # Permitimos actualizar nombre, apellido.
    # El alias generalmente no se cambia una vez creado, o requiere lógica especial.
    # La contraseña se actualizaría a través de un endpoint diferente y más seguro.
    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    apellido: Optional[str] = Field(None, min_length=1, max_length=100)
    # Si quisieras permitir cambiar el alias, necesitarías verificar que no exista ya.
    alias: Optional[str] = Field(None, min_length=3, max_length=50)

class UserInDBBase(UserBase):
    # Lo que se almacena en la base de datos, incluyendo el ID de Firestore y la contraseña hasheada
    id: str # El ID que asigna Firestore
    hashed_contrasena: str
    # Estas listas almacenarán los IDs de los coches y chats asociados al usuario
    # Se podrían manejar como subcolecciones en Firestore también, pero empezamos simple.
    coches_ids: List[str] = []
    chats_ids: List[str] = []
    # foto_autentificador_url: Optional[str] = None # Si vas a guardar una URL a una imagen

class UserDisplay(UserBase):
    # Lo que se devuelve al cliente (API response), NUNCA la contraseña.
    id: str
    coches_ids: List[str] = []
    chats_ids: List[str] = []
    # foto_autentificador_url: Optional[str] = None

    class Config:
        # Para Pydantic v1 era orm_mode = True
        # Para Pydantic v2 es from_attributes = True
        # Esto permite que el modelo Pydantic se cree a partir de atributos de un objeto,
        # lo cual es útil si obtienes un objeto de base de datos y quieres convertirlo.
        from_attributes = True

# --- Modelos para Autenticación ---

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer" # Tipo de token estándar

class TokenData(BaseModel):
    # Lo que guardaremos dentro del JWT (payload)
    # 'sub' (subject) es el claim estándar para el identificador principal del token
    # En nuestro caso, el alias del usuario.
    sub: Optional[str] = None # Cambiado de 'alias' a 'sub' para seguir convención JWT

class UserLogin(BaseModel):
    # Lo que el usuario enviará para hacer login
    alias: str
    contrasena: str