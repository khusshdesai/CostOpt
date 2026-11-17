"""
Context Propagation & Scope Management for Agent Attribution in CostOpt
Enables multi-agent attribution (run_id, agent, step) across threads and async tasks.
"""

import contextvars
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator

# ContextVar holding the current scope metadata dict
_CURRENT_SCOPE: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "costopt_scope", default={}
)


def get_current_scope() -> Dict[str, Any]:
    """Returns a copy of the current agent/run scope metadata."""
    return dict(_CURRENT_SCOPE.get())


@contextmanager
def scope(
    agent: Optional[str] = None,
    run_id: Optional[str] = None,
    step: Optional[str] = None,
    **kwargs: Any
) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager to scope all underlying LLM calls to a specific agent, run, or execution step.
    
    Example:
    --------
    with costopt.scope(agent="Researcher", run_id="workflow-101"):
        client.chat.completions.create(...)
    """
    parent = _CURRENT_SCOPE.get()
    new_scope = dict(parent)
    
    if agent is not None:
        new_scope["agent"] = str(agent)
    if run_id is not None:
        new_scope["run_id"] = str(run_id)
    if step is not None:
        new_scope["step"] = str(step)
        
    for k, v in kwargs.items():
        new_scope[k] = v

    token = _CURRENT_SCOPE.set(new_scope)
    try:
        yield new_scope
    finally:
        _CURRENT_SCOPE.reset(token)


def track(agent: Optional[str] = None, step: Optional[str] = None):
    """
    Decorator for agent functions/nodes in LangGraph, CrewAI, AutoGen, etc.
    
    Example:
    --------
    @costopt.track(agent="Writer")
    def write_report(state):
        ...
    """
    def decorator(fn):
        import functools
        import inspect

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                with scope(agent=agent or fn.__name__, step=step):
                    return await fn(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                with scope(agent=agent or fn.__name__, step=step):
                    return fn(*args, **kwargs)
            return sync_wrapper

    return decorator

