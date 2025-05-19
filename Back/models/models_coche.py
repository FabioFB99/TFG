# TFG2/Back/models/models_coche.py
from pydantic import BaseModel, Field
from typing import Optional, List # Asegúrate de importar List
from enum import Enum
from datetime import datetime # Necesario para campos de fecha/hora si los añadiéramos después

# Enums para campos con opciones limitadas
class CombustibleEnum(str, Enum):
    diesel = "diesel"
    gasolina = "gasolina"
    electrico = "electrico"
    hibrido = "hibrido"

class EstadoCocheEnum(str, Enum):
    disponible = "disponible"
    reservado = "reservado"
    vendido = "vendido"

# --- Modelo Base ---
# Contiene todos los campos comunes que describen un coche.
class CocheBase(BaseModel):
    # Campos existentes
    marca: str = Field(..., min_length=2, max_length=50, description="Marca del coche")
    modelo: str = Field(..., min_length=1, max_length=50, description="Modelo del coche")
    cv: int = Field(..., gt=0, description="Caballos de vapor (potencia)")
    color: str = Field(..., min_length=2, max_length=30, description="Color del coche")
    ano: int = Field(..., ge=1900, le=datetime.now().year + 1, description="Año de fabricación, ej: 2023") # Año actual + 1 como límite superior razonable
    combustible: CombustibleEnum = Field(..., description="Tipo de combustible")
    km: int = Field(..., ge=0, description="Kilometraje del coche")
    estado: EstadoCocheEnum = Field(default=EstadoCocheEnum.disponible, description="Estado actual del coche")

    # --- NUEVOS CAMPOS AÑADIDOS ---
    etiqueta: Optional[str] = Field(None, description="Etiqueta medioambiental (ej: 0, ECO, C, B)")
    descripcion: Optional[str] = Field(None, max_length=1000, description="Descripción detallada del coche") # Añadido max_length
    localidad: Optional[str] = Field(None, max_length=100, description="Localidad donde se encuentra el coche (ej: Madrid, Valencia)")
    imagen_urls: List[str] = Field(default=[], description="Lista de URLs de las imágenes del coche almacenadas en Firebase Storage")
    # --- FIN NUEVOS CAMPOS ---

    class Config:
        # Necesario para que Pydantic V2 pueda crear modelos desde atributos de objetos
        # y para usar Enums correctamente.
        from_attributes = True
        use_enum_values = True # Para que al convertir a dict/json se usen los valores del Enum ("diesel") y no el nombre ("CombustibleEnum.diesel")

# --- Modelo para Crear ---
# Lo que el cliente envía para crear un coche nuevo.
class CocheCreate(CocheBase):
    # Hereda todos los campos de CocheBase.
    # El user_id se añadirá en el backend.
    # El frontend deberá enviar el array (posiblemente vacío) de imagen_urls.
    pass

# --- Modelo para Actualizar ---
# Lo que el cliente envía para actualizar un coche existente (parcialmente).
class CocheUpdate(BaseModel):
    # Campos existentes (opcionales)
    marca: Optional[str] = Field(None, min_length=2, max_length=50)
    modelo: Optional[str] = Field(None, min_length=1, max_length=50)
    cv: Optional[int] = Field(None, gt=0)
    color: Optional[str] = Field(None, min_length=2, max_length=30)
    ano: Optional[int] = Field(None, ge=1900, le=datetime.now().year + 1)
    combustible: Optional[CombustibleEnum] = None
    km: Optional[int] = Field(None, ge=0)
    estado: Optional[EstadoCocheEnum] = None

    # --- NUEVOS CAMPOS (OPCIONALES) ---
    etiqueta: Optional[str] = Field(None, description="Etiqueta medioambiental (ej: 0, ECO, C, B)")
    descripcion: Optional[str] = Field(None, max_length=1000, description="Descripción detallada del coche")
    localidad: Optional[str] = Field(None, max_length=100, description="Localidad donde se encuentra el coche")
    # Si se incluye, reemplaza la lista completa de imágenes. Si es None, no se modifica.
    imagen_urls: Optional[List[str]] = Field(None, description="Lista COMPLETA de URLs para reemplazar las existentes.")
    # --- FIN NUEVOS CAMPOS ---

    class Config:
        use_enum_values = True # Importante para manejar los Enums en la actualización

# --- Modelo Interno (Base de Datos) ---
# Cómo se ve el coche en Firestore, incluyendo IDs y campos añadidos.
class CocheInDB(CocheBase):
    id: str = Field(..., description="ID único del coche asignado por Firestore")
    user_id: str = Field(..., description="ID del usuario propietario del coche")
    # Podrías añadir timestamps automáticos aquí si los gestionas en el CRUD
    # fecha_creacion: datetime
    # fecha_actualizacion: Optional[datetime] = None

    # Hereda todos los campos de CocheBase, incluyendo los nuevos.

    # Config ya heredada de CocheBase

# --- Modelo para Mostrar ---
# Lo que se devuelve al cliente en las respuestas GET.
class CocheDisplay(CocheBase):
    id: str
    user_id: str
    # Hereda todos los campos de CocheBase, incluyendo los nuevos.
    # La lista imagen_urls se incluirá aquí.

    # Config ya heredada de CocheBase