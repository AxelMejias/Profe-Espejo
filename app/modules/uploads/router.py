"""
Módulo /uploads — gestión de imágenes en Cloudinary.

POST /api/v1/uploads        → sube una imagen, devuelve secure_url + public_id
DELETE /api/v1/uploads      → elimina una imagen por public_id

Solo accesible por ADMIN.
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

import cloudinary
import cloudinary.uploader

from app.core.config import settings
from app.core.dependencies import require_role

router = APIRouter(prefix="/api/v1/uploads", tags=["Uploads"])

_ADMIN = Depends(require_role(["ADMIN"]))

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _configure_cloudinary():
    if not settings.CLOUDINARY_CLOUD_NAME:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": "Cloudinary no configurado. Agregá las credenciales al .env", "code": "CLOUDINARY_NOT_CONFIGURED"},
        )
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )


class UploadResponse(BaseModel):
    secure_url: str
    public_id: str


@router.post("/", response_model=UploadResponse, status_code=status.HTTP_201_CREATED, summary="Subir imagen a Cloudinary")
def upload_image(
    archivo: UploadFile = File(...),
    folder: str = Query(default="foodstore/productos", description="Carpeta destino en Cloudinary"),
    _=_ADMIN,
):
    _configure_cloudinary()
    if archivo.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Solo se permiten imágenes (jpg, png, webp, gif)", "code": "INVALID_FILE_TYPE"},
        )
    try:
        contents = archivo.file.read()
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            transformation=[{"width": 800, "height": 800, "crop": "limit", "quality": "auto"}],
        )
        return UploadResponse(secure_url=result["secure_url"], public_id=result["public_id"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"detail": f"Error al subir imagen a Cloudinary: {str(e)}", "code": "CLOUDINARY_UPLOAD_ERROR"},
        )


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar imagen de Cloudinary por public_id")
def delete_image(
    public_id: str = Query(..., description="public_id de la imagen en Cloudinary"),
    _=_ADMIN,
):
    _configure_cloudinary()
    try:
        result = cloudinary.uploader.destroy(public_id)
        if result.get("result") not in ("ok", "not found"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"detail": f"Cloudinary respondió: {result}", "code": "CLOUDINARY_DELETE_ERROR"},
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"detail": f"Error al eliminar imagen de Cloudinary: {str(e)}", "code": "CLOUDINARY_DELETE_ERROR"},
        )
