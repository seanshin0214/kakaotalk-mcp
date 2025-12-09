"""
KakaoTalk Export TXT Parser
Parses exported chat history from KakaoTalk app
(Settings > Chat > Export Chat History)

This is a simpler approach that doesn't require decryption!
"""
import re
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class KakaoTxtParser:
    """
    Parser for KakaoTalk exported .txt files.

    KakaoTalk export format (Korean):
    --------------- 2024년 12월 9일 월요일 ---------------
    [홍길동] [오후 2:30] 안녕하세요
    [김철수] [오후 2:31] 네 안녕하세요!

    Or English format:
    --------------- Monday, December 9, 2024 ---------------
    [John] [2:30 PM] Hello
    """

    # Date line pattern (Korean)
    DATE_PATTERN_KR = re.compile(
        r'-+\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*\w+\s*-+'
    )

    # Date line pattern (English)
    DATE_PATTERN_EN = re.compile(
        r'-+\s*\w+,\s*(\w+)\s+(\d{1,2}),\s*(\d{4})\s*-+'
    )

    # Message pattern: [sender] [time] message
    MESSAGE_PATTERN = re.compile(
        r'\[([^\]]+)\]\s*\[([^\]]+)\]\s*(.*)'
    )

    # System message pattern (no sender)
    SYSTEM_PATTERN = re.compile(
        r'^[^\[].+$'
    )

    def __init__(self):
        self.messages = []
        self.participants = set()
        self.chat_name = ""

    def parse_file(self, file_path: str) -> Dict:
        """
        Parse a KakaoTalk export .txt file.
        """
        self.messages = []
        self.participants = set()

        file_path = Path(file_path)
        self.chat_name = file_path.stem

        # Try different encodings
        content = None
        for encoding in ['utf-8', 'cp949', 'euc-kr', 'utf-16']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if content is None:
            return {"error": "Could not decode file"}

        current_date = None
        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for date line
            date_match = self.DATE_PATTERN_KR.match(line)
            if date_match:
                year, month, day = date_match.groups()
                current_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                continue

            date_match_en = self.DATE_PATTERN_EN.match(line)
            if date_match_en:
                month_name, day, year = date_match_en.groups()
                # Convert month name to number
                months = {
                    'January': '01', 'February': '02', 'March': '03',
                    'April': '04', 'May': '05', 'June': '06',
                    'July': '07', 'August': '08', 'September': '09',
                    'October': '10', 'November': '11', 'December': '12'
                }
                month = months.get(month_name, '01')
                current_date = f"{year}-{month}-{day.zfill(2)}"
                continue

            # Check for message
            msg_match = self.MESSAGE_PATTERN.match(line)
            if msg_match:
                sender, time_str, content = msg_match.groups()
                self.participants.add(sender)

                self.messages.append({
                    "sender": sender,
                    "time": time_str,
                    "date": current_date,
                    "content": content,
                    "raw": line,
                })

        return {
            "chat_name": self.chat_name,
            "file_path": str(file_path),
            "total_messages": len(self.messages),
            "participants": list(self.participants),
            "messages": self.messages,
        }

    def extract_todos(self, messages: List[Dict] = None) -> List[Dict]:
        """
        Extract todos from parsed messages.
        """
        if messages is None:
            messages = self.messages

        # Todo keywords
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
            "처리", "진행", "완료해",
        ]

        URGENT_KEYWORDS = [
            "급", "빨리", "ASAP", "asap", "긴급",
            "오늘", "내일", "당장", "바로", "지금",
        ]

        todos = []

        for msg in messages:
            content = msg.get("content", "")
            if not content:
                continue

            # Check for todo keywords
            matched_keywords = [kw for kw in TODO_KEYWORDS if kw in content]

            if not matched_keywords:
                continue

            # Check urgency
            is_urgent = any(kw in content for kw in URGENT_KEYWORDS)

            todos.append({
                "content": content,
                "sender": msg.get("sender", "Unknown"),
                "date": msg.get("date", ""),
                "time": msg.get("time", ""),
                "is_urgent": is_urgent,
                "keywords": matched_keywords,
            })

        return todos

    def get_messages_by_sender(self, sender: str) -> List[Dict]:
        """
        Get all messages from a specific sender.
        """
        return [m for m in self.messages if m.get("sender") == sender]

    def search_messages(self, keyword: str) -> List[Dict]:
        """
        Search messages by keyword.
        """
        keyword_lower = keyword.lower()
        return [
            m for m in self.messages
            if keyword_lower in m.get("content", "").lower()
        ]


def scan_export_folder(folder_path: str) -> List[Dict]:
    """
    Scan a folder for KakaoTalk export .txt files.
    """
    folder = Path(folder_path)
    if not folder.exists():
        return []

    txt_files = []

    # Look for KakaoTalk export files
    for file in folder.glob("*.txt"):
        # KakaoTalk exports usually have specific naming patterns
        txt_files.append({
            "path": str(file),
            "name": file.stem,
            "size": file.stat().st_size,
            "modified": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
        })

    return txt_files


if __name__ == "__main__":
    # Test the parser
    parser = KakaoTxtParser()

    # Example: parse an exported file
    test_content = """
카카오톡 대화 - 테스트 채팅방

--------------- 2024년 12월 9일 월요일 ---------------
[홍길동] [오후 2:30] 안녕하세요
[김철수] [오후 2:31] 네 안녕하세요!
[홍길동] [오후 2:35] 오늘 회의 자료 정리 부탁드려요
[김철수] [오후 2:36] 네, 저녁까지 보내드릴게요
[홍길동] [오후 2:40] 급한건데 오늘 6시까지 해주세요
    """.strip()

    # Write test file
    test_path = Path("test_kakao.txt")
    test_path.write_text(test_content, encoding='utf-8')

    result = parser.parse_file(str(test_path))
    print(f"Parsed {result['total_messages']} messages")
    print(f"Participants: {result['participants']}")

    todos = parser.extract_todos()
    print(f"\nFound {len(todos)} todos:")
    for todo in todos:
        urgent = "[URGENT]" if todo['is_urgent'] else ""
        print(f"  {urgent} [{todo['sender']}] {todo['content']}")

    # Cleanup
    test_path.unlink()
