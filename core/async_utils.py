import asyncio
import logging
import concurrent.futures
from typing import Callable, Any, List, Coroutine
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')

class AsyncJobManager:
    """
    Manages heavy CPU and I/O tasks to keep the main event loop responsive.
    """
    def __init__(self, max_io_concurrency: int = 10, max_cpu_workers: int = None):
        """
        :param max_io_concurrency: Max concurrent async I/O tasks (e.g., API calls).
        :param max_cpu_workers: Max CPU workers (defaults to os.cpu_count()).
        """
        self.io_semaphore = asyncio.Semaphore(max_io_concurrency)
        self.cpu_executor = concurrent.futures.ProcessPoolExecutor(max_workers=max_cpu_workers)

    async def run_cpu_job(self, func: Callable, *args) -> Any:
        """
        Runs a CPU-bound blocking function in a separate process.
        This prevents the asyncio event loop from freezing.
        """
        loop = asyncio.get_running_loop()
        try:
            # Run in ProcessPool to bypass GIL for true parallelism
            return await loop.run_in_executor(self.cpu_executor, func, *args)
        except Exception as e:
            logging.error(f"CPU Job Failed: {e}")
            raise e

    async def run_io_job(self, coroutine: Coroutine) -> Any:
        """
        Runs a single I/O-bound coroutine with rate limiting.
        """
        async with self.io_semaphore:
            try:
                return await coroutine
            except Exception as e:
                logging.error(f"I/O Job Failed: {e}")
                raise e

    async def run_batched_io_jobs(self, coroutines: List[Coroutine]) -> List[Any]:
        """
        Runs a list of coroutines concurrently, respecting the rate limit.
        Uses asyncio.gather for efficiency.
        """
        # Wrap each coroutine with the semaphore logic
        tasks = [self.run_io_job(coro) for coro in coroutines]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def shutdown(self):
        """Clean up resources."""
        self.cpu_executor.shutdown(wait=True)

# Global Instance
async_manager = AsyncJobManager()

# --- Retry Logic Decorators ---

def retry_api_call():
    """
    Decorator for API calls using exponential backoff.
    Retries on typical transient errors.
    """
    def is_retryable(exception):
        """Do not retry on coding errors, only on API/network errors."""
        non_retryable = (SyntaxError, KeyError, AttributeError, TypeError, NameError, ValueError, ImportError)
        return not isinstance(exception, non_retryable)

    return retry(
        stop=stop_after_attempt(3), # Reduced from 10 so we don't hang if it's genuinely failing
        wait=wait_exponential(multiplier=1, min=2, max=10), # Reduced max wait
        retry=retry_if_exception(is_retryable),
        reraise=True
    )
