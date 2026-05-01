import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from core.database import Base

def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    audits = relationship("AuditLog", back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # e.g., 'OPTIMIZE', 'AUDIT'
    target_data = Column(Text, nullable=False)        # Context/code or GitHub URL that was audited
    result_status = Column(String(20), nullable=False) # e.g., 'SUCCESS', 'BLOCKED'
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="audits")
    findings = relationship("VulnerabilityFinding", back_populates="audit")


class VulnerabilityFinding(Base):
    __tablename__ = "vulnerability_findings"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audit_logs.id"), nullable=False)
    severity = Column(String(20), nullable=False)      # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    description = Column(Text, nullable=False)
    detector = Column(String(50), nullable=False)      # 'AST', 'Bandit', 'Shannon', 'AI_Sentinel'
    created_at = Column(DateTime, default=_utcnow)

    audit = relationship("AuditLog", back_populates="findings")
