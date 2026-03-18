import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Callable, Optional, TYPE_CHECKING

from .llm_helpers import extract_json_from_text
from .llm_helpers import build_tool_call_message, build_tool_result_message
from app.core.config import LOG_LLM_OUTPUTS

if TYPE_CHECKING:
    from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

@dataclass
class AgenticLoopConfig:
    max_iterations: int
    min_interval: int
    tools: List[Dict[str, Any]]
    tool_functions: Dict[str, Callable]
    final_prompt: Optional[str] = None
    use_async_tools: bool = False

@dataclass
class AgenticLoopResult:
    analysis: str
    reasoning_history: List[Dict[str, Any]]
    iterations: int
    messages: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)

def parse_tool_args(raw_args: str) -> Dict[str, Any]:
    if not raw_args:
        return {}
    try:
        parsed = json.loads(raw_args)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        parsed = extract_json_from_text(raw_args)
        return parsed if isinstance(parsed, dict) else {}

def get_tool_call_attr(tool_call: Any, path: str, default: Any = None) -> Any:
    current = tool_call
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            current = getattr(current, key, default)
        if current is default:
            break
    return current

async def execute_tool_call(
    tool_name: str,
    tool_args: Dict[str, Any],
    tool_functions: Dict[str, Callable],
    use_async: bool = False
) -> str:
    if tool_name not in tool_functions:
        logger.warning(
            "Tool call received for unknown tool",
            extra={"event": "tool_unknown", "tool_name": tool_name},
        )
        return f"Error: Unknown tool '{tool_name}'"

    try:
        if use_async:
            result = await tool_functions[tool_name](**tool_args)
        else:
            result = tool_functions[tool_name](**tool_args)

        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=4)
        return str(result)
    except Exception as error:
        logger.exception(
            "Tool execution failed",
            extra={"event": "tool_execution_failed", "tool_name": tool_name, "tool_args": tool_args},
        )
        return f"Error executing {tool_name}: {str(error)}"

def record_tool_trace(
    metadata: Dict[str, Any],
    iteration: int,
    tool_name: str,
    tool_args: Dict[str, Any],
    tool_result: str
) -> None:
    if "tool_execution_trace" not in metadata:
        metadata["tool_execution_trace"] = []
    metadata["tool_execution_trace"].append(
        {
            "iteration": iteration,
            "tool_name": tool_name,
            "tool_input": tool_args,
            "tool_output": tool_result
        }
    )

