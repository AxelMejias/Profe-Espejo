from typing import Optional
from pydantic import BaseModel, Field


class IngredienteCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100, description="Nombre del ingrediente")
    unidad_medida: str = Field(
        min_length=1, max_length=50, description="Unidad de medida (kg, g, ml, unidad, etc.)"
    )


class IngredienteUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    unidad_medida: Optional[str] = Field(default=None, min_length=1, max_length=50)


class IngredienteResponse(BaseModel):
    id: int
    nombre: str
    unidad_medida: str

    model_config = {"from_attributes": True}
