from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.download.router import router as download_router
from app.drive.router import router as drive_router
from app.file_version.router import router as file_version_router
from app.preview.router import router as preview_router
from app.upload.router import router as upload_router
from app.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(drive_router)
api_router.include_router(file_version_router)
api_router.include_router(upload_router)
api_router.include_router(download_router)
api_router.include_router(preview_router)
