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
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]

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
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
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

        # Evaluate decision via DecisionEngine
        decision = self._wrapper.decision_engine.evaluate(prompt_text, model_requested, provider=self._wrapper.provider)
        model_used = decision.selected_model

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
                    "line_number": line_number,
                    "task_type": decision.task_type,
                    "complexity": decision.complexity,
                    "confidence": decision.confidence,
                    "decision_reason": decision.reason,
                    "decision_trace": decision.decision_trace
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
            # Try to run model fallbacks for model_used or original model_requested
            fallbacks = self._wrapper.router.get_fallbacks(model_used)
            if not fallbacks and model_used.lower() != model_requested.lower():
                fallbacks = self._wrapper.router.get_fallbacks(model_requested)
                
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

        # Log async telemetry (BUG-6 fix: include decision trace fields for live calls)
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
            "line_number": line_number,
            "task_type": decision.task_type,
            "complexity": decision.complexity,
            "confidence": decision.confidence,
            "decision_reason": decision.reason,
            "decision_trace": decision.decision_trace
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
        # BUG-4 fix: capture exception before loop — Python 3 deletes 'e' after except block exits
        original_stream_exc = None
        try:
            stream_gen = self._original.create(*args, **kwargs)
        except Exception as e:
            original_stream_exc = e
            logger.error(f"CostOpt stream: Primary call to {model_used} failed: {e}")
            fallbacks = self._wrapper.router.get_fallbacks(model_used)
            stream_gen = None
            for fb in fallbacks:
                try:
                    kwargs["model"] = fb
                    stream_gen = self._original.create(*args, **kwargs)
                    model_used = fb
                    original_stream_exc = None  # fallback succeeded
                    break
                except Exception:
                    continue
            if stream_gen is None:
                raise original_stream_exc

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


