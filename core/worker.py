import os
import asyncio
from celery import Celery
import logging
from core.engine import AletheiaEngine
from core.database import SessionLocal
from core.models import AuditLog, VulnerabilityFinding
from core.config import GEMINI_API_KEY

# Set up logging
logger = logging.getLogger("aletheia.worker")

# Initialize Celery
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("aletheia_tasks", broker=REDIS_URL, backend=REDIS_URL)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="optimize_task")
def optimize_task(code: str, user_id: int):
    """
    Background worker task for heavy code optimization.
    """
    logger.info(f"Starting optimization task for user {user_id}")
    
    # We must run the async dispatch in a sync wrapper for Celery
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        engine = AletheiaEngine(api_key=GEMINI_API_KEY)
        result_json = loop.run_until_complete(engine.dispatch_optimization(code))
        
        # Persist success to DB
        db = SessionLocal()
        log = AuditLog(
            user_id=user_id,
            action_type="OPTIMIZE_BACKGROUND",
            target_data=code[:200] + "...",
            result_status="SUCCESS"
        )
        db.add(log)
        db.commit()
        db.close()
        
        return result_json

    except Exception as e:
        logger.error(f"Worker Task Failure: {e}")
        db = SessionLocal()
        log = AuditLog(
            user_id=user_id,
            action_type="OPTIMIZE_BACKGROUND",
            target_data=code[:200] + "...",
            result_status="FAILED"
        )
        db.add(log)
        db.commit()
        db.close()
        raise e
