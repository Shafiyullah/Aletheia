import os
import datetime
import secrets
import logging
from passlib.context import CryptContext
from typing import Optional

try:
    from jose import JWTError, jwt
except ImportError:
    import jwt
    from jwt.exceptions import InvalidTokenError as JWTError

logger = logging.getLogger("aletheia.auth")

# Enterprise security parameters
# JWT_SECRET MUST be set in production via environment variable.
SECRET_KEY = os.environ.get("ALETHEIA_SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("ENV", "").upper() == "PROD":
        raise ValueError(
            "CRITICAL: ALETHEIA_SECRET_KEY is not set in a production environment. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    # In non-production, generate a random ephemeral key per process.
    # This means tokens are invalidated on restart — acceptable for dev/CI.
    SECRET_KEY = secrets.token_urlsafe(64)
    logger.warning(
        "ALETHEIA_SECRET_KEY not set. Using ephemeral random key. "
        "Tokens will NOT survive restarts. Set a persistent key for staging/production."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Bcrypt handles strong password hashing uniformly
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
