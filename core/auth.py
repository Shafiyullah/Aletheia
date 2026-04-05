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
SECRET_KEY = os.environ.get("ALETHEIA_SECRET_KEY", "b3c9f28a7d189e4c5b3648f5a2b19e26d9c87f3e1b7d5a5cf2b3e4f8d9b1a2c3") # Always overwrite in real PROD!
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
