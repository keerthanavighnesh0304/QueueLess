from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.database import get_db, test_connection
from app.routers.auth import router as auth_router
from app.routers.hospitals import router as hospitals_router
from app.routers.admin import router as admin_router
from app.routers.tickets import router as tickets_router

app = FastAPI(
    title="QueueLess Backend API",
    description="Authoritative API for QueueLess - Smart Healthcare Appointment & Queue Management",
    version="0.1.0",
)

# Configure Cross-Origin Resource Sharing (CORS) for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(hospitals_router, prefix="/api/hospitals", tags=["Hospitals"])
app.include_router(admin_router, prefix="/api/admin", tags=["Administration"])
app.include_router(tickets_router, prefix="/api", tags=["Queue & Tokens"])



@app.get("/", tags=["General"])
def root():
    """Application root endpoint providing metadata and status."""
    return {
        "app": "QueueLess API",
        "version": "0.1.0",
        "status": "online",
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
    }


@app.get("/api/health", tags=["Health"])
def health_check():
    """
    Health check endpoint that verifies server and MySQL database connectivity.
    Does not expose sensitive connection parameters.
    """
    db_connected = test_connection()
    return {
        "status": "healthy" if db_connected else "degraded",
        "database_connected": db_connected,
        "database_type": "MySQL 8.0",
    }