async def run_agentic_loop(
    initial_messages: List[Dict[str, Any]],
    config: AgenticLoopConfig,
    client: "LLMClient",
    model: str,
    metadata_collector: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]] = None,
    streaming_state: Optional[Any] = None
) -> AgenticLoopResult:
    messages = initial_messages.copy()
    reasoning_history: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    iteration = 0

    while iteration < config.max_iterations:
        iteration += 1
        logger.info(
            "Agentic iteration started",
            extra={"event": "agentic_iteration_started", "iteration": iteration},
        )
        if config.min_interval > 0:
            await asyncio.sleep(config.min_interval)

        if streaming_state:
            streaming_state.start_iteration(iteration)
            streaming_state.update(operation=f"Running agentic iteration {iteration}", progress=min(30 + iteration * 10, 70))

        response = await asyncio.to_thread(
            client.chat,
            messages=messages,
            model=model,
            tools=config.tools,
            tool_choice="auto"
        )

        if LOG_LLM_OUTPUTS:
            logger.info(
                "Agentic iteration LLM output",
                extra={
                    "event": "agentic_iteration_llm_output",
                    "iteration": iteration,
                    "finish_reason": response.get("finish_reason"),
                    "content": response.get("content", ""),
                    "has_reasoning": bool(response.get("reasoning")),
                    "tool_call_count": len(response.get("tool_calls") or []),
                },
            )

        if response.get("reasoning"):
            reasoning_history.append(
                {
                    "iteration": iteration,
                    "reasoning": response["reasoning"]
                }
            )

        tool_calls = response.get("tool_calls") or []
        if not tool_calls:
            logger.info(
                "Agentic loop completed without tool calls",
                extra={"event": "agentic_loop_completed", "iterations": iteration},
            )
            
            if config.final_prompt:
                messages.append({"role": "assistant", "content": response["content"]})
                messages.append({"role": "user", "content": config.final_prompt})
                if streaming_state:
                    streaming_state.update(operation="Generating final analysis", progress=92)
                final_response = await asyncio.to_thread(client.chat, messages=messages, model=model)
                if LOG_LLM_OUTPUTS:
                    logger.info(
                        "Agentic final LLM output",
                        extra={
                            "event": "agentic_final_llm_output",
                            "iteration": iteration,
                            "finish_reason": final_response.get("finish_reason"),
                            "content": final_response.get("content", ""),
                            "has_reasoning": bool(final_response.get("reasoning")),
                            "tool_call_count": len(final_response.get("tool_calls") or []),
                        },
                    )
                messages.append({"role": "assistant", "content": final_response["content"]})
                return AgenticLoopResult(
                    analysis=final_response["content"],
                    reasoning_history=reasoning_history,
                    iterations=iteration,
                    messages=messages,
                    metadata=metadata
                )
            return AgenticLoopResult(
                analysis=response["content"],
                reasoning_history=reasoning_history,
                iterations=iteration,
                messages=messages,
                metadata=metadata
            )

        messages.append(build_tool_call_message(tool_calls))

        for tool_call in tool_calls:
            tool_name = get_tool_call_attr(tool_call, "function.name", "")
            raw_args = get_tool_call_attr(tool_call, "function.arguments", "{}")
            tool_call_id = get_tool_call_attr(tool_call, "id", "")
            tool_args = parse_tool_args(raw_args)

            if metadata_collector:
                metadata_collector(tool_name, tool_args, metadata)

            if streaming_state:
                streaming_state.start_tool_call(tool_name, tool_args, iteration)
                streaming_state.update(operation=f"Executing tool: {tool_name}")

            tool_result = await execute_tool_call(
                tool_name=tool_name,
                tool_args=tool_args,
                tool_functions=config.tool_functions,
                use_async=config.use_async_tools
            )
            record_tool_trace(metadata, iteration, tool_name, tool_args, tool_result)
            logger.info(
                "Tool call completed",
                extra={"event": "tool_execution_completed", "iteration": iteration, "tool_name": tool_name},
            )

            if streaming_state:
                streaming_state.complete_tool_call(tool_result)
                streaming_state.update(operation=f"Tool execution complete: {tool_name}", progress=min(75 + iteration * 5, 90))

            messages.append(build_tool_result_message(tool_call_id, tool_result))

    if config.final_prompt:
        logger.info(
            "Agentic loop reached max iterations, requesting final analysis",
            extra={"event": "agentic_loop_final_prompt", "iterations": iteration},
        )
        messages.append({"role": "user", "content": config.final_prompt})
        if streaming_state:
            streaming_state.update(operation="Generating final analysis", progress=92)
        final_response = await asyncio.to_thread(client.chat, messages=messages, model=model)
        if LOG_LLM_OUTPUTS:
            logger.info(
                "Agentic final LLM output",
                extra={
                    "event": "agentic_final_llm_output",
                    "iteration": iteration,
                    "finish_reason": final_response.get("finish_reason"),
                    "content": final_response.get("content", ""),
                    "has_reasoning": bool(final_response.get("reasoning")),
                    "tool_call_count": len(final_response.get("tool_calls") or []),
                },
            )
        messages.append({"role": "assistant", "content": final_response["content"]})
        return AgenticLoopResult(
            analysis=final_response["content"],
            reasoning_history=reasoning_history,
            iterations=iteration,
            messages=messages,
            metadata=metadata
        )

    return AgenticLoopResult(
        analysis="Max iterations reached without final output",
        reasoning_history=reasoning_history,
        iterations=iteration,
        messages=messages,
        metadata=metadata
    )
