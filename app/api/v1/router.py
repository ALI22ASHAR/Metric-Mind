from fastapi import APIRouter
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.datasets import router as datasets_router
from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.dashboards import dataset_dashboards_router, dashboards_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.insights import router as insights_router
from app.api.v1.endpoints.predictive import router as predictive_router
from app.api.v1.endpoints.exports import router as exports_router

api_v1_router = APIRouter()

# Register endpoint routers
api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(auth_router)
api_v1_router.include_router(datasets_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(dataset_dashboards_router)
api_v1_router.include_router(dashboards_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(insights_router)
api_v1_router.include_router(predictive_router)
api_v1_router.include_router(exports_router)
