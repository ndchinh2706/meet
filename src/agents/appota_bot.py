"""LiveKit agent — joins a Meet room, transcribes each participant, and
persists transcripts to the Meet backend so they can be queried via MCP.

Per-participant pipeline:

    audio → Silero VAD → OpenAI STT → AgentSession event
                                       │
                                       ├─→ broadcast on `lk.transcription`
                                       │   data channel (Meet UI captions)
                                       └─→ POST to Meet backend
                                           /external-api/v1.0/rooms/{id}/utterances/

The backend POST is fire-and-forget: if it fails we log and move on, the
STT pipeline keeps running. Persistence guarantees are not the agent's job
— the backend acks every accepted utterance with 201, and any drop here is
already lost data (we're not buffering interim drafts to disk on purpose).

Run locally:
    cd agents && cp .env.example .env.local
    # set OPENAI_API_KEY, AGENT_API_KEY in .env.local
    uv sync
    uv run python agent.py start
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    JobRequest,
    RoomIO,
    WorkerOptions,
    cli,
    utils,
)
from livekit.agents import room_io as lk_room_io
from livekit.plugins import openai, silero

load_dotenv(".env.local", override=False)
load_dotenv(".env", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("appota-agent")

AGENT_NAME = os.getenv("AGENT_NAME", "appota-bot")
AGENT_DISPLAY_NAME = os.getenv("AGENT_DISPLAY_NAME", "Trợ lý Appota")
WORKER_HTTP_PORT = int(os.getenv("AGENT_HTTP_PORT", "8089"))

STT_MODEL = os.getenv("STT_MODEL", "gpt-4o-mini-transcribe")
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "vi")

# Backend persistence
MEET_API_URL = os.getenv("MEET_API_URL", "http://localhost:8083").rstrip("/")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")

CHAT_DATA_TOPIC = "lk.chat"


def _build_stt() -> openai.STT:
    kwargs: dict = {"model": STT_MODEL}
    if STT_LANGUAGE:
        kwargs["language"] = STT_LANGUAGE
    return openai.STT(**kwargs)


# ---------------------------------------------------------------------------
# Backend persistence
# ---------------------------------------------------------------------------

_http_client: Optional[httpx.AsyncClient] = None


def _client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=5.0)
    return _http_client


async def _post_utterance(
    *,
    room_id: str,
    speaker_identity: str,
    speaker_name: str,
    text: str,
    is_final: bool,
    language: str,
) -> None:
    """Send one utterance to the Meet backend. Never raises."""
    if not AGENT_API_KEY:
        # Backend persistence not configured — skip silently. Useful when
        # the agent is run in a smoke-test context without a Meet backend.
        return
    text = (text or "").strip()
    if not text:
        return

    payload = {
        "speaker_identity": speaker_identity,
        "speaker_name": speaker_name or "",
        "text": text,
        "language": language or "",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "is_final": is_final,
    }
    url = f"{MEET_API_URL}/external-api/v1.0/rooms/{room_id}/utterances/"
    headers = {"Authorization": f"Bearer {AGENT_API_KEY}"}
    try:
        resp = await _client().post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.warning(
                "Backend rejected utterance (%s): %s",
                resp.status_code,
                resp.text[:200],
            )
    except Exception:
        logger.exception("Failed to post utterance to %s", url)


def _fire_and_forget(coro) -> None:
    """Schedule a coroutine without awaiting. Errors get logged via the task
    callback so they don't drift away silently."""
    task = asyncio.create_task(coro)

    def _on_done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            logger.error("Background task failed: %s", exc, exc_info=exc)

    task.add_done_callback(_on_done)


# ---------------------------------------------------------------------------
# STT pipeline
# ---------------------------------------------------------------------------


class _Transcriber(Agent):
    def __init__(self, *, participant_identity: str) -> None:
        super().__init__(instructions="not-needed", stt=_build_stt())
        self.participant_identity = participant_identity


