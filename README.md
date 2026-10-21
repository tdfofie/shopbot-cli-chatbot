# ShopBot: CLI chatbot with one tool and logging

A small command-line chatbot built for learning how LLM tool calling works, and
how to treat model output as untrusted input. It runs entirely on your machine
using [Ollama](https://ollama.com). No data leaves your computer.

## What it does

- Chats with a local model (default `llama3.2:3b`) acting as a store support bot.
- Has **one tool**, `get_order_status(order_id)`, backed by a fake in-memory order table.
- **Validates every tool request** from the model (known tool name, 4-digit order ID)
  before running anything, and caps tool calls per turn.
- Writes a **structured JSON log** (`chatbot.log`) of every user message, tool call,
  tool result and final answer, so a session can be reviewed or used to build detections.

## Setup

1. Install Ollama and pull a tool-capable model:
   ```
   ollama pull llama3.2:3b
   ```
2. Install the dependency:
   ```
   pip install -r requirements.txt
   ```
3. Run:
   ```
   python chatbot.py
   ```
   Use another model with `CHAT_MODEL`, e.g. `set CHAT_MODEL=mistral-small` on Windows.
   The model must support tool calling.

Try: `Where is my order 1234?` (shipped) or `Where is order 5678?` (processing).
Commands: `reset` clears the conversation, `quit` exits.

## Log format

One JSON object per line, for example:

```
{"event": "tool_call", "tool": "get_order_status", "args": {"order_id": "1234"}}
{"event": "tool_result", "result": {"status": "shipped", "eta": "2 days"}}
```

Events: `session_start`, `user_message`, `tool_call`, `tool_result`,
`tool_limit_reached`, `final_answer`, `error`, `session_end`.

## Things I learned

- The model decides when to call a tool and chooses the arguments, so the arguments
  must be validated in code. In testing, a small model sometimes called the tool with
  an invented order ID, or described a tool that does not exist.
- Tool calling turns text into actions, which raises the stakes of prompt injection.

## Limitations

- Fake data only; there is no authentication or per-user access control.
- Small local models are unreliable at deciding when to use a tool.
- Only run security tests against systems you own or have permission to test.
