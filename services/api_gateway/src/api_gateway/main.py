"""API Gateway FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ai_trading_shared.config import Settings, get_settings
from ai_trading_shared.domain.enums import Role
from ai_trading_shared.security import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    role_at_least,
    verify_password,
)
from ai_trading_shared.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)
ACCESS_COOKIE = "aether_access"
REFRESH_COOKIE = "aether_refresh"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)
limiter = Limiter(key_func=get_remote_address)


class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: Role


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
    execution_mode: str
    live_trading_enabled: bool


class _UserStore:
    """In-memory user store for bootstrap; swap for SQLAlchemy in production."""

    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        admin_id = uuid4()
        self.users["admin@local.dev"] = {
            "id": admin_id,
            "email": "admin@local.dev",
            "full_name": "Platform Admin",
            "role": Role.ADMIN,
            "hashed_password": hash_password("ChangeMeAdmin123!"),
            "is_active": True,
        }

    def create(self, email: str, password: str, full_name: str, role: Role = Role.VIEWER) -> dict:
        if email in self.users:
            raise ValueError("Email already registered")
        user = {
            "id": uuid4(),
            "email": email,
            "full_name": full_name,
            "role": role,
            "hashed_password": hash_password(password),
            "is_active": True,
        }
        self.users[email] = user
        return user

    def authenticate(self, email: str, password: str) -> dict | None:
        user = self.users.get(email)
        if user is None or not user["is_active"]:
            return None
        if not verify_password(password, user["hashed_password"]):
            return None
        return user

    def get_by_id(self, user_id: UUID) -> dict | None:
        for user in self.users.values():
            if user["id"] == user_id:
                return user
        return None


user_store = _UserStore()
_audit_log: list[dict[str, Any]] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    logger.info("api_gateway_started", env=settings.app_env)
    yield


app = FastAPI(title="AI Trading Platform API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _cookie_kwargs(settings: Settings, *, max_age: int) -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.is_production,
        "max_age": max_age,
        "path": "/",
    }


def _set_auth_cookies(
    response: Response,
    *,
    access: str,
    refresh: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        **_cookie_kwargs(settings, max_age=settings.jwt_access_token_expire_minutes * 60),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        **_cookie_kwargs(settings, max_age=settings.jwt_refresh_token_expire_days * 86400),
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


def _issue_tokens(user: dict, settings: Settings) -> tuple[str, str]:
    secret = settings.secret_key.get_secret_value()
    access = create_access_token(
        subject=str(user["id"]),
        role=user["role"],
        secret_key=secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_access_token_expire_minutes,
    )
    refresh = create_refresh_token(
        subject=str(user["id"]),
        secret_key=secret,
        algorithm=settings.jwt_algorithm,
        expires_days=settings.jwt_refresh_token_expire_days,
    )
    return access, refresh


def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    bearer: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> dict:
    token = bearer or request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        raw = decode_token(token, settings.secret_key.get_secret_value(), settings.jwt_algorithm)
        if raw.get("type") != "access":
            raise ValueError("Not an access token")
        payload = TokenPayload(raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = user_store.get_by_id(payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(required: Role):
    def _dep(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if not role_at_least(user["role"], required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _dep


def audit(action: str, actor: dict | None, details: dict | None = None, request: Request | None = None) -> None:
    _audit_log.append(
        {
            "action": action,
            "actor_id": str(actor["id"]) if actor else None,
            "details": details or {},
            "ip": request.client.host if request and request.client else None,
            "at": datetime.utcnow().isoformat(),
        }
    )


@app.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="api_gateway",
        timestamp=datetime.utcnow(),
        execution_mode=settings.execution_mode,
        live_trading_enabled=settings.enable_live_trading,
    )


@app.post("/v1/auth/register", response_model=UserPublic, status_code=201)
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterRequest) -> UserPublic:
    try:
        user = user_store.create(body.email, body.password, body.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit("user.register", user, request=request)
    return UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"], role=user["role"]
    )


@app.post("/v1/auth/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = user_store.authenticate(form.username, form.password)
    if user is None:
        audit("auth.login_failed", None, {"email": form.username}, request)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access, refresh = _issue_tokens(user, settings)
    audit("auth.login", user, request=request)
    return TokenResponse(access_token=access, refresh_token=refresh)


@app.post("/v1/auth/session/login", response_model=UserPublic)
@limiter.limit("20/minute")
async def session_login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JSONResponse:
    """Browser login — sets HttpOnly cookies (preferred for the dashboard)."""
    user = user_store.authenticate(form.username, form.password)
    if user is None:
        audit("auth.session_login_failed", None, {"email": form.username}, request)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access, refresh = _issue_tokens(user, settings)
    audit("auth.session_login", user, request=request)
    body = UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"], role=user["role"]
    )
    response = JSONResponse(content=body.model_dump(mode="json"))
    _set_auth_cookies(response, access=access, refresh=refresh, settings=settings)
    return response


@app.post("/v1/auth/session/logout")
async def session_logout(request: Request) -> JSONResponse:
    audit("auth.session_logout", None, request=request)
    response = JSONResponse(content={"ok": True})
    _clear_auth_cookies(response)
    return response


@app.post("/v1/auth/session/refresh", response_model=UserPublic)
async def session_refresh(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> JSONResponse:
    refresh = request.cookies.get(REFRESH_COOKIE)
    if not refresh:
        raise HTTPException(status_code=401, detail="Missing refresh cookie")
    try:
        raw = decode_token(
            refresh,
            settings.secret_key.get_secret_value(),
            settings.jwt_algorithm,
        )
        if raw.get("type") != "refresh":
            raise ValueError("Not a refresh token")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = user_store.get_by_id(UUID(str(raw["sub"])))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    access, new_refresh = _issue_tokens(user, settings)
    body = UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"], role=user["role"]
    )
    response = JSONResponse(content=body.model_dump(mode="json"))
    _set_auth_cookies(response, access=access, refresh=new_refresh, settings=settings)
    return response


@app.post("/v1/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        raw = decode_token(
            body.refresh_token,
            settings.secret_key.get_secret_value(),
            settings.jwt_algorithm,
        )
        if raw.get("type") != "refresh":
            raise ValueError("Not a refresh token")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = user_store.get_by_id(UUID(str(raw["sub"])))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    access, refresh = _issue_tokens(user, settings)
    return TokenResponse(access_token=access, refresh_token=refresh)


@app.get("/v1/me", response_model=UserPublic)
async def me(user: Annotated[dict, Depends(get_current_user)]) -> UserPublic:
    return UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"], role=user["role"]
    )


@app.get("/v1/audit")
async def list_audit(
    user: Annotated[dict, Depends(require_role(Role.ADMIN))],
) -> list[dict]:
    return list(reversed(_audit_log[-200:]))


@app.get("/v1/platform/status")
async def platform_status(
    user: Annotated[dict, Depends(require_role(Role.VIEWER))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return {
        "execution_mode": settings.execution_mode,
        "live_trading_enabled": settings.enable_live_trading,
        "use_mock_news": settings.use_mock_news,
        "use_mock_llm": settings.use_mock_llm,
        "risk": {
            "max_position_pct": settings.risk_max_position_pct,
            "daily_loss_limit_pct": settings.risk_daily_loss_limit_pct,
            "max_drawdown_pct": settings.risk_max_drawdown_pct,
        },
    }


async def _proxy_portfolio(
    method: str,
    path: str,
    *,
    settings: Settings,
    params: dict | None = None,
    json_body: dict | None = None,
    timeout: float = 30.0,
) -> Any:
    import httpx

    url = f"{settings.portfolio_service_url.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, params=params, json=json_body)
    except httpx.RequestError as exc:
        logger.exception("portfolio_proxy_unreachable", url=url)
        raise HTTPException(status_code=503, detail=f"Portfolio service unavailable: {exc}") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    if not response.content:
        return {}
    return response.json()


@app.get("/v1/portfolio/broker")
async def proxy_portfolio_broker(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.VIEWER))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Any:
    audit("portfolio.broker", user, request=request)
    return await _proxy_portfolio("GET", "/v1/portfolio/broker", settings=settings)


@app.post("/v1/portfolio/broker/connect")
async def proxy_portfolio_broker_connect(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.TRADER))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Any:
    body = await request.json()
    audit("portfolio.broker_connect", user, {"paper": body.get("paper", True)}, request)
    return await _proxy_portfolio(
        "POST", "/v1/portfolio/broker/connect", settings=settings, json_body=body
    )


@app.post("/v1/portfolio/broker/disconnect")
async def proxy_portfolio_broker_disconnect(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.TRADER))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Any:
    audit("portfolio.broker_disconnect", user, request=request)
    return await _proxy_portfolio("POST", "/v1/portfolio/broker/disconnect", settings=settings)


@app.get("/v1/portfolio")
async def proxy_portfolio(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.VIEWER))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Any:
    audit("portfolio.read", user, request=request)
    return await _proxy_portfolio("GET", "/v1/portfolio", settings=settings)


@app.get("/v1/portfolio/history")
async def proxy_portfolio_history(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.VIEWER))],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = 50,
) -> Any:
    audit("portfolio.history", user, request=request)
    return await _proxy_portfolio(
        "GET", "/v1/portfolio/history", settings=settings, params={"limit": limit}
    )


@app.get("/v1/portfolio/recommendations")
async def proxy_portfolio_recommendations(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.VIEWER))],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = 8,
) -> Any:
    audit("portfolio.recommendations", user, request=request)
    return await _proxy_portfolio(
        "GET",
        "/v1/portfolio/recommendations",
        settings=settings,
        params={"limit": limit},
    )


@app.post("/v1/portfolio/run")
async def proxy_portfolio_run(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.TRADER))],
    settings: Annotated[Settings, Depends(get_settings)],
    tickers: str | None = None,
) -> Any:
    audit("portfolio.run", user, {"tickers": tickers}, request)
    params = {"tickers": tickers} if tickers else None
    return await _proxy_portfolio(
        "POST",
        "/v1/portfolio/run",
        settings=settings,
        params=params,
        timeout=60.0,
    )


@app.get("/v1/portfolio/blotter")
async def proxy_portfolio_blotter(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.VIEWER))],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = 80,
) -> Any:
    audit("portfolio.blotter", user, request=request)
    return await _proxy_portfolio(
        "GET",
        "/v1/portfolio/blotter",
        settings=settings,
        params={"limit": limit},
    )


@app.get("/v1/portfolio/journal")
async def proxy_portfolio_journal(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.VIEWER))],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = 50,
) -> Any:
    audit("portfolio.journal", user, request=request)
    return await _proxy_portfolio(
        "GET",
        "/v1/portfolio/journal",
        settings=settings,
        params={"limit": limit},
    )


@app.get("/v1/portfolio/autopilot")
async def proxy_autopilot_get(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.VIEWER))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Any:
    audit("portfolio.autopilot.get", user, request=request)
    return await _proxy_portfolio("GET", "/v1/portfolio/autopilot", settings=settings)


@app.post("/v1/portfolio/autopilot")
async def proxy_autopilot_update(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.TRADER))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Any:
    body = await request.json()
    audit("portfolio.autopilot.update", user, body, request)
    return await _proxy_portfolio(
        "POST", "/v1/portfolio/autopilot", settings=settings, json_body=body
    )


@app.post("/v1/portfolio/autopilot/start")
async def proxy_autopilot_start(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.TRADER))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Any:
    audit("portfolio.autopilot.start", user, request=request)
    return await _proxy_portfolio("POST", "/v1/portfolio/autopilot/start", settings=settings)


@app.post("/v1/portfolio/autopilot/stop")
async def proxy_autopilot_stop(
    request: Request,
    user: Annotated[dict, Depends(require_role(Role.TRADER))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Any:
    audit("portfolio.autopilot.stop", user, request=request)
    return await _proxy_portfolio("POST", "/v1/portfolio/autopilot/stop", settings=settings)
