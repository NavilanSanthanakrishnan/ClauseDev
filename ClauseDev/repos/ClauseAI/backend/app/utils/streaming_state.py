import time
from typing import Dict, Any, Optional

class StreamingState:
    def __init__(self):
        self.status = "idle"
        self.current_operation: Optional[str] = None
        self.progress = 0
        self.step: Optional[str] = None
        self.error: Optional[str] = None
        self.current_iteration = 0
        self.tool_calls_history = []
        self.current_tool_call: Optional[Dict[str, Any]] = None
        self.partial_data: Optional[Any] = None

    def reset(self, step: str):
        self.status = "running"
        self.current_operation = "Initializing..."
        self.progress = 0
        self.step = step
        self.error = None
        self.current_iteration = 0
        self.tool_calls_history = []
        self.current_tool_call = None
        self.partial_data = None

    def update(
        self,
        operation: Optional[str] = None,
        progress: Optional[int] = None,
        partial_data: Optional[Any] = None
    ):
        if operation:
            self.current_operation = operation
        if progress is not None:
            self.progress = max(0, min(100, progress))
        if partial_data is not None:
            self.partial_data = partial_data

    def start_iteration(self, iteration: int):
        self.current_iteration = iteration
        self.current_operation = f"Agentic iteration {iteration}"

    def complete(self, final_data: Optional[Any] = None):
        self.status = "completed"
        self.current_operation = "Analysis complete"
        self.progress = 100
        if final_data is not None:
            self.partial_data = final_data

    def start_tool_call(self, tool_name: str, tool_args: dict, iteration: int):
        self.current_tool_call = {
            "iteration": iteration,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "status": "executing",
            "started_at": time.time()
        }
        self.current_operation = f"Executing tool: {tool_name}"

    def complete_tool_call(self, tool_result: str):
        if not self.current_tool_call:
            return

        completed_at = time.time()
        started_at = self.current_tool_call["started_at"]
        self.current_tool_call["status"] = "completed"
        self.current_tool_call["result"] = tool_result
        self.current_tool_call["completed_at"] = completed_at
        self.current_tool_call["duration"] = completed_at - started_at
        self.tool_calls_history.append(self.current_tool_call.copy())
        self.current_tool_call = None

    def set_error(self, error_msg: str):
        self.status = "error"
        self.current_operation = f"Error: {error_msg}"
        self.progress = 0
        self.error = error_msg

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "status": self.status,
            "current_operation": self.current_operation,
            "progress": self.progress,
            "step": self.step,
            "current_iteration": self.current_iteration,
            "total_tool_calls": len(self.tool_calls_history),
            "tool_calls_history": self.tool_calls_history,
            "current_tool_call": self.current_tool_call
        }

        if self.partial_data is not None:
            payload["partial_data"] = self.partial_data

        if self.error:
            payload["error"] = self.error

        return payload