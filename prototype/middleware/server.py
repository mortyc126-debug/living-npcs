"""FastAPI-сервер: эмулирует OpenAI /v1/chat/completions для Mindcraft.

Запуск:
    python -m middleware.server --config configs/wanderer.yaml --port 8090

Mindcraft видит этот сервер как обычный OpenAI API. Внутри — наш cognitive
agent с HEXACO/VAD/STM/LTM.
"""

import argparse
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from .character import CharacterState
from .cognitive_loop import CognitiveAgent
from .config import load_config
from .llm_client import LlamaServerClient


# --- OpenAI API типы (минимальный набор для Mindcraft) ---


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 200
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


class Choice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]


# --- Глобальное состояние ---


class AppState:
    agent: Optional[CognitiveAgent] = None
    llm_client: Optional[LlamaServerClient] = None
    config: Optional[Dict[str, Any]] = None


state = AppState()
log = logging.getLogger("wanderer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = state.config or {}
    llm_cfg = cfg.get("llm", {})
    state.llm_client = LlamaServerClient(
        base_url=llm_cfg.get("base_url", "http://localhost:8080"),
    )
    if not await state.llm_client.health():
        log.warning("llama-server недоступен на старте — продолжаем, но запросы упадут")

    character = CharacterState.from_config(cfg)
    state.agent = CognitiveAgent(
        name=cfg.get("name", "Странник"),
        character=character,
        llm=state.llm_client,
        stm_capacity=cfg.get("memory", {}).get("stm_capacity", 50),
        ltm_max_size=cfg.get("memory", {}).get("ltm_max_size", 1000),
    )
    log.info(f"Странник готов. HEXACO: {character.hexaco}")
    yield
    if state.llm_client:
        await state.llm_client.close()


app = FastAPI(title="Living NPCs middleware", lifespan=lifespan)


@app.get("/health")
async def health() -> Dict[str, Any]:
    llm_ok = await state.llm_client.health() if state.llm_client else False
    return {"agent_ready": state.agent is not None, "llm_ok": llm_ok}


@app.get("/v1/models")
async def list_models() -> Dict[str, Any]:
    """Mindcraft проверяет модели — возвращаем заглушку."""
    name = (state.config or {}).get("llm", {}).get("model_name", "wanderer")
    return {
        "object": "list",
        "data": [{"id": name, "object": "model", "created": 0, "owned_by": "living-npcs"}],
    }


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(req: ChatCompletionRequest) -> ChatCompletionResponse:
    if state.agent is None:
        raise HTTPException(503, "agent not ready")
    if req.stream:
        # Шаг 1 — без стриминга. Mindcraft умеет работать без него.
        raise HTTPException(400, "streaming not supported in MVP step 1")

    # Берём последнее user-сообщение как восприятие/реплику.
    user_msgs = [m for m in req.messages if m.role == "user"]
    if not user_msgs:
        raise HTTPException(400, "no user message")
    last_user = user_msgs[-1].content

    # История без system (мы свой соберём) и без последнего user.
    history = [
        {"role": m.role, "content": m.content}
        for m in req.messages[:-1]
        if m.role in ("user", "assistant")
    ]

    log.info(f"[->] Странник получил: {last_user[:200]}")
    response_text = await state.agent.respond(
        user_message=last_user,
        history=history,
        max_tokens=req.max_tokens or 200,
        temperature=req.temperature or 0.7,
    )
    log.info(f"[<-] Странник ответил: {response_text[:200]}")

    return ChatCompletionResponse(
        id=f"wndr-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=req.model,
        choices=[Choice(index=0, message=ChatMessage(role="assistant", content=response_text))],
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/wanderer.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    state.config = load_config(args.config)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()
