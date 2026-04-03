import time
import random
import logging
import functools

logger = logging.getLogger(__name__)

def retry_with_backoff(retries=3, backoff_in_seconds=1):
    """
    Decorator to retry a function with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if x == retries:
                        logger.error(f"Failed after {retries} retries: {e}")
                        raise
                    
                    sleep = (backoff_in_seconds * 2 ** x) + random.uniform(0, 1)
                    logger.warning(f"Error {e}. Retrying in {sleep:.2f} seconds...")
                    time.sleep(sleep)
                    x += 1
        return wrapper
    return decorator

import re

def extract_code(text: str) -> str:
    """
    Safely extracts code from a markdown-formatted LLM response.
    Handles multiple languages, bare code blocks, and lack of markdown.
    """
    if not text:
        return ""
        
    # Regex to capture content inside ```language ... ``` or ``` ... ```
    match = re.search(r'```[a-zA-Z]*\n(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Check if there's an unclosed code block at the end of the text
    match_unclosed = re.search(r'```[a-zA-Z]*\n(.*)', text, re.DOTALL)
    if match_unclosed:
        return match_unclosed.group(1).strip()

    # If no markdown blocks, return text as is (strip leading/trailing space)
    return text.strip()
