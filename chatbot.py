"""Command-line chatbot with one tool and structured logging.

A local Ollama model can ask for one tool, get_order_status. Our code
VALIDATES every request before running it: model output is untrusted input.
"""
import json
import logging
import os
import re

import requests

OLLAMA_CHAT = "http://localhost:11434/api/chat"
MODEL = os.environ.get("CHAT_MODEL", "llama3.2:3b")  # must support tool calling
LOG_FILE = "chatbot.log"
MAX_TOOL_CALLS_PER_TURN = 2

# Fake data standing in for a real order database.
ORDERS = {
    "1234": {"status": "shipped", "eta": "2 days"},
    "5678": {"status": "processing", "eta": "5 days"},
}

SYSTEM_PROMPT = (
    "You are ShopBot, a customer support assistant for an online store. "
    "Only use the get_order_status tool when the customer gives a specific order ID. "
    "Otherwise answer normally and briefly."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Look up the status of a customer order by its 4-digit ID.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "4-digit order ID"}},
                "required": ["order_id"],
            },
        },
    }
]

logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO,
    format="%(asctime)s %(message)s", encoding="utf-8",
)


def log_event(event: str, **data) -> None:
    logging.info(json.dumps({"event": event, "model": MODEL, **data}, ensure_ascii=False))


def get_order_status(order_id: str) -> dict:
    return ORDERS.get(order_id, {"error": "order not found"})


def run_tool(name: str, args: dict) -> dict:
    """Validate the model's request before running anything."""
    if name != "get_order_status":
        return {"error": "unknown tool"}
    order_id = str(args.get("order_id", ""))
    if not re.fullmatch(r"\d{4}", order_id):  # never trust model-supplied arguments
        return {"error": "invalid order id"}
    return get_order_status(order_id)


def call_model(messages: list[dict]) -> dict:
    resp = requests.post(
        OLLAMA_CHAT,
        json={"model": MODEL, "stream": False, "messages": messages, "tools": TOOLS},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["message"]


def handle_turn(messages: list[dict], user_msg: str) -> str:
    messages.append({"role": "user", "content": user_msg})
    log_event("user_message", text=user_msg)
    reply = call_model(messages)

    tool_calls = 0
    while reply.get("tool_calls"):
        messages.append(reply)
        for call in reply["tool_calls"]:
            name, args = call["function"]["name"], call["function"]["arguments"]
            tool_calls += 1
            if tool_calls > MAX_TOOL_CALLS_PER_TURN:
                log_event("tool_limit_reached", tool=name, args=args)
                result = {"error": "tool call limit reached"}
            else:
                log_event("tool_call", tool=name, args=args)
                result = run_tool(name, args)
                log_event("tool_result", tool=name, result=result)
            messages.append({"role": "tool", "content": json.dumps(result)})
        if tool_calls > MAX_TOOL_CALLS_PER_TURN:
            reply = {"role": "assistant", "content": "Sorry, I couldn't complete that request."}
            break
        reply = call_model(messages)

    text = reply["content"]
    messages.append({"role": "assistant", "content": text})
    log_event("final_answer", text=text)
    return text


def new_conversation() -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def main() -> None:
    print(f"ShopBot ({MODEL}). Try: 'Where is my order 1234?'  Commands: reset, quit\n")
    log_event("session_start")
    messages = new_conversation()
    while True:
        user_msg = input("You: ").strip()
        if not user_msg:
            continue
        if user_msg.lower() == "quit":
            break
        if user_msg.lower() == "reset":
            messages = new_conversation()
            print("(conversation reset)\n")
            continue
        try:
            print(f"\nShopBot: {handle_turn(messages, user_msg)}\n")
        except requests.RequestException as e:
            log_event("error", error=str(e))
            print(f"Error talking to Ollama: {e}\n")
            messages.pop()
    log_event("session_end")


if __name__ == "__main__":
    main()
