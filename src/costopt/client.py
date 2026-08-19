import os
import inspect
import time
import uuid
import json
import hashlib
import logging
from typing import Any, Dict, List, Optional
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

from costopt.cache import SQLiteCache
from costopt.router import CostOptRouter
from costopt.pricing import calculate_cost
from costopt.telemetry import SQLiteTelemetryLogger
from costopt.circuit_breaker import CircuitBreaker

logger = logging.getLogger("costopt.client")

def _compute_prompt_hash(text: str) -> str:
    if not text:
        return ""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]

def _compute_params_hash(kwargs: dict) -> str:
    """Computes a deterministic hash of request parameters (temperature, tools, response_format, seed, max_tokens)."""
    relevant = {}
    for key in ("temperature", "tools", "tool_choice", "response_format", "seed", "max_tokens", "top_p"):
        if key in kwargs and kwargs[key] is not None:
            relevant[key] = kwargs[key]
    if not relevant:
        return ""
    try:
        raw = json.dumps(relevant, sort_keys=True, default=str)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    except Exception:
        return ""

def _get_caller_location() -> tuple:
    """Inspects stack frames to pinpoint user code file path and line number."""
    try:
        stack = inspect.stack()
        for frame_info in stack[2:]:
            filename = frame_info.filename
            if "costopt" not in filename and "site-packages" not in filename and "importlib" not in filename:
                return os.path.abspath(filename), frame_info.lineno
    except Exception:
        pass
    return "", 0

