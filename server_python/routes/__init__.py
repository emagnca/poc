from .auth import router as auth_router
from .selfsign import router as selfsign_router

# Only include routers that actually exist
__all__ = ["auth_router", "selfsign_router"]
