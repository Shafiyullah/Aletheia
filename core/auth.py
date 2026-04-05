import os
import datetime
from passlib.context import CryptContext
from typing import Optional

try:
    from jose import JWTError, jwt
except ImportError:
    # We installed pyjwt, fallback import
    import jwt
    from jwt.exceptions import InvalidTokenError as JWTError

# Enterprise security parameters
# JWT_SECRET MUST be set in production
SECRET_KEY = os.environ.get("ALETHEIA_SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("ENV") == "PROD":
        raise ValueError("Critical Security Error: ALETHEIA_SECRET_KEY not found in production environment.")
    SECRET_KEY = "dev-secret-only" # Safe default for local/CI tests
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
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
