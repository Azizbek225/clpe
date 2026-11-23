from fastapi import APIRouter

from app.api.v1 import admin, assessment, auth, courses, ctf, labs, vms

api_router = APIRouter(prefix="/api/v1")
for r in (auth, courses, assessment, labs, vms, ctf, admin):
    api_router.include_router(r.router)