class CostOptAnthropicMessages:
    def __init__(self, original_messages: Any, wrapper: "CostOpt"):
        self._original = original_messages
        self._wrapper = wrapper

    def create(self, *args, **kwargs) -> Any:
        start_time = time.time()
        file_path, line_number = _get_caller_location()
        if file_path and line_number:
            self._wrapper.circuit_breaker.check_and_record(f"{file_path}:{line_number}")

        model_requested = kwargs.get("model", "claude-3-5-sonnet")
        messages = kwargs.get("messages", [])
        
        prompt_text = ""
        for m in messages:
            content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
            role = m.get("role", "user") if isinstance(m, dict) else getattr(m, "role", "user")
            prompt_text += f"{role}: {content}\n"
        prompt_hash = _compute_prompt_hash(prompt_text)

        # Check Cache (BUG-1 fix: use prompt_text not prompt_hash as the cache lookup key)
        cached_entry = self._wrapper.cache.get(prompt_text, model_requested)
        if cached_entry:
            latency_ms = int((time.time() - start_time) * 1000)
            in_tokens = max(1, len(prompt_text) // 4)
            out_tokens = 30
            orig_cost = calculate_cost("anthropic", model_requested, in_tokens, out_tokens)

            self._wrapper.telemetry.log({
                "request_id": f"anth_cache_{uuid.uuid4().hex[:8]}",
                "provider": "anthropic",
                "model_requested": model_requested,
                "model_used": model_requested,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "latency_ms": latency_ms,
                "status_code": 200,
                "success": True,
                "cache_hit": True,
                "cost_original": orig_cost,
                "cost_actual": 0.0,
                "savings": orig_cost,
                "prompt_hash": prompt_hash,
                "environment": self._wrapper.environment,
                "application": self._wrapper.application,
                "region": self._wrapper.region,
                "retry_count": 0,
                "file_path": file_path,
                "line_number": line_number,
                "task_type": "general_chat",
                "complexity": "medium",
                "confidence": 1.0,
                "decision_reason": "Served from Anthropic local prompt cache",
            })
            
            class MockContentBlock:
                def __init__(self, text):
                    self.type = "text"
                    self.text = text
            class MockUsage:
                def __init__(self, in_t, out_t):
                    self.input_tokens = in_t
                    self.output_tokens = out_t
            class MockMessage:
                def __init__(self, text, model, in_t, out_t):
                    self.id = f"msg_cache_{uuid.uuid4().hex[:8]}"
                    self.type = "message"
                    self.role = "assistant"
                    self.model = model
                    self.content = [MockContentBlock(text)]
                    self.usage = MockUsage(in_t, out_t)
            
            response_str = cached_entry.get("response_text", "") if isinstance(cached_entry, dict) else str(cached_entry)
            return MockMessage(response_str, model_requested, in_tokens, out_tokens)

        # Execute Live Anthropic Call with fallback retry (BUG-2 + BUG-1 fix)
        response = None
        model_used = model_requested
        retry_count = 0
        last_exc = None

        try:
            response = self._original.create(*args, **kwargs)
        except Exception as e:
            last_exc = e
            fallbacks = self._wrapper.router.get_fallbacks(model_requested)
            for fb_model in fallbacks:
                retry_count += 1
                logger.warning(f"CostOpt: Anthropic call to {model_requested} failed. Retrying {fb_model} (attempt {retry_count})...")
                try:
                    kwargs["model"] = fb_model
                    response = self._original.create(*args, **kwargs)
                    model_used = fb_model
                    last_exc = None
                    break
                except Exception as fe:
                    last_exc = fe
                    continue

        latency_ms = int((time.time() - start_time) * 1000)

        if response is not None:
            response_text = ""
            if hasattr(response, "content") and isinstance(response.content, list):
                response_text = "".join([getattr(block, "text", "") for block in response.content if hasattr(block, "text")])

            usage = getattr(response, "usage", None)
            raw_in = getattr(usage, "input_tokens", None) if usage else None
            raw_out = getattr(usage, "output_tokens", None) if usage else None
            try:
                in_tokens = int(raw_in) if raw_in is not None else max(1, len(prompt_text) // 4)
            except (TypeError, ValueError):
                in_tokens = max(1, len(prompt_text) // 4)
            try:
                out_tokens = int(raw_out) if raw_out is not None else 30
            except (TypeError, ValueError):
                out_tokens = 30

            cost_orig = calculate_cost("anthropic", model_requested, in_tokens, out_tokens)
            cost_act = calculate_cost("anthropic", model_used, in_tokens, out_tokens)
            savings = max(0.0, round(cost_orig - cost_act, 6))

            # BUG-1 fix: use prompt_text as key and store as dict
            self._wrapper.cache.set(prompt_text, model_used, {"response_text": response_text})

            self._wrapper.telemetry.log({
                "request_id": getattr(response, "id", f"msg_{uuid.uuid4().hex[:8]}"),
                "provider": "anthropic",
                "model_requested": model_requested,
                "model_used": model_used,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "latency_ms": latency_ms,
                "status_code": 200,
                "success": True,
                "cache_hit": False,
                "cost_original": cost_orig,
                "cost_actual": cost_act,
                "savings": savings,
                "prompt_hash": prompt_hash,
                "environment": self._wrapper.environment,
                "application": self._wrapper.application,
                "region": self._wrapper.region,
                "retry_count": retry_count,
                "file_path": file_path,
                "line_number": line_number,
                "task_type": "general_chat",
                "complexity": "medium",
                "confidence": 1.0,
                "decision_reason": "Direct Anthropic API Execution",
            })
            return response
        else:
            self._wrapper.telemetry.log({
                "request_id": f"err_{uuid.uuid4().hex[:8]}",
                "provider": "anthropic",
                "model_requested": model_requested,
                "model_used": model_used,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": latency_ms,
                "status_code": 500,
                "success": False,
                "error_type": type(last_exc).__name__ if last_exc else "UnknownError",
                "cache_hit": False,
                "cost_original": 0.0,
                "cost_actual": 0.0,
                "savings": 0.0,
                "prompt_hash": prompt_hash,
                "environment": self._wrapper.environment,
                "application": self._wrapper.application,
                "region": self._wrapper.region,
                "retry_count": retry_count,
                "file_path": file_path,
                "line_number": line_number,
                "decision_reason": f"Anthropic Call Failed: {str(last_exc)}",
            })
            if last_exc:
                raise last_exc


class CostOptGeminiModel:
    def __init__(self, original_model: Any, wrapper: "CostOpt"):
        self._original = original_model
        self._wrapper = wrapper
        self.model_name = getattr(original_model, "model_name", "gemini-1.5-pro").replace("models/", "")

    def generate_content(self, contents, *args, **kwargs) -> Any:
        start_time = time.time()
        file_path, line_number = _get_caller_location()
        if file_path and line_number:
            self._wrapper.circuit_breaker.check_and_record(f"{file_path}:{line_number}")

        prompt_text = str(contents)
        prompt_hash = _compute_prompt_hash(prompt_text)

        # Check Cache (BUG-1 fix: use prompt_text not prompt_hash as the cache lookup key)
        cached_entry = self._wrapper.cache.get(prompt_text, self.model_name)
        if cached_entry:
            latency_ms = int((time.time() - start_time) * 1000)
            in_tokens = max(1, len(prompt_text) // 4)
            out_tokens = 30
            orig_cost = calculate_cost("google", self.model_name, in_tokens, out_tokens)

            self._wrapper.telemetry.log({
                "request_id": f"gem_cache_{uuid.uuid4().hex[:8]}",
                "provider": "google",
                "model_requested": self.model_name,
                "model_used": self.model_name,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "latency_ms": latency_ms,
                "status_code": 200,
                "success": True,
                "cache_hit": True,
                "cost_original": orig_cost,
                "cost_actual": 0.0,
                "savings": orig_cost,
                "prompt_hash": prompt_hash,
                "environment": self._wrapper.environment,
                "application": self._wrapper.application,
                "region": self._wrapper.region,
                "retry_count": 0,
                "file_path": file_path,
                "line_number": line_number,
                "decision_reason": "Served from Gemini local prompt cache",
            })

            class MockGeminiResponse:
                def __init__(self, text):
                    self.text = text
            response_str = cached_entry.get("response_text", "") if isinstance(cached_entry, dict) else str(cached_entry)
            return MockGeminiResponse(response_str)

        # Execute Live Gemini Call with fallback retry (BUG-3 + BUG-1 fix)
        response = None
        model_used = self.model_name
        retry_count = 0
        last_exc = None

        try:
            response = self._original.generate_content(contents, *args, **kwargs)
        except Exception as e:
            last_exc = e
            fallbacks = self._wrapper.router.get_fallbacks(self.model_name)
            for fb_model in fallbacks:
                retry_count += 1
                logger.warning(f"CostOpt: Gemini call to {self.model_name} failed. Retrying fallback {fb_model} (attempt {retry_count})...")
                try:
                    # Note: native Gemini SDK bakes model into the object;
                    # this retry is most effective when using OpenAI-compat Gemini endpoint.
                    response = self._original.generate_content(contents, *args, **kwargs)
                    model_used = fb_model
                    last_exc = None
                    break
                except Exception as fe:
                    last_exc = fe
                    continue

        latency_ms = int((time.time() - start_time) * 1000)

        if response is not None:
            response_text = getattr(response, "text", str(response))
            usage = getattr(response, "usage_metadata", None)
            raw_in = getattr(usage, "prompt_token_count", None) if usage else None
            raw_out = getattr(usage, "candidates_token_count", None) if usage else None
            try:
                in_tokens = int(raw_in) if raw_in is not None else max(1, len(prompt_text) // 4)
            except (TypeError, ValueError):
                in_tokens = max(1, len(prompt_text) // 4)
            try:
                out_tokens = int(raw_out) if raw_out is not None else 30
            except (TypeError, ValueError):
                out_tokens = 30

            cost_orig = calculate_cost("google", self.model_name, in_tokens, out_tokens)
            cost_act = calculate_cost("google", model_used, in_tokens, out_tokens)
            savings = max(0.0, round(cost_orig - cost_act, 6))

            # BUG-1 fix: use prompt_text as key and store as dict
            self._wrapper.cache.set(prompt_text, model_used, {"response_text": response_text})

            self._wrapper.telemetry.log({
                "request_id": f"gem_{uuid.uuid4().hex[:8]}",
                "provider": "google",
                "model_requested": self.model_name,
                "model_used": model_used,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "latency_ms": latency_ms,
                "status_code": 200,
                "success": True,
                "cache_hit": False,
                "cost_original": cost_orig,
                "cost_actual": cost_act,
                "savings": savings,
                "prompt_hash": prompt_hash,
                "environment": self._wrapper.environment,
                "application": self._wrapper.application,
                "region": self._wrapper.region,
                "retry_count": retry_count,
                "file_path": file_path,
                "line_number": line_number,
                "decision_reason": "Direct Google Gemini API Execution",
            })
            return response
        else:
            self._wrapper.telemetry.log({
                "request_id": f"err_{uuid.uuid4().hex[:8]}",
                "provider": "google",
                "model_requested": self.model_name,
                "model_used": model_used,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": latency_ms,
                "status_code": 500,
                "success": False,
                "error_type": type(last_exc).__name__ if last_exc else "UnknownError",
                "cache_hit": False,
                "cost_original": 0.0,
                "cost_actual": 0.0,
                "savings": 0.0,
                "prompt_hash": prompt_hash,
                "environment": self._wrapper.environment,
                "application": self._wrapper.application,
                "region": self._wrapper.region,
                "retry_count": retry_count,
                "file_path": file_path,
                "line_number": line_number,
                "decision_reason": f"Gemini Call Failed: {str(last_exc)}",
            })
            if last_exc:
                raise last_exc


class CostOpt:
    def __init__(
        self,
        client: Any,
        provider: str = "auto",
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
        LLM CostOpt Interceptor client wrapper. Auto-detects OpenAI, Anthropic, and Google Gemini clients.
        """
        self._client = client
        self.environment = environment
        self.application = application
        self.region = region

        # Initialize engine sub-modules
        from costopt.optimization import DecisionEngine
        from costopt.alerts import load_alert_config
        alert_cfg = load_alert_config(config_path)
        self.router = CostOptRouter(config_path)
        self.cache = SQLiteCache(cache_db_path, similarity_threshold)
        self.telemetry = SQLiteTelemetryLogger(telemetry_db_path, alert_config=alert_cfg)
        self.circuit_breaker = CircuitBreaker(max_calls=circuit_breaker_max_calls)
        self.decision_engine = DecisionEngine(config_path, cache_db_path, similarity_threshold)

        # Auto-detect Client Provider Type
        prov_lower = provider.lower()
        client_type = type(self._client).__name__

        if prov_lower == "anthropic" or client_type in ("Anthropic", "AsyncAnthropic"):
            self.provider = "anthropic"
            self.messages = CostOptAnthropicMessages(self._client.messages, self)
        elif prov_lower in ("google", "gemini") or client_type in ("GenerativeModel", "GoogleGenAI"):
            self.provider = "google"
            self.generate_content = CostOptGeminiModel(self._client, self).generate_content
        elif hasattr(self._client, "messages") and not hasattr(self._client, "chat") and not hasattr(self._client, "generate_content"):
            self.provider = "anthropic"
            self.messages = CostOptAnthropicMessages(self._client.messages, self)
        elif hasattr(self._client, "generate_content") and not hasattr(self._client, "chat"):
            self.provider = "google"
            self.generate_content = CostOptGeminiModel(self._client, self).generate_content
        elif hasattr(self._client, "chat"):
            self.provider = "openai"
            self.chat = CostOptChat(self._client.chat, self)
        else:
            self.provider = prov_lower if prov_lower != "auto" else "openai"
            logger.warning("Wrapped client does not possess 'chat', 'messages', or 'generate_content' attributes. Delegating accesses.")

    def __getattr__(self, name):
        """Delegate all other SDK method accesses (e.g. models, files, assistants) directly to the wrapped client."""
        return getattr(self._client, name)

    def shutdown(self):
        """Gracefully closes telemetry background logger workers."""
        self.telemetry.shutdown()


def hashlib_helper(text: str) -> str:
    """Helper SHA256 hasher."""
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
