"""Streamable-HTTP MCP server endpoint for external integrations (Thổ Thần Skill).

Implements just enough of the Model Context Protocol (spec 2025-03) over a
single POST endpoint, returning plain JSON responses (no SSE) so that
clients like LobeChat that disable SSE can still talk to it.

Exposed tools:
- create_meeting_room(purpose?, access_level?)  → returns the room URL.
- add_agent_to_meeting(room, metadata?)         → dispatches an external
  LiveKit agent worker (registered name = settings.MCP_DEFAULT_AGENT_NAME)
  into the room. The agent must already be running and connected to
  LiveKit; otherwise the dispatch is queued and times out.
"""

from logging import getLogger

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import ValidationError
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest

from rest_framework import permissions as drf_permissions
from rest_framework.decorators import (
    api_view,
    permission_classes,
    renderer_classes,
)
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from core import models, utils
from transcription import services as transcription_services

logger = getLogger(__name__)

MCP_PROTOCOL_VERSION = "2025-03-26"
MCP_SERVER_NAME = "meet-mcp"
MCP_SERVER_VERSION = "0.3.0"

TOOL_CREATE_MEETING_ROOM = "create_meeting_room"
TOOL_ADD_AGENT_TO_MEETING = "add_agent_to_meeting"
TOOL_LIST_MEETINGS = "list_meetings"
TOOL_GET_MEETING_TRANSCRIPT = "get_meeting_transcript"

DEFAULT_AGENT_NAME = getattr(settings, "MCP_DEFAULT_AGENT_NAME", "appota-bot")


def _parse_iso(value):
    """Lenient ISO-8601 parser. Returns None for empty input, raises on bad."""
    if not value:
        return None
    from datetime import datetime  # local: keeps import cost off cold path

    text = value.rstrip("Z")  # `fromisoformat` doesn't grok the trailing Z
    return datetime.fromisoformat(text)

TOOLS = [
    {
        "name": TOOL_CREATE_MEETING_ROOM,
        "description": (
            "Tạo một phòng họp Meet mới và trả về URL để chia sẻ với người tham gia. "
            "Dùng khi user muốn lên lịch họp, phỏng vấn, hoặc tạo cuộc gọi."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "purpose": {
                    "type": "string",
                    "description": (
                        "Mục đích cuộc họp (tự do, ví dụ: 'Phỏng vấn BE Python'). "
                        "Chỉ để log/tham khảo, không ảnh hưởng kỹ thuật."
                    ),
                },
                "access_level": {
                    "type": "string",
                    "enum": ["public", "trusted", "restricted"],
                    "default": "public",
                    "description": (
                        "public = ai có link cũng vào được; "
                        "trusted = phải đăng nhập Meet; "
                        "restricted = host phải duyệt từng người."
                    ),
                },
            },
        },
    },
    {
        "name": TOOL_ADD_AGENT_TO_MEETING,
        "description": (
            "Triệu hồi agent AI (bot) vào một phòng họp Meet đã tồn tại. "
            "Dùng khi user muốn 'thêm bot', 'thêm trợ lý AI', hoặc 'ghi lại cuộc họp'."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["room"],
            "properties": {
                "room": {
                    "type": "string",
                    "description": (
                        "Định danh phòng: slug (ví dụ 'abc-def-ghi') hoặc UUID. "
                        "Cả hai đều được chấp nhận."
                    ),
                },
                "agent_name": {
                    "type": "string",
                    "description": (
                        "Tên agent đã đăng ký với LiveKit. "
                        f"Bỏ trống để dùng mặc định: '{DEFAULT_AGENT_NAME}'."
                    ),
                },
                "metadata": {
                    "type": "string",
                    "description": (
                        "Chuỗi tùy ý truyền cho agent qua job.metadata "
                        "(ví dụ JSON config persona/instructions). Optional."
                    ),
                },
            },
        },
    },
    {
        "name": TOOL_LIST_MEETINGS,
        "description": (
            "Liệt kê các cuộc họp gần đây mà user có quyền truy cập, kèm số "
            "câu transcript đã ghi và thời điểm hoạt động cuối. Dùng khi "
            "user hỏi 'cuộc họp nào đã ghi', 'meeting nào có transcript'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Số phòng tối đa trả về (1-100).",
                },
                "since": {
                    "type": "string",
                    "description": (
                        "ISO-8601 timestamp. Chỉ trả phòng có hoạt động "
                        "transcript sau thời điểm này."
                    ),
                },
            },
        },
    },
    {
        "name": TOOL_GET_MEETING_TRANSCRIPT,
        "description": (
            "Lấy toàn bộ transcript của một phòng họp theo thứ tự thời gian, "
            "kèm tên người nói. Dùng khi user hỏi 'ai đã nói gì trong họp X', "
            "'transcript phòng abc-def', hoặc muốn summarize cuộc họp."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["room"],
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Slug hoặc UUID của phòng.",
                },
                "since": {
                    "type": "string",
                    "description": "ISO-8601 — chỉ lấy utterance từ thời điểm này.",
                },
                "until": {
                    "type": "string",
                    "description": "ISO-8601 — chỉ lấy utterance đến thời điểm này.",
                },
                "include_partial": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "true để lấy cả interim drafts (nhiễu nhưng realtime); "
                        "false (mặc định) chỉ trả final."
                    ),
                },
            },
        },
    },
]


