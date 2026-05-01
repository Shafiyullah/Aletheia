import os
import json
import logging
import secrets
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import contextlib

from core.database import engine, Base, get_db
from core.models import User, AuditLog, VulnerabilityFinding
from core.auth import verify_password, get_password_hash, create_access_token
from core.engine import AletheiaEngine
from core.config import GEMINI_API_KEY, ALLOWED_ORIGINS
from core.safety import SecurityViolationException, validate_llm_output
from core.worker import optimize_task, celery_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aletheia.api")

# Construct the DB tables
Base.metadata.create_all(bind=engine)

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    db = next(get_db())
    try:
        admin_user = db.query(User).filter(User.username == "enterprise_admin").first()
        if not admin_user:
            admin_password = os.environ.get("ADMIN_PASSWORD")
            if not admin_password:
                if os.environ.get("ENV", "").upper() == "PROD":
                    raise ValueError(
                        "CRITICAL: ADMIN_PASSWORD is not set in a production environment."
                    )
                # Non-production: generate a random password and log it once.
                admin_password = secrets.token_urlsafe(20)
                logger.warning(
                    "ADMIN_PASSWORD not set. Generated ephemeral admin password: %s  "
                    "(Set ADMIN_PASSWORD env var for persistent credentials)",
                    admin_password,
                )

            hashed_pw = get_password_hash(admin_password)
        admin_user = User(
            username="enterprise_admin",
            email="admin@aletheia.local",
            hashed_password=hashed_pw,
            is_superuser=True
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()
    yield

app = FastAPI(
    title="Aletheia Production API",
    description="Enterprise-grade decoupled backend for Neuro-Symbolic Code Verification & Diagnostics.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — Restricted to configured origins (defaults to http://localhost:8501)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ─── SCHEMAS ────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str

class OptimizationRequest(BaseModel):
    code: str = Field(..., max_length=50_000)  # Bounded input size

class OptResponse(BaseModel):
    method: str
    code: str

class AuditRequest(BaseModel):
    claims: List[str] = Field(..., max_items=20)  # Bounded claim count
    context: str = Field(..., max_length=50_000)

# DEPENDENCIES

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    from core.auth import jwt, JWTError, SECRET_KEY, ALGORITHM
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# AUTHENTICATION ROUTES

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


# EXECUTION ROUTES

@app.post("/api/v1/optimize")
async def optimize_code(
    request: OptimizationRequest, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits code for optimization via Celery Worker.
    Returns a task_id immediately.
    """
    # Pre-check for safety before queueing (to avoid malicious workers)
    from core.safety import static_analysis_check
    try:
        static_analysis_check(request.code)
    except SecurityViolationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    # Offload to worker
    task = optimize_task.delay(request.code, current_user.id)
    
    return {"task_id": task.id, "status": "PENDING"}

@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    """
    Query the status of an asynchronous background task.
    """
    from celery.result import AsyncResult
    res = AsyncResult(task_id, app=celery_app)
    
    if res.ready():
        if res.successful():
            return {"status": "SUCCESS", "result": res.result}
        else:
            return {"status": "FAILED", "error": str(res.result)}
    
    return {"status": "IN_PROGRESS"}

class AuditRequest(BaseModel):
    claims: List[str]
    context: str

@app.post("/api/v1/audit")
async def audit_claims(
    request: AuditRequest, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from core.veritas import VeritasAuditor
    auditor = VeritasAuditor(api_key=GEMINI_API_KEY)
    results = []
    
    # Run the audits
    for claim in request.claims:
        res = auditor.span_level_verification(claim, request.context)
        results.append({"claim": claim, "support": res})
        
    # Persist the action securely
    log = AuditLog(
        user_id=current_user.id,
        action_type="VERITAS_AUDIT",
        target_data=f"Audited {len(request.claims)} claims",
        result_status="SUCCESS"
    )
    db.add(log)
    db.commit()
    
    return {"results": results}
