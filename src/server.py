"""
KakaoTalk MCP Server
World's First KakaoTalk Message Analyzer MCP
Extract todos from KakaoTalk conversations by friend name or chat room name
"""
import asyncio
import json
from datetime import datetime
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    EmbeddedResource,
)

from .registry import (
    get_kakaotalk_user_dir,
    get_chat_data_path,
    list_chat_files,
    get_kakaotalk_device_info,
)
from .chat_info import ChatInfoManager, TodoExtractor
from .decrypt import KakaoDecryptor


# Initialize server
app = Server("kakaotalk-mcp")

# Global instances (lazy initialization)
_decryptor = None
_chat_manager = None
_todo_extractor = None


def get_decryptor():
    global _decryptor
    if _decryptor is None:
        _decryptor = KakaoDecryptor()
    return _decryptor


def get_chat_manager():
    global _chat_manager
    if _chat_manager is None:
        _chat_manager = ChatInfoManager(decryptor=get_decryptor())
    return _chat_manager


def get_todo_extractor():
    global _todo_extractor
    if _todo_extractor is None:
        _todo_extractor = TodoExtractor()
    return _todo_extractor


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available KakaoTalk tools."""
    return [
        Tool(
            name="kakaotalk_status",
            description="카카오톡 MCP 상태 확인. KakaoTalk 설치 여부, 채팅방 개수 등 기본 정보 확인",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_chats",
            description="모든 카카오톡 채팅방 목록 조회. 최근 활동 순으로 정렬됨",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "가져올 채팅방 개수 (기본: 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="search_chat",
            description="친구 이름 또는 채팅방 이름으로 검색. 1:1 채팅, 단체 채팅방 모두 검색 가능",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "검색할 친구 이름 또는 채팅방 이름",
                    },
                    "exact": {
                        "type": "boolean",
                        "description": "정확히 일치하는 이름만 검색 (기본: false)",
                        "default": False,
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="get_messages",
            description="특정 채팅방의 메시지 조회",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "채팅방 ID",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "가져올 메시지 개수 (기본: 100)",
                        "default": 100,
                    },
                },
                "required": ["chat_id"],
            },
        ),
        Tool(
            name="extract_todos",
            description="특정 채팅방에서 할일/요청사항 추출. 키워드 기반으로 '해줘', '부탁', '마감' 등의 메시지 찾기",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "채팅방 ID",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "분석할 최근 메시지 개수 (기본: 500)",
                        "default": 500,
                    },
                },
                "required": ["chat_id"],
            },
        ),
        Tool(
            name="extract_todos_by_name",
            description="친구 이름 또는 채팅방 이름으로 검색하여 할일 추출. 예: '홍길동' 또는 '프로젝트팀' 입력하면 해당 채팅방에서 할일 추출",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "친구 이름 또는 채팅방 이름",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "분석할 최근 메시지 개수 (기본: 500)",
                        "default": 500,
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="search_messages",
            description="특정 채팅방에서 키워드로 메시지 검색",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "채팅방 ID",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "검색할 키워드",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "최대 결과 개수 (기본: 50)",
                        "default": 50,
                    },
                },
                "required": ["chat_id", "keyword"],
            },
        ),
        Tool(
            name="get_urgent_todos",
            description="모든 최근 채팅방에서 긴급 할일만 추출. '급', '오늘', 'ASAP' 등 긴급 키워드 포함된 요청 찾기",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_limit": {
                        "type": "integer",
                        "description": "확인할 최근 채팅방 개수 (기본: 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle tool calls."""

    try:
        if name == "kakaotalk_status":
            return await handle_status()

        elif name == "list_chats":
            limit = arguments.get("limit", 20)
            return await handle_list_chats(limit)

        elif name == "search_chat":
            chat_name = arguments.get("name", "")
            exact = arguments.get("exact", False)
            return await handle_search_chat(chat_name, exact)

        elif name == "get_messages":
            chat_id = arguments.get("chat_id", "")
            limit = arguments.get("limit", 100)
            return await handle_get_messages(chat_id, limit)

        elif name == "extract_todos":
            chat_id = arguments.get("chat_id", "")
            limit = arguments.get("limit", 500)
            return await handle_extract_todos(chat_id, limit)

        elif name == "extract_todos_by_name":
            chat_name = arguments.get("name", "")
            limit = arguments.get("limit", 500)
            return await handle_extract_todos_by_name(chat_name, limit)

        elif name == "search_messages":
            chat_id = arguments.get("chat_id", "")
            keyword = arguments.get("keyword", "")
            limit = arguments.get("limit", 50)
            return await handle_search_messages(chat_id, keyword, limit)

        elif name == "get_urgent_todos":
            chat_limit = arguments.get("chat_limit", 10)
            return await handle_get_urgent_todos(chat_limit)

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_status() -> Sequence[TextContent]:
    """Check KakaoTalk MCP status."""
    user_dir = get_kakaotalk_user_dir()
    chat_data = get_chat_data_path()
    chat_files = list_chat_files()
    device_info = get_kakaotalk_device_info()

    status = {
        "mcp_name": "KakaoTalk MCP",
        "version": "1.0.0",
        "description": "World's First KakaoTalk Message Analyzer",
        "kakaotalk_installed": user_dir is not None,
        "user_directory": user_dir,
        "chat_data_path": chat_data,
        "total_chat_rooms": len(chat_files),
        "device_info_found": device_info is not None,
    }

    return [TextContent(
        type="text",
        text=json.dumps(status, ensure_ascii=False, indent=2)
    )]