def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _text_content(text):
    return {"content": [{"type": "text", "text": text}]}


def _resolve_room(room_ref: str):
    """Look up a room by UUID first, then by slug. Returns the Room or None."""
    if not room_ref:
        return None
    qs = models.Room.objects.all()
    try:
        return qs.get(id=room_ref)
    except (models.Room.DoesNotExist, ValueError, ValidationError):
        # ValidationError handles non-UUID strings passed to UUID lookup.
        pass
    return qs.filter(slug=room_ref).first()


def _create_room(user, purpose=None, access_level=None):
    """Mirror external_api.serializers.RoomSerializer.create() but minimal."""

    valid_levels = {choice[0] for choice in models.RoomAccessLevel.choices}
    if access_level not in valid_levels:
        access_level = "public"

    room = models.Room.objects.create(
        name=utils.generate_room_slug(),
        access_level=access_level,
        configuration={},
    )
    models.ResourceAccess.objects.create(
        resource=room,
        user=user,
        role=models.RoleChoices.OWNER,
    )

    base = (settings.APPLICATION_BASE_URL or "").rstrip("/")
    url = f"{base}/{room.slug}" if base else f"/{room.slug}"

    logger.info(
        "MCP create_meeting_room: user=%s room=%s purpose=%r",
        user.id,
        room.id,
        purpose,
    )
    return {
        "room_id": str(room.id),
        "slug": room.slug,
        "url": url,
        "access_level": room.access_level,
    }


@async_to_sync
async def _dispatch_agent(agent_name: str, room_id: str, metadata: str) -> str:
    """Ask LiveKit to dispatch an agent worker into the room.

    Returns the dispatch id on success. Raises on failure — caller catches.
    """
    lkapi = utils.create_livekit_client()
    try:
        response = await lkapi.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                agent_name=agent_name,
                room=room_id,
                metadata=metadata or "",
            )
        )
        return getattr(response, "id", "")
    finally:
        await lkapi.aclose()


def _add_agent(user, room_ref: str, agent_name: str, metadata: str):
    """Resolve room, check user can access it, dispatch."""

    room = _resolve_room(room_ref)
    if room is None:
        return None, f"Không tìm thấy phòng: {room_ref!r}"

    # User must have any role on the room (owner, admin, member). Mirrors
    # has_any_role used elsewhere for safe room operations.
    if not room.has_any_role(user):
        return None, f"Bạn không có quyền với phòng {room.slug}"

    target_agent = (agent_name or DEFAULT_AGENT_NAME).strip()
    md = metadata or ""

    try:
        dispatch_id = _dispatch_agent(target_agent, str(room.id), md)
    except Exception as exc:  # pragma: no cover - logged & surfaced
        logger.exception(
            "MCP add_agent_to_meeting failed: room=%s agent=%s",
            room.id,
            target_agent,
        )
        return None, f"Dispatch agent thất bại: {exc}"

    logger.info(
        "MCP add_agent_to_meeting: user=%s room=%s agent=%s dispatch=%s",
        user.id,
        room.id,
        target_agent,
        dispatch_id,
    )
    return {
        "room_id": str(room.id),
        "slug": room.slug,
        "agent_name": target_agent,
        "dispatch_id": dispatch_id,
    }, None