class MultiUserTranscriber:
    """Open one transcription session per remote participant."""

    def __init__(self, ctx: JobContext) -> None:
        self.ctx = ctx
        self._sessions: dict[str, AgentSession] = {}
        self._tasks: set[asyncio.Task] = set()

    def start(self) -> None:
        self.ctx.room.on("participant_connected", self._on_participant_connected)
        self.ctx.room.on(
            "participant_disconnected", self._on_participant_disconnected
        )

    async def aclose(self) -> None:
        await utils.aio.cancel_and_wait(*self._tasks)
        await asyncio.gather(
            *[self._close_session(s) for s in self._sessions.values()]
        )
        self.ctx.room.off("participant_connected", self._on_participant_connected)
        self.ctx.room.off(
            "participant_disconnected", self._on_participant_disconnected
        )
        global _http_client
        if _http_client is not None:
            await _http_client.aclose()
            _http_client = None

    def _on_participant_connected(self, participant: rtc.RemoteParticipant) -> None:
        if participant.identity in self._sessions:
            return
        logger.info("Starting STT session for %s", participant.identity)
        task = asyncio.create_task(self._start_session(participant))
        self._tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            try:
                self._sessions[participant.identity] = t.result()
            except Exception:
                logger.exception(
                    "STT session failed for %s", participant.identity
                )
            finally:
                self._tasks.discard(t)

        task.add_done_callback(_done)

    def _on_participant_disconnected(
        self, participant: rtc.RemoteParticipant
    ) -> None:
        session = self._sessions.pop(participant.identity, None)
        if session is None:
            return
        logger.info("Closing STT session for %s", participant.identity)
        task = asyncio.create_task(self._close_session(session))
        self._tasks.add(task)
        task.add_done_callback(lambda _: self._tasks.discard(task))

    async def _start_session(
        self, participant: rtc.RemoteParticipant
    ) -> AgentSession:
        vad = self.ctx.proc.userdata.get("vad")
        session = AgentSession(vad=vad)
        room_io = RoomIO(
            agent_session=session,
            room=self.ctx.room,
            participant=participant,
            options=lk_room_io.RoomOptions(
                text_input=False,
                audio_output=False,
                text_output=True,
            ),
        )
        await room_io.start()

        room_name = self.ctx.room.name
        identity = participant.identity
        display_name = participant.name or participant.identity

        @session.on("user_input_transcribed")
        def _on_transcribed(ev) -> None:  # type: ignore[no-untyped-def]
            text = getattr(ev, "transcript", "") or ""
            is_final = bool(getattr(ev, "is_final", True))
            language = getattr(ev, "language", "") or STT_LANGUAGE
            kind = "final" if is_final else "partial"
            logger.info("[%s] (%s) %s", display_name, kind, text)
            _fire_and_forget(
                _post_utterance(
                    room_id=room_name,
                    speaker_identity=identity,
                    speaker_name=display_name,
                    text=text,
                    is_final=is_final,
                    language=language,
                )
            )

        await session.start(
            agent=_Transcriber(participant_identity=identity)
        )
        return session

    @staticmethod
    async def _close_session(session: AgentSession) -> None:
        await session.drain()
        await session.aclose()


# ---------------------------------------------------------------------------
# Worker plumbing
# ---------------------------------------------------------------------------


async def entrypoint(ctx: JobContext) -> None:
    metadata = ctx.job.metadata or ""
    logger.info("Dispatched to room=%s metadata=%r", ctx.room.name, metadata)

    transcriber = MultiUserTranscriber(ctx)
    transcriber.start()

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    me = ctx.room.local_participant
    logger.info("Connected: identity=%s name=%s", me.identity, me.name)

    try:
        await me.publish_data(
            payload=f"👋 {AGENT_DISPLAY_NAME} đã vào phòng, sẽ ghi lại bản ghi.".encode(
                "utf-8"
            ),
            reliable=True,
            topic=CHAT_DATA_TOPIC,
        )
    except Exception:
        logger.exception("Failed to send hello chat")

    for p in ctx.room.remote_participants.values():
        transcriber._on_participant_connected(p)

    async def cleanup() -> None:
        await transcriber.aclose()

    ctx.add_shutdown_callback(cleanup)


async def handle_request(req: JobRequest) -> None:
    logger.info("Accepting job for room=%s", req.room.name)
    suffix = (req.room.name or "")[:20]
    await req.accept(
        identity=f"{AGENT_NAME}-{suffix}" if suffix else AGENT_NAME,
        name=AGENT_DISPLAY_NAME,
    )


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            request_fnc=handle_request,
            prewarm_fnc=prewarm,
            agent_name=AGENT_NAME,
            port=WORKER_HTTP_PORT,
        )
    )
