from __future__ import annotations

from uuid import UUID, uuid4

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolCall
from app.assistant.llm.router import ModelRouter
from app.assistant.prompt import build_system_prompt
from app.assistant.schemas import AssistantChatResponse, AssistantToolCall, AssistantToolResult
from app.assistant.skills.registry import SkillContext, SkillRegistry
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError


class AgentService:
    def __init__(
        self,
        *,
        llm: ModelRouter,
        registry: SkillRegistry,
        context: ContextManager,
        max_tool_iterations: int,
        num_ctx: int,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._context = context
        self._max_tool_iterations = max(1, max_tool_iterations)
        self._num_ctx = num_ctx

    async def chat(
        self,
        *,
        user_id: UUID,
        message: str,
        session_id: UUID | None = None,
    ) -> AssistantChatResponse:
        active_session_id = session_id or uuid4()
        messages = [
            LLMMessage(role="system", content=build_system_prompt(self._registry)),
            LLMMessage(role="user", content=message),
        ]
        all_calls: list[AssistantToolCall] = []
        all_results: list[AssistantToolResult] = []
        final_response: LLMResponse | None = None

        for _ in range(self._max_tool_iterations):
            response = await self._llm.chat(
                self._context.trim(messages),
                self._registry.tool_definitions(),
                num_ctx=self._num_ctx,
            )
            final_response = response
            if not response.tool_calls:
                break
            messages.append(LLMMessage(role="assistant", content=response.content))
            for call in response.tool_calls:
                all_calls.append(_to_schema_call(call))
                result = await self._execute_tool(user_id=user_id, call=call)
                all_results.append(result)
                messages.append(LLMMessage(role="tool", content=_tool_message(result)))
        else:
            raise AppError(
                ErrorCode.INVALID_OPERATION,
                "Assistant reached the maximum tool iteration limit",
            )

        content = final_response.content if final_response is not None else ""
        return AssistantChatResponse(
            session_id=active_session_id,
            message=content or "Done.",
            tool_calls=all_calls,
            tool_results=all_results,
        )

    async def _execute_tool(self, *, user_id: UUID, call: LLMToolCall) -> AssistantToolResult:
        try:
            output = await self._registry.execute(
                name=call.name,
                context=SkillContext(user_id=user_id),
                arguments=call.arguments,
            )
            return AssistantToolResult(name=call.name, ok=True, output=output)
        except Exception as exc:
            return AssistantToolResult(name=call.name, ok=False, error=str(exc))


def _to_schema_call(call: LLMToolCall) -> AssistantToolCall:
    return AssistantToolCall(name=call.name, arguments=call.arguments)


def _tool_message(result: AssistantToolResult) -> str:
    return result.model_dump_json()
