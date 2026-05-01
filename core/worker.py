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
    # Security: prevent deserialization attacks via pickle
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=100,  # Recycle workers to prevent memory leaks
)

@celery_app.task(name="optimize_task", bind=True, max_retries=2)
def optimize_task(self, code: str, user_id: int):
    """
    Background worker task for heavy code optimization.
    Uses a fresh event loop per task to avoid collisions with Celery's internals.
    """
    logger.info(f"Starting optimization task for user {user_id}")
    
    # Always create a fresh event loop for Celery tasks.
    # Celery workers may reuse threads, so the previous loop may be closed.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    db = None
    try:
        engine = AletheiaEngine(api_key=GEMINI_API_KEY)
        result_json = loop.run_until_complete(engine.dispatch_optimization(code))
        
        # Persist success to DB
        db = SessionLocal()
        log = AuditLog(
            user_id=user_id,
            action_type="OPTIMIZE_BACKGROUND",
            target_data=code[:200] + "..." if len(code) > 200 else code,
            result_status="SUCCESS"
        )
        db.add(log)
        db.commit()
        
        return result_json

    except Exception as e:
        logger.error(f"Worker Task Failure: {e}")
        try:
            db = SessionLocal()
            log = AuditLog(
                user_id=user_id,
                action_type="OPTIMIZE_BACKGROUND",
                target_data=code[:200] + "..." if len(code) > 200 else code,
                result_status="FAILED"
            )
            db.add(log)
            db.commit()
        except Exception as db_err:
            logger.error(f"Failed to log audit entry: {db_err}")
        raise e

    finally:
        # Always close DB session and event loop to prevent resource leaks
        if db is not None:
            db.close()
        loop.close()
