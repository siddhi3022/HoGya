from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal
from .routers import auth as auth_router, inventory
from . import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database tables on startup
    Base.metadata.create_all(bind=engine)
    # Idempotently bootstrap the primary admin account
    db = SessionLocal()
    try:
        auth.init_admin_user(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Inventory Microservice",
    description="Dedicated microservice managing product catalog, stock counts, and stock reservations.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User registration, JWT login, and profile inspection."
        },
        {
            "name": "Admin User Management",
            "description": "Admin-only user list inspection and account deletion."
        },
        {
            "name": "Inventory",
            "description": "Product catalog CRUD and stock reservation endpoints."
        }
    ]
)

from .rate_limiter import RateLimitMiddleware

# Add Rate Limiting Middleware (Strict 5 requests per 60s per client)
app.add_middleware(RateLimitMiddleware)

# Enable CORS for cross-origin testing if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

# Include routers
app.include_router(auth_router.router)
app.include_router(inventory.router)


@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint for Inventory Service."""
    return {
        "service": "Inventory Service",
        "status": "healthy",
        "port": 8002,
        "docs_url": "/docs"
    }
