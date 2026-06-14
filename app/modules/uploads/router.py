"""
Módulo /uploads — gestión de imágenes en Cloudinary.

POST /api/v1/uploads/imagen              → sube una imagen, devuelve secure_url + public_id
DELETE /api/v1/uploads/imagen/{public_id} → elimina una imagen por public_id

Solo accesible por ADMIN.
"""
from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status
from pydantic import BaseModel

import cloudinary
import cloudinary.uploader

from app.core.config import settings
from app.core.dependencies import require_role

router = APIRouter(prefix="/api/v1/uploads", tags=["Uploads"])

_ADMIN = Depends(require_role(["ADMIN"]))

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB (doc §10.1 paso 3)


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


class CloudinaryResponse(BaseModel):
    """Respuesta del upload (doc §6.3). secure_url se guarda en imagenes_url[]."""
    secure_url: str
    public_id: str
    width: int
    height: int
    format: str
    resource_type: str


# Alias retrocompatible — el nombre canónico de la doc es CloudinaryResponse.
UploadResponse = CloudinaryResponse


@router.post("/imagen", response_model=CloudinaryResponse, status_code=status.HTTP_201_CREATED, summary="Subir imagen a Cloudinary")
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
        # Validar tamaño ≤ 5 MB (doc §10.1 paso 3)
        if len(contents) > _MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "La imagen supera el máximo de 5 MB", "code": "FILE_TOO_LARGE"},
            )
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            allowed_formats=["jpg", "jpeg", "png", "webp"],
            overwrite=False,
            unique_filename=True,
            resource_type="image",
            transformation=[{"width": 800, "height": 800, "crop": "limit", "quality": "auto"}],
        )
        return CloudinaryResponse(
            secure_url=result["secure_url"],
            public_id=result["public_id"],
            width=result["width"],
            height=result["height"],
            format=result["format"],
            resource_type=result["resource_type"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"detail": f"Error al subir imagen a Cloudinary: {str(e)}", "code": "CLOUDINARY_UPLOAD_ERROR"},
        )


@router.delete("/imagen/{public_id:path}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar imagen de Cloudinary por public_id")
def delete_image(
    public_id: str = Path(..., description="public_id de la imagen en Cloudinary"),
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
