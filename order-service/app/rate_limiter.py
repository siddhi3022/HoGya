import re
import time
import threading
from typing import Dict, Tuple, Optional
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Centralized configuration with defaults: 5 requests per 60 seconds
RATE_LIMIT_REQUESTS = 5
RATE_LIMIT_WINDOW_SECONDS = 60
AUTH_RATE_LIMIT_REQUESTS = 5
AUTH_RATE_LIMIT_WINDOW_SECONDS = 60

INTERNAL_SERVICE_TOKEN = "microservices-internal-secret-token-2026"
JWT_SECRET_KEY = "microservices-shared-secret-key-at-least-32-bytes-long!"
JWT_ALGORITHM = "HS256"


class InMemoryRateLimiter:
    """
    Thread-safe in-memory fixed-window rate limiter.
    Stores (window_start_time, request_count) per client bucket key.
    Easily replaceable with Redis in multi-instance production deployments.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # Storage format: {bucket_key: (window_start_time, count)}
        self._records: Dict[str, Tuple[float, int]] = {}

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Check if the request is permitted under the strict request-count + cooldown rule.

        Returns:
            (is_allowed: bool, retry_after_seconds: int)
        """
        now = time.time()
        with self._lock:
            if key not in self._records:
                # First request starts the fixed window
                self._records[key] = (now, 1)
                return True, 0

            window_start, count = self._records[key]
            elapsed = now - window_start

            if elapsed >= window_seconds:
                # 60-second window has expired -> reset window
                self._records[key] = (now, 1)
                return True, 0

            # Inside the active window
            if count < max_requests:
                self._records[key] = (window_start, count + 1)
                return True, 0

            # Exceeded max requests -> calculate remaining cooldown
            retry_after = max(1, int(round(window_seconds - elapsed)))
            return False, retry_after

    def reset(self, key: Optional[str] = None):
        """Reset counter for a specific key or all keys."""
        with self._lock:
            if key:
                self._records.pop(key, None)
            else:
                self._records.clear()


# Global limiter singleton
limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette Middleware enforcing:
    - 5 requests per 60 seconds per client per endpoint.
    - Fixed 60-second window with automatic reset after cooldown.
    - Excludes internal service communication using X-Internal-Service-Token.
    - Uses JWT user identity for authenticated clients and IP for anonymous clients.
    - Returns HTTP 429 with Retry-After header and standard detail message.
    """
    async def dispatch(self, request: Request, call_next):
        # 1. Skip pre-flight CORS OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # 2. Skip rate limiting for static docs, health check, and schema definitions
        if path in ["/", "/docs", "/openapi.json", "/redoc", "/favicon.ico"]:
            return await call_next(request)

        # 3. Exclude trusted internal service-to-service calls
        internal_token = request.headers.get("X-Internal-Service-Token")
        if internal_token and internal_token == INTERNAL_SERVICE_TOKEN:
            return await call_next(request)

        # 4. Determine client identity (authenticated user or client IP)
        client_key = self._get_client_identifier(request)

        # 5. Normalize endpoint path (e.g. /orders/12 -> /orders/{id})
        normalized_path = re.sub(r"/\d+", "/{id}", path).rstrip("/")
        if not normalized_path:
            normalized_path = "/"

        # 6. Choose rate limit parameters based on route
        if normalized_path in ["/auth/login", "/auth/register"]:
            max_requests = AUTH_RATE_LIMIT_REQUESTS
            window_seconds = AUTH_RATE_LIMIT_WINDOW_SECONDS
            bucket_key = f"auth:{request.method}:{normalized_path}:{client_key}"
        else:
            max_requests = RATE_LIMIT_REQUESTS
            window_seconds = RATE_LIMIT_WINDOW_SECONDS
            bucket_key = f"api:{request.method}:{normalized_path}:{client_key}"

        # 7. Check with limiter
        allowed, retry_after = limiter.is_allowed(bucket_key, max_requests, window_seconds)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please wait 60 seconds before trying again."
                },
                headers={
                    "Retry-After": str(retry_after)
                }
            )

        return await call_next(request)

    def _get_client_identifier(self, request: Request) -> str:
        """Extract user_id from valid Bearer JWT, or fallback to client IP."""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                # Cryptographically verify JWT using secret key
                payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
                user_id = payload.get("user_id") or payload.get("sub")
                if user_id:
                    return f"user:{user_id}"
            except Exception:
                pass

        # Fallback to client IP
        client_ip = request.client.host if request.client else "unknown_client"
        # Check X-Forwarded-For if behind a reverse proxy
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        return f"ip:{client_ip}"
