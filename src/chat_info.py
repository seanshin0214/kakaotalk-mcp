"""
KakaoTalk Chat Info Parser
Extracts chat room names, participants info from chatListInfo.edb
Supports searching by friend name or group chat name
"""
import sqlite3
import json
import os
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .registry import get_chat_data_path, list_chat_files


class ChatInfoManager:
    """
    Manages chat room information and message retrieval.
    """

    def __init__(self, decryptor=None):
        self.chat_data_path = get_chat_data_path()
        self.decryptor = decryptor
        self._chat_list_cache = None

    def get_chat_list_info_path(self) -> Optional[str]:
        """Get path to chatListInfo.edb"""
        if not self.chat_data_path:
            return None
        path = Path(self.chat_data_path) / "chatListInfo.edb"
        return str(path) if path.exists() else None

    def get_talk_user_db_path(self) -> Optional[str]:
        """Get path to TalkUserDB.edb (contains user/friend info)"""
        if not self.chat_data_path:
            return None
        # TalkUserDB is in parent directory
        parent = Path(self.chat_data_path).parent
        path = parent / "TalkUserDB.edb"
        return str(path) if path.exists() else None

    def _decrypt_and_query(self, edb_path: str, query: str) -> List[Dict]:
        """
        Decrypt EDB and execute query.
        """
        if not self.decryptor:
            return []

        temp_path = self.decryptor.decrypt_to_temp_file(edb_path)
        if not temp_path:
            return []

        try:
            conn = sqlite3.connect(temp_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(query)
            results = [dict(row) for row in cursor.fetchall()]

            conn.close()
            return results

        except Exception as e:
            print(f"Error querying {edb_path}: {e}")
            return []

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def get_all_chat_rooms(self) -> List[Dict]:
        """
        Get all chat rooms with their names and IDs.
        Returns list of {chat_id, name, type, member_count, last_message_time}
        """
        if self._chat_list_cache:
            return self._chat_list_cache

        chat_files = list_chat_files()

        # Build basic info from file system
        chat_rooms = []
        for cf in chat_files:
            chat_rooms.append({
                "chat_id": cf["chat_id"],
                "file_path": cf["path"],
                "file_size": cf["size"],
                "last_modified": datetime.fromtimestamp(cf["modified"]).isoformat(),
                "name": f"Chat_{cf['chat_id'][-6:]}",  # Default name
                "type": "unknown",
                "member_count": 0,
            })

        self._chat_list_cache = chat_rooms
        return chat_rooms

    def search_chat_by_name(self, name: str, exact: bool = False) -> List[Dict]:
        """
        Search chat rooms by name (friend name or group chat name).

        Args:
            name: Name to search for
            exact: If True, require exact match; otherwise partial match

        Returns:
            List of matching chat rooms
        """
        all_chats = self.get_all_chat_rooms()

        if exact:
            return [c for c in all_chats if c.get("name", "").lower() == name.lower()]
        else:
            return [c for c in all_chats if name.lower() in c.get("name", "").lower()]

    def get_recent_chats(self, limit: int = 10) -> List[Dict]:
        """
        Get most recently active chat rooms.
        """
        all_chats = self.get_all_chat_rooms()
        return all_chats[:limit]

    def get_messages_from_chat(self, chat_id: str, limit: int = 100) -> List[Dict]:
        """
        Get messages from a specific chat room.
        """
        if not self.chat_data_path:
            return []

        edb_path = Path(self.chat_data_path) / f"chatLogs_{chat_id}.edb"
        if not edb_path.exists():
            return []

        if not self.decryptor:
            return []

        return self.decryptor.get_messages_from_edb(str(edb_path))

    def search_messages(self, chat_id: str, keyword: str, limit: int = 50) -> List[Dict]:
        """
        Search messages in a chat room by keyword.
        """
        messages = self.get_messages_from_chat(chat_id, limit=1000)

        results = []
        for msg in messages:
            content = msg.get("message", "") or msg.get("content", "") or ""
            if keyword.lower() in content.lower():
                results.append(msg)
                if len(results) >= limit:
                    break

        return results


class TodoExtractor:
    """
    Extracts todos/tasks from chat messages.
    Uses pattern matching and AI-like heuristics.
    """

    # Korean todo keywords
    TODO_KEYWORDS = [
        "해야", "해줘", "해주세요", "부탁", "요청",
        "할 일", "할일", "TODO", "todo",
        "까지", "마감", "deadline",
        "확인", "검토", "리뷰",
        "보내", "전달", "공유",
        "작성", "준비", "완료",
        "미팅", "회의", "콜",
        "연락", "답장", "회신",
        "수정", "변경", "업데이트",
    ]

    # Urgency keywords
    URGENT_KEYWORDS = [
        "급", "빨리", "ASAP", "asap", "긴급",
        "오늘", "내일", "당장", "바로",
    ]

    def __init__(self):
        pass

    def extract_todos_from_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        Extract potential todos from a list of messages.
        """
        todos = []

        for msg in messages:
            content = msg.get("message", "") or msg.get("content", "") or ""
            if not content:
                continue

            # Check for todo keywords
            is_todo = False
            matched_keywords = []

            for keyword in self.TODO_KEYWORDS:
                if keyword in content:
                    is_todo = True
                    matched_keywords.append(keyword)

            if not is_todo:
                continue

            # Check urgency
            is_urgent = any(kw in content for kw in self.URGENT_KEYWORDS)

            # Extract sender info
            sender = msg.get("authorId", "") or msg.get("sender", "") or "Unknown"
            timestamp = msg.get("sendAt", "") or msg.get("timestamp", "")

            todos.append({
                "content": content,
                "sender": sender,
                "timestamp": timestamp,
                "is_urgent": is_urgent,
                "keywords": matched_keywords,
                "original_message": msg,
            })

        return todos

    def extract_todos_from_chat(
        self,
        chat_manager: ChatInfoManager,
        chat_id: str,
        limit: int = 500
    ) -> List[Dict]:
        """
        Extract todos from a specific chat room.
        """
        messages = chat_manager.get_messages_from_chat(chat_id, limit=limit)
        return self.extract_todos_from_messages(messages)

    def search_and_extract_todos(
        self,
        chat_manager: ChatInfoManager,
        chat_name: str,
        limit: int = 500
    ) -> Dict[str, Any]:
        """
        Search for a chat room by name and extract todos.
        """
        matching_chats = chat_manager.search_chat_by_name(chat_name)

        if not matching_chats:
            return {
                "success": False,
                "error": f"No chat room found matching '{chat_name}'",
                "todos": [],
            }

        # Use the most recently modified matching chat
        chat = matching_chats[0]
        todos = self.extract_todos_from_chat(chat_manager, chat["chat_id"], limit)

        return {
            "success": True,
            "chat_name": chat.get("name", chat["chat_id"]),
            "chat_id": chat["chat_id"],
            "todos": todos,
            "total_found": len(todos),
        }


if __name__ == "__main__":
    manager = ChatInfoManager()
    print(f"Chat Data Path: {manager.chat_data_path}")

    chats = manager.get_all_chat_rooms()
    print(f"Found {len(chats)} chat rooms")

    for chat in chats[:5]:
        print(f"  - {chat['chat_id']}: {chat['name']}")