class CostOptCompletions:
    def __init__(self, original_completions: Any, wrapper: "CostOpt"):
        self._original = original_completions
        self._wrapper = wrapper

    def create(self, *args, **kwargs) -> Any:
        start_time = time.time()
        
        # 1. Extract request parameters
        model_requested = kwargs.get("model", "")
        messages = kwargs.get("messages", [])
        
        # Extract environment, feature / application metadata from kwargs
        environment = kwargs.pop("environment", self._wrapper.environment)
        feature_name = kwargs.pop("feature", None)
        application = feature_name if feature_name else kwargs.pop("application", self._wrapper.application)
        region = kwargs.pop("region", self._wrapper.region)

        # Automatic caller source location extraction
        caller_file, caller_line = _get_caller_location()
        file_path = kwargs.pop("file_path", caller_file)
        line_number = kwargs.pop("line_number", caller_line)

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
        prompt_hash = _compute_prompt_hash(prompt_text)
        params_hash = _compute_params_hash(kwargs)

        # 0. Circuit Breaker Check to prevent silent runaway billing loops
        location_key = f"{file_path}:{line_number}" if file_path else "<unknown_location>"
        self._wrapper.circuit_breaker.check_and_record(location_key)

        # Evaluate model routing first to get model_used
        model_used = self._wrapper.router.match_route(prompt_text, model_requested)

        # Handle streaming interception if stream=True
        if kwargs.get("stream"):
            return self._handle_stream(start_time, prompt_text, prompt_hash, params_hash, model_requested, model_used, environment, application, region, file_path, line_number, args, kwargs)

        # 2. Check Cache using model_used and params_hash (Fix Bug 1 & Bug 2)
        cached_data = self._wrapper.cache.get(prompt_text, model_used, params_hash)
        if cached_data:
            latency_ms = int((time.time() - start_time) * 1000)
            
            try:
                # Reconstruct OpenAI Pydantic model
                chat_completion = ChatCompletion.model_validate(cached_data)
                
                input_tokens = chat_completion.usage.prompt_tokens if chat_completion.usage else 0
                output_tokens = chat_completion.usage.completion_tokens if chat_completion.usage else 0
                
                cost_original = calculate_cost(self._wrapper.provider, model_requested, input_tokens, output_tokens, cache_hit=False)
                cost_actual = calculate_cost(self._wrapper.provider, model_used, input_tokens, output_tokens, cache_hit=True)
                savings = max(0.0, round(cost_original - cost_actual, 6))

                # Log async telemetry with UNIQUE request_id per cache hit (Fix Bug 6)
                self._wrapper.telemetry.log({
                    "request_id": f"cache_hit_{uuid.uuid4()}",
                    "provider": self._wrapper.provider,
                    "model_requested": model_requested,
                    "model_used": model_used,
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
                    "retry_count": 0,
                    "file_path": file_path,
                    "line_number": line_number
                })
                return chat_completion
            except Exception as e:
                logger.error(f"Error parsing cached response into OpenAI object: {e}. Falling back to API query.")

        # Set model in kwargs
        kwargs["model"] = model_used

        # 4. API Call execution with multi-provider fallback retry logic
        response = None
        status_code = 200
        error_type = None
        success = True
        retry_count = 0
        last_exception = None
        provider_used = self._wrapper.provider

        try:
            response = self._original.create(*args, **kwargs)
        except Exception as e:
            last_exception = e
            # Try to run model fallbacks
            fallbacks = self._wrapper.router.get_fallbacks(model_used)
            for fallback_entry in fallbacks:
                retry_count += 1
                # Support multi-provider syntax e.g. "anthropic/claude-3-5-sonnet"
                provider_target = self._wrapper.provider
                fallback_model = fallback_entry
                if "/" in fallback_entry:
                    provider_target, fallback_model = fallback_entry.split("/", 1)

                logger.warning(f"CostOpt: Call to {model_used} failed. Retrying fallback {fallback_model} on provider {provider_target} (attempt {retry_count})...")
                try:
                    kwargs["model"] = fallback_model
                    response = self._original.create(*args, **kwargs)
                    model_used = fallback_model
                    provider_used = provider_target
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
            
            # Save successful response to cache using model_used and params_hash (Fix Bug 1 & Bug 2)
            try:
                self._wrapper.cache.set(prompt_text, model_used, response.model_dump(), params_hash=params_hash)
            except Exception as ce:
                logger.error(f"Failed to cache response: {ce}")
            
            # Cost calculations using provider_used (Fix Bug 3)
            cost_original = calculate_cost(self._wrapper.provider, model_requested, input_tokens, output_tokens, cache_hit=False)
            cost_actual = calculate_cost(provider_used, model_used, input_tokens, output_tokens, cache_hit=False)
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
            "provider": provider_used,
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
            "retry_count": retry_count,
            "file_path": file_path,
            "line_number": line_number
        })

        if not success and last_exception:
            raise last_exception

        return response

    def _handle_stream(self, start_time, prompt_text, prompt_hash, params_hash, model_requested, model_used, environment, application, region, file_path, line_number, args, kwargs):
        """Generates stream chunks while recording telemetry when stream finishes."""
        kwargs["model"] = model_used

        # 1. Check cache first using model_used and params_hash (Fix Bug 1 & Bug 2)
        cached_data = self._wrapper.cache.get(prompt_text, model_used, params_hash)
        if cached_data and "_stream_chunks" in cached_data:
            latency_ms = int((time.time() - start_time) * 1000)
            for raw_chunk in cached_data["_stream_chunks"]:
                try:
                    yield ChatCompletionChunk.model_validate(raw_chunk)
                except Exception:
                    pass
            self._wrapper.telemetry.log({
                "request_id": f"cache_hit_{uuid.uuid4()}",
                "provider": self._wrapper.provider,
                "model_requested": model_requested,
                "model_used": model_used,
                "input_tokens": cached_data.get("_input_tokens", 0),
                "output_tokens": cached_data.get("_output_tokens", 0),
                "latency_ms": latency_ms,
                "status_code": 200,
                "success": True,
                "error_type": None,
                "cache_hit": True,
                "cost_original": cached_data.get("_cost_original", 0.0),
                "cost_actual": 0.0,
                "savings": cached_data.get("_cost_original", 0.0),
                "prompt_hash": prompt_hash,
                "environment": environment,
                "application": application,
                "region": region,
                "retry_count": 0,
                "file_path": file_path,
                "line_number": line_number
            })
            return

        # 2. Live API call with fallback/retry
        try:
            stream_gen = self._original.create(*args, **kwargs)
        except Exception as e:
            logger.error(f"CostOpt stream: Primary call to {model_used} failed: {e}")
            fallbacks = self._wrapper.router.get_fallbacks(model_used)
            stream_gen = None
            for fb in fallbacks:
                try:
                    kwargs["model"] = fb
                    stream_gen = self._original.create(*args, **kwargs)
                    model_used = fb
                    break
                except Exception:
                    continue
            if stream_gen is None:
                raise e

        accumulated_chunks = []
        stream_failed = False
        stream_error = None
        exact_usage = None

        # Wrap chunk iteration to catch mid-stream failures (Fix Bug 7)
        try:
            for chunk in stream_gen:
                accumulated_chunks.append(chunk)
                if hasattr(chunk, "usage") and chunk.usage:
                    exact_usage = chunk.usage
                yield chunk
        except Exception as se:
            stream_failed = True
            stream_error = se

        latency_ms = int((time.time() - start_time) * 1000)

        if exact_usage:
            input_tokens = getattr(exact_usage, "prompt_tokens", 0)
            output_tokens = getattr(exact_usage, "completion_tokens", 0)
        else:
            try:
                import tiktoken
                enc = tiktoken.encoding_for_model(model_used)
                input_tokens = len(enc.encode(prompt_text))
            except Exception:
                input_tokens = len(prompt_text.split())
            output_tokens = max(0, len(accumulated_chunks) - 1)

        cost_orig = calculate_cost(self._wrapper.provider, model_requested, input_tokens, output_tokens, cache_hit=False)
        cost_act = calculate_cost(self._wrapper.provider, model_used, input_tokens, output_tokens, cache_hit=False) if not stream_failed else 0.0
        savings = max(0.0, round(cost_orig - cost_act, 6)) if not stream_failed else 0.0

        if not stream_failed:
            # 3. Write chunks to cache for future hits (Fix Bug 1 & Bug 2)
            try:
                self._wrapper.cache.set(prompt_text, model_used, {
                    "_stream_chunks": [c.model_dump() for c in accumulated_chunks],
                    "_input_tokens": input_tokens,
                    "_output_tokens": output_tokens,
                    "_cost_original": cost_orig,
                }, params_hash=params_hash)
            except Exception as ce:
                logger.error(f"CostOpt stream: Failed to write cache: {ce}")

        # Always log telemetry even on mid-stream failure (Fix Bug 7)
        self._wrapper.telemetry.log({
            "request_id": str(uuid.uuid4()),
            "provider": self._wrapper.provider,
            "model_requested": model_requested,
            "model_used": model_used,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "status_code": 200 if not stream_failed else 500,
            "success": not stream_failed,
            "error_type": type(stream_error).__name__ if stream_failed else None,
            "cache_hit": False,
            "cost_original": cost_orig,
            "cost_actual": cost_act,
            "savings": savings,
            "prompt_hash": prompt_hash,
            "environment": environment,
            "application": application,
            "region": region,
            "retry_count": 0,
            "file_path": file_path,
            "line_number": line_number
        })

        if stream_failed and stream_error:
            raise stream_error


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
        region: str = "us-east-1",
        circuit_breaker_max_calls: int = 15
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
        self.circuit_breaker = CircuitBreaker(max_calls=circuit_breaker_max_calls)

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
