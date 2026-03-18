from typing import List, Dict, Any, Optional
import logging
from openai import OpenAI
from openai import APIError, RateLimitError
import re

from app.core.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_API_KEYS,
    OPENROUTER_BASE_URL,
    DEFAULT_MODEL,
    LLM_REQUEST_TIMEOUT_SECONDS,
    ENABLE_THINKING,
    ENABLE_PROMPT_CACHING,
    LOG_LLM_OUTPUTS,
    LOG_LLM_PROMPTS,
)

logger = logging.getLogger(__name__)

def _serialize_tool_calls(tool_calls: Any) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    if not tool_calls:
        return serialized

    for tool_call in tool_calls:
        if isinstance(tool_call, dict):
            call_id = tool_call.get("id")
            tool_type = tool_call.get("type")
            function = tool_call.get("function") or {}
            function_name = function.get("name") if isinstance(function, dict) else None
            function_args = function.get("arguments") if isinstance(function, dict) else None
        else:
            call_id = getattr(tool_call, "id", None)
            tool_type = getattr(tool_call, "type", None)
            function = getattr(tool_call, "function", None)
            function_name = getattr(function, "name", None) if function is not None else None
            function_args = getattr(function, "arguments", None) if function is not None else None

        serialized.append(
            {
                "id": call_id,
                "type": tool_type,
                "name": function_name,
                "arguments": function_args,
            }
        )

    return serialized

class LLMClient:    
    def __init__(self):
        self.api_keys = OPENROUTER_API_KEYS or ([OPENROUTER_API_KEY] if OPENROUTER_API_KEY else [])
        self.key_index = 0
        self.client = OpenAI(
            api_key=self._current_key(),
            base_url=OPENROUTER_BASE_URL,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS
        )
        self.model = DEFAULT_MODEL
        logger.info(
            "LLM client initialized",
            extra={
                "event": "llm_client_initialized",
                "configured_keys": len(self.api_keys),
                "model": self.model,
            },
        )

    def _current_key(self) -> str:
        if not self.api_keys:
            return ""
        return self.api_keys[self.key_index % len(self.api_keys)]

    def _rotate_key(self) -> bool:
        if not self.api_keys:
            return False
        if len(self.api_keys) == 1:
            return False
        self.key_index = (self.key_index + 1) % len(self.api_keys)
        self.client = OpenAI(
            api_key=self._current_key(),
            base_url=OPENROUTER_BASE_URL,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS
        )
        logger.warning(
            "Rotated OpenRouter API key after rate limit",
            extra={
                "event": "llm_key_rotated",
                "key_index": self.key_index,
                "total_keys": len(self.api_keys),
            },
        )
        return True

    def _is_rate_limit(self, error: Exception) -> bool:
        if isinstance(error, RateLimitError):
            return True
        if isinstance(error, APIError) and getattr(error, "status_code", None) == 429:
            return True
        return getattr(error, "status_code", None) == 429
    
    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        enable_thinking: bool = ENABLE_THINKING,
        prompt_caching: bool = ENABLE_PROMPT_CACHING,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> Dict[str, Any]:
        extra_params = {"chat_template_kwargs": {}}
        
        if enable_thinking:
            extra_params["chat_template_kwargs"]["enable_thinking"] = True
            extra_params["reasoning"] = {"enabled": True}
        
        if prompt_caching:
            extra_params["chat_template_kwargs"]["cache_prompt"] = True
        
        if model is None:
            model = self.model

        if LOG_LLM_PROMPTS:
            logger.info(
                "LLM chat request",
                extra={
                    "event": "llm_chat_request",
                    "model": model,
                    "message_count": len(messages),
                    "messages": messages,
                    "tool_count": len(tools or []),
                    "tools": tools or [],
                    "tool_choice": tool_choice if tools else None,
                    "enable_thinking": enable_thinking,
                    "prompt_caching": prompt_caching,
                    "temperature": temperature,
                    "top_p": top_p,
                },
            )
        
        attempts = 0
        max_attempts = max(1, len(self.api_keys))
        while True:
            try:
                completion = self.client.chat.completions.create(
                    messages=messages,
                    model=model,
                    extra_body=extra_params,
                    temperature=temperature,
                    top_p=top_p,
                    tools=tools,
                    tool_choice=tool_choice if tools else None,
                    stream=False
                )
                break
            except Exception as error:
                attempts += 1
                if self._is_rate_limit(error):
                    logger.warning(
                        "LLM request rate limited",
                        extra={
                            "event": "llm_rate_limited",
                            "attempt": attempts,
                            "max_attempts": max_attempts,
                            "model": model,
                        },
                    )
                    if attempts < max_attempts and self._rotate_key():
                        continue
                    logger.error(
                        "All OpenRouter API keys exhausted due to rate limit",
                        extra={"event": "llm_keys_exhausted", "attempts": attempts, "model": model},
                    )
                    raise RuntimeError("OpenRouter API keys not working")
                logger.exception(
                    "LLM chat completion failed",
                    extra={"event": "llm_chat_failed", "attempt": attempts, "model": model},
                )
                raise error

        message = completion.choices[0].message
        content = message.content or ""
        content = re.sub(r'```(\w+)?', '', content.strip())
        content = re.sub(r'```', '', content)
        finish_reason = completion.choices[0].finish_reason
        tool_calls = message.tool_calls if hasattr(message, 'tool_calls') else None
        serialized_tool_calls = _serialize_tool_calls(tool_calls)

        logger.info(
            "LLM chat completed",
            extra={
                "event": "llm_chat_completed",
                "model": model,
                "finish_reason": finish_reason,
                "output_chars": len(content),
                "tool_call_count": len(serialized_tool_calls),
            },
        )

        if LOG_LLM_OUTPUTS:
            logger.info(
                "LLM chat output",
                extra={
                    "event": "llm_chat_output",
                    "model": model,
                    "finish_reason": finish_reason,
                    "content": content,
                    "reasoning": getattr(message, 'reasoning', None),
                    "tool_calls": serialized_tool_calls,
                },
            )

        return {
            "content": content,
            "reasoning": getattr(message, 'reasoning', None),
            "tool_calls": tool_calls,
            "finish_reason": finish_reason
        }