@api_view(["POST"])
@permission_classes([drf_permissions.IsAuthenticated])
@renderer_classes([JSONRenderer])
def mcp_endpoint(request):
    """Single-shot JSON-RPC handler. Auth via PAT in Authorization header."""

    body = request.data or {}
    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    if method == "initialize":
        return Response(
            _ok(
                req_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": MCP_SERVER_NAME,
                        "version": MCP_SERVER_VERSION,
                    },
                },
            )
        )

    if method == "tools/list":
        return Response(_ok(req_id, {"tools": TOOLS}))

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == TOOL_CREATE_MEETING_ROOM:
            result = _create_room(
                request.user,
                purpose=args.get("purpose"),
                access_level=args.get("access_level", "public"),
            )
            text = (
                f"Phòng đã tạo: {result['url']}\n"
                f"Room ID: {result['room_id']}\n"
                f"Quyền truy cập: {result['access_level']}\n"
                "Gửi link cho người tham gia."
            )
            payload = _text_content(text)
            payload["structuredContent"] = result
            return Response(_ok(req_id, payload))

        if name == TOOL_ADD_AGENT_TO_MEETING:
            result, err = _add_agent(
                request.user,
                room_ref=args.get("room") or "",
                agent_name=args.get("agent_name") or "",
                metadata=args.get("metadata") or "",
            )
            if err:
                return Response(_err(req_id, -32000, err))
            text = (
                f"Agent '{result['agent_name']}' đã được triệu hồi vào phòng "
                f"{result['slug']}.\nDispatch ID: {result['dispatch_id']}"
            )
            payload = _text_content(text)
            payload["structuredContent"] = result
            return Response(_ok(req_id, payload))

        if name == TOOL_LIST_MEETINGS:
            try:
                since = _parse_iso(args.get("since"))
            except ValueError:
                return Response(
                    _err(req_id, -32602, "`since` must be ISO-8601.")
                )
            meetings = transcription_services.list_meetings(
                request.user,
                limit=int(args.get("limit") or 20),
                since=since,
            )
            text_lines = [f"{len(meetings)} cuộc họp:"]
            for m in meetings[:10]:
                last = m["last_utterance_at"] or "—"
                text_lines.append(
                    f"  • {m['slug']} · {m['utterance_count']} câu · last: {last}"
                )
            payload = _text_content("\n".join(text_lines))
            payload["structuredContent"] = {"meetings": meetings}
            return Response(_ok(req_id, payload))

        if name == TOOL_GET_MEETING_TRANSCRIPT:
            room_ref = args.get("room") or ""
            if not room_ref:
                return Response(_err(req_id, -32602, "`room` is required."))
            try:
                since = _parse_iso(args.get("since"))
                until = _parse_iso(args.get("until"))
            except ValueError:
                return Response(
                    _err(req_id, -32602, "`since`/`until` must be ISO-8601.")
                )

            utterances = transcription_services.get_meeting_transcript(
                request.user,
                room_ref=room_ref,
                since=since,
                until=until,
                include_partial=bool(args.get("include_partial")),
            )
            if utterances is None:
                return Response(
                    _err(
                        req_id,
                        -32000,
                        f"Không tìm thấy phòng hoặc không có quyền: {room_ref!r}",
                    )
                )

            text = (
                f"{len(utterances)} utterance cho phòng {room_ref}."
                if utterances
                else f"Phòng {room_ref} chưa có transcript nào."
            )
            payload = _text_content(text)
            payload["structuredContent"] = {
                "room": room_ref,
                "utterances": utterances,
            }
            return Response(_ok(req_id, payload))

        return Response(_err(req_id, -32601, f"Unknown tool: {name}"))

    # MCP notifications (no id) — ack with empty 200
    if req_id is None:
        return Response(status=204)

    return Response(_err(req_id, -32601, f"Unknown method: {method}"))
