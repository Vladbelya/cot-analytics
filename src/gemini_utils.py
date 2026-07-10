import time
import random
import os
import logging
from typing import List, Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def get_fallback_models(primary_model: str) -> List[str]:
    """
    Returns an ordered list of models to try, starting with the primary model,
    followed by alternative models to fallback to in case of transient failures.
    """
    models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"]
    
    ordered_models = [primary_model]
    for m in models:
        if m != primary_model:
            ordered_models.append(m)
            
    if primary_model not in models:
        return [primary_model] + models
        
    return ordered_models

def generate_content_with_retry(
    client: genai.Client,
    model: str,
    contents,
    config: Optional[types.GenerateContentConfig] = None,
    max_retries: int = 5,
    initial_backoff: float = 2.0
):
    """
    Calls client.models.generate_content with transient error retries,
    exponential backoff, jitter, and automatic model fallback.
    """
    models_to_try = get_fallback_models(model)
    current_backoff = initial_backoff
    last_exception = None
    
    for try_model in models_to_try:
        retries_for_model = 3 if try_model == model else 2
        
        for attempt in range(1, retries_for_model + 1):
            try:
                logger.info(f"Calling Gemini API (model: {try_model}, attempt {attempt}/{retries_for_model})")
                response = client.models.generate_content(
                    model=try_model,
                    contents=contents,
                    config=config
                )
                return response
            except Exception as e:
                last_exception = e
                err_msg = str(e).lower()
                
                # Assume retryable by default
                is_retryable = True
                
                # Explicitly exclude authentication or developer bad requests from retry logic
                non_retryable_keywords = [
                    "api_key_invalid", "invalid api key", "invalid_argument", "400", "bad request"
                ]
                if any(kw in err_msg for kw in non_retryable_keywords):
                    is_retryable = False
                
                if not is_retryable:
                    logger.error(f"Non-retryable error encountered: {e}")
                    raise e
                
                if try_model == models_to_try[-1] and attempt == retries_for_model:
                    break
                    
                sleep_time = current_backoff + random.uniform(0.1, 1.0)
                logger.warning(
                    f"Gemini API call failed with retryable error: {e}. "
                    f"Retrying in {sleep_time:.2f} seconds..."
                )
                time.sleep(sleep_time)
                current_backoff *= 2.0
                
        current_backoff = initial_backoff
        logger.warning(f"Failed all attempts with model {try_model}. Falling back to next available model...")
        
    logger.error("All attempts to call Gemini with primary and fallback models failed.")
    raise last_exception
