"""One assistant turn: the conversation so far in, one reply out (CH-01, D-011).

Nothing is stored on the server; the widget sends the recent messages each time. The model may
call the role's read-only tools for up to MAX_TOOL_ROUNDS rounds, then must answer.
"""

import logging
import time
from dataclasses import dataclass

from django.conf import settings

from chat_bot.ai_chatbot import Asker, run_tool, tools_for
from chat_bot.prompts import system_instruction
from marketlink_core.gemini import AIUnavailable, call_with_fallback, make_client, model_chain

logger = logging.getLogger("marketlink")

MAX_TOOL_ROUNDS = 3
MAX_CALLS_PER_ROUND = 4
MAX_REPLY_CHARS = 2000


@dataclass(frozen=True)
class ChatReply:
    reply: str
    tools_used: list[str]
    model: str


def _models() -> list[str]:
    return model_chain(settings.GEMINI_CHAT_MODEL, settings.GEMINI_CHAT_FALLBACK_MODELS)


def _generate(client, model: str, contents, config):
    """One call. Split out so tests can stand in for the network."""
    return client.models.generate_content(model=model, contents=contents, config=config)


def _contents(messages: list[dict]):
    from google.genai import types

    return [
        types.Content(role="model" if message["role"] == "assistant" else "user", parts=[types.Part.from_text(text=message["content"])])
        for message in messages
    ]


def _text(response) -> str:
    try:
        return (response.text or "").strip()
    except (ValueError, AttributeError):  # no text part (e.g. only function calls)
        return ""


def answer(messages: list[dict], asker: Asker) -> ChatReply:
    """Raises AIUnavailable when the assistant is off or no model answers in time."""
    if not settings.AI_CHAT_ENABLED:
        raise AIUnavailable("The assistant is turned off.")
    client = make_client(settings.AI_CHAT_TIMEOUT_MS)
    from google.genai import types

    deadline = time.monotonic() + settings.AI_CHAT_DEADLINE_S
    contents = _contents(messages)
    base = {
        "system_instruction": system_instruction(asker.role, messages[-1]["content"]),
        "temperature": 0.3,
        # The tool loop below is ours (role checks, round limit), never the SDK's.
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
    }
    with_tools = types.GenerateContentConfig(**base, tools=tools_for(asker))
    # After the last tool round the model must answer with what it has.
    no_tools = types.GenerateContentConfig(**base)

    tools_used: list[str] = []
    model = ""
    for round_index in range(MAX_TOOL_ROUNDS + 1):
        config = with_tools if round_index < MAX_TOOL_ROUNDS else no_tools
        response, model = call_with_fallback(
            _models(), lambda name: _generate(client, name, contents, config), deadline=deadline
        )
        calls = list(response.function_calls or []) if config is with_tools else []
        if not calls:
            reply = _text(response)
            if not reply:
                raise AIUnavailable("The model returned an empty answer.")
            return ChatReply(reply=reply[:MAX_REPLY_CHARS], tools_used=tools_used, model=model)

        # Keep the model's own turn (its function calls), then answer each call.
        contents.append(response.candidates[0].content)
        results = []
        for call in calls[:MAX_CALLS_PER_ROUND]:
            outcome = run_tool(asker, call.name, call.args)
            if call.name not in tools_used:
                tools_used.append(call.name)
            results.append(types.Part.from_function_response(name=call.name, response=outcome))
        contents.append(types.Content(role="user", parts=results))
    raise AIUnavailable("The model kept asking for tools without answering.")  # pragma: no cover
