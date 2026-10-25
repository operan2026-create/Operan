from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.organizations import router as orgs_router
from app.api.v1.roles import router as roles_router
from app.api.v1.academy import router as academy_router
from app.api.v1.locations import router as locations_router
from app.api.v1.professionals import router as professionals_router
from app.api.v1.missions import router as missions_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(orgs_router)
api_router.include_router(roles_router)
api_router.include_router(academy_router)
api_router.include_router(locations_router)
api_router.include_router(professionals_router)
api_router.include_router(missions_router)
