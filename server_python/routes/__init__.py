from .auth import router as auth_router

# Only include routers that actually exist
__all__ = ["auth_router"]
