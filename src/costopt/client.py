import time
import uuid
import logging
from typing import Any, Dict, List, Optional
from openai.types.chat import ChatCompletion

from costopt.cache import SQLiteCache
from costopt.router import CostOptRouter
from costopt.pricing import calculate_cost
from costopt.telemetry import SQLiteTelemetryLogger

logger = logging.getLogger("costopt.client")

class CostOptCompletions:
    def __init__(self, original_completions: Any, wrapper: "CostOpt"):
        self._original = original_completions
        self._wrapper = wrapper

    def create(self, *args, **kwargs) -> ChatCompletion:
        start_time = time.time()
        
        # 1. Extract request parameters
        model_requested = kwargs.get("model", "")
        messages = kwargs.get("messages", [])
        
        # Extract environment and application metadata from kwargs (or fall back to configuration defaults)
        environment = kwargs.pop("environment", self._wrapper.environment)
        application = kwargs.pop("application", self._wrapper.application)
        region = kwargs.pop("region", self._wrapper.region)

        # Concatenate message contents for prompt hash and analysis
        prompt_parts = []
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
            else:
                content = getattr(msg, "content", "")
            if content:
                prompt_parts.append(str(content))
        prompt_text = "\n".join(prompt_parts)
        prompt_hash = hashlib_helper(prompt_text)

        # 2. Check Cache
        cached_data = self._wrapper.cache.get(prompt_text, model_requested)
        if cached_data:
            latency_ms = int((time.time() - start_time) * 1000)
            
            try:
                # Reconstruct OpenAI Pydantic model
                chat_completion = ChatCompletion.model_validate(cached_data)
                
                # Calculate cost savings
                # For cache hit, cost_original is what they would pay for model_requested with full input tokens.
                # cost_actual is 0.0 or the cached input rate.
                input_tokens = chat_completion.usage.prompt_tokens if chat_completion.usage else 0
                output_tokens = chat_completion.usage.completion_tokens if chat_completion.usage else 0
                
                cost_original = calculate_cost(self._wrapper.provider, model_requested, input_tokens, output_tokens, cache_hit=False)
                cost_actual = calculate_cost(self._wrapper.provider, model_requested, input_tokens, output_tokens, cache_hit=True)
                savings = max(0.0, round(cost_original - cost_actual, 6))

                # Log async telemetry
                self._wrapper.telemetry.log({
                    "request_id": chat_completion.id,
                    "provider": self._wrapper.provider,
                    "model_requested": model_requested,
                    "model_used": model_requested,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                    "status_code": 200,
                    "success": True,
                    "error_type": None,
                    "cache_hit": True,
                    "cost_original": cost_original,
                    "cost_actual": cost_actual,
                    "savings": savings,
                    "prompt_hash": prompt_hash,
                    "environment": environment,
                    "application": application,
                    "region": region,
                    "retry_count": 0
                })
                return chat_completion
            except Exception as e:
                logger.error(f"Error parsing cached response into OpenAI object: {e}. Falling back to API query.")

        # 3. Check Routing Reroute
        model_used = self._wrapper.router.match_route(prompt_text, model_requested)
        kwargs["model"] = model_used

        # 4. API Call execution with fallback retry logic
        response = None
        status_code = 200
        error_type = None
        success = True
        retry_count = 0
        last_exception = None

        try:
            response = self._original.create(*args, **kwargs)
        except Exception as e:
            last_exception = e
            # Try to run model fallbacks
            fallbacks = self._wrapper.router.get_fallbacks(model_used)
            for fallback_model in fallbacks:
                retry_count += 1
                logger.warning(f"CostOpt: Call to {model_used} failed. Retrying fallback {fallback_model} (attempt {retry_count})...")
                try:
                    kwargs["model"] = fallback_model
                    response = self._original.create(*args, **kwargs)
                    model_used = fallback_model
                    success = True
                    last_exception = None
                    break
                except Exception as fe:
                    last_exception = fe
                    continue

            if response is None:
                success = False
                status_code = getattr(last_exception, "status_code", 500)
                error_type = type(last_exception).__name__

        latency_ms = int((time.time() - start_time) * 1000)

        # 5. Extract values and compute costs
        if success and response:
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            
            # Save successful response to cache
            try:
                self._wrapper.cache.set(prompt_text, model_requested, response.model_dump())
            except Exception as ce:
                logger.error(f"Failed to cache response: {ce}")
            
            # Cost calculations
            cost_original = calculate_cost(self._wrapper.provider, model_requested, input_tokens, output_tokens, cache_hit=False)
            cost_actual = calculate_cost(self._wrapper.provider, model_used, input_tokens, output_tokens, cache_hit=False)
            savings = max(0.0, round(cost_original - cost_actual, 6))
            req_id = response.id
        else:
            # Failure state tracking
            input_tokens = 0
            output_tokens = 0
            cost_original = 0.0
            cost_actual = 0.0
            savings = 0.0
            req_id = str(uuid.uuid4())

        # Log async telemetry
        self._wrapper.telemetry.log({
            "request_id": req_id,
            "provider": self._wrapper.provider,
            "model_requested": model_requested,
            "model_used": model_used,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "status_code": status_code,
            "success": success,
            "error_type": error_type,
            "cache_hit": False,
            "cost_original": cost_original,
            "cost_actual": cost_actual,
            "savings": savings,
            "prompt_hash": prompt_hash,
            "environment": environment,
            "application": application,
            "region": region,
            "retry_count": retry_count
        })

        if not success and last_exception:
            raise last_exception

        return response


class CostOptChat:
    def __init__(self, original_chat: Any, wrapper: "CostOpt"):
        self._original = original_chat
        self.completions = CostOptCompletions(self._original.completions, wrapper)

    def __getattr__(self, name):
        return getattr(self._original, name)


class CostOpt:
    def __init__(
        self,
        client: Any,
        provider: str = "openai",
        config_path: str = "costopt.yaml",
        cache_db_path: str = "costopt_cache.db",
        telemetry_db_path: str = "costopt_telemetry.db",
        similarity_threshold: float = 1.0,
        environment: str = "production",
        application: str = "default-app",
        region: str = "us-east-1"
    ):
        """
        LLM CostOpt Interceptor client wrapper.
        """
        self._client = client
        self.provider = provider.lower()
        self.environment = environment
        self.application = application
        self.region = region

        # Initialize engine sub-modules
        self.router = CostOptRouter(config_path)
        self.cache = SQLiteCache(cache_db_path, similarity_threshold)
        self.telemetry = SQLiteTelemetryLogger(telemetry_db_path)

        # Wrap chat endpoint
        if hasattr(self._client, "chat"):
            self.chat = CostOptChat(self._client.chat, self)
        else:
            logger.warning("Wrapped client does not possess 'chat' attribute. Autowrap may only partial capture.")

    def __getattr__(self, name):
        """Delegate all other SDK method accesses (e.g. models, files, assistants) directly to the wrapped client."""
        return getattr(self._client, name)

    def shutdown(self):
        """Gracefully closes telemetry background logger workers."""
        self.telemetry.shutdown()


def hashlib_helper(text: str) -> str:
    """Helper MD5 hasher."""
    import hashlib
    return hashlib.md5(text.encode("utf-8")).hexdigest()