async def handle_list_chats(limit: int) -> Sequence[TextContent]:
    """List chat rooms."""
    manager = get_chat_manager()
    chats = manager.get_recent_chats(limit)

    result = {
        "total": len(chats),
        "chats": chats,
    }

    return [TextContent(
        type="text",
        text=json.dumps(result, ensure_ascii=False, indent=2)
    )]


async def handle_search_chat(name: str, exact: bool) -> Sequence[TextContent]:
    """Search chat rooms by name."""
    manager = get_chat_manager()
    results = manager.search_chat_by_name(name, exact)

    return [TextContent(
        type="text",
        text=json.dumps({
            "query": name,
            "exact_match": exact,
            "found": len(results),
            "results": results,
        }, ensure_ascii=False, indent=2)
    )]


async def handle_get_messages(chat_id: str, limit: int) -> Sequence[TextContent]:
    """Get messages from a chat room."""
    manager = get_chat_manager()
    messages = manager.get_messages_from_chat(chat_id, limit)

    return [TextContent(
        type="text",
        text=json.dumps({
            "chat_id": chat_id,
            "message_count": len(messages),
            "messages": messages[:limit],
        }, ensure_ascii=False, indent=2)
    )]


async def handle_extract_todos(chat_id: str, limit: int) -> Sequence[TextContent]:
    """Extract todos from a chat room."""
    manager = get_chat_manager()
    extractor = get_todo_extractor()

    todos = extractor.extract_todos_from_chat(manager, chat_id, limit)

    # Separate urgent and normal todos
    urgent = [t for t in todos if t.get("is_urgent")]
    normal = [t for t in todos if not t.get("is_urgent")]

    return [TextContent(
        type="text",
        text=json.dumps({
            "chat_id": chat_id,
            "total_todos": len(todos),
            "urgent_count": len(urgent),
            "normal_count": len(normal),
            "urgent_todos": urgent,
            "normal_todos": normal,
        }, ensure_ascii=False, indent=2)
    )]


async def handle_extract_todos_by_name(name: str, limit: int) -> Sequence[TextContent]:
    """Search chat by name and extract todos."""
    manager = get_chat_manager()
    extractor = get_todo_extractor()

    result = extractor.search_and_extract_todos(manager, name, limit)

    if result.get("success"):
        todos = result.get("todos", [])
        urgent = [t for t in todos if t.get("is_urgent")]
        normal = [t for t in todos if not t.get("is_urgent")]

        result["urgent_count"] = len(urgent)
        result["normal_count"] = len(normal)
        result["urgent_todos"] = urgent
        result["normal_todos"] = normal

    return [TextContent(
        type="text",
        text=json.dumps(result, ensure_ascii=False, indent=2)
    )]


async def handle_search_messages(chat_id: str, keyword: str, limit: int) -> Sequence[TextContent]:
    """Search messages by keyword."""
    manager = get_chat_manager()
    results = manager.search_messages(chat_id, keyword, limit)

    return [TextContent(
        type="text",
        text=json.dumps({
            "chat_id": chat_id,
            "keyword": keyword,
            "found": len(results),
            "messages": results,
        }, ensure_ascii=False, indent=2)
    )]


async def handle_get_urgent_todos(chat_limit: int) -> Sequence[TextContent]:
    """Get urgent todos from recent chats."""
    manager = get_chat_manager()
    extractor = get_todo_extractor()

    recent_chats = manager.get_recent_chats(chat_limit)
    all_urgent = []

    for chat in recent_chats:
        todos = extractor.extract_todos_from_chat(manager, chat["chat_id"], limit=200)
        urgent = [t for t in todos if t.get("is_urgent")]

        for todo in urgent:
            todo["chat_name"] = chat.get("name", chat["chat_id"])
            todo["chat_id"] = chat["chat_id"]
            all_urgent.append(todo)

    # Sort by timestamp (most recent first)
    all_urgent.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return [TextContent(
        type="text",
        text=json.dumps({
            "chats_checked": chat_limit,
            "total_urgent": len(all_urgent),
            "urgent_todos": all_urgent,
        }, ensure_ascii=False, indent=2)
    )]


async def main():
    """Main entry point."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
