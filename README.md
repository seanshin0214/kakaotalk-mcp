# KakaoTalk MCP

## World's First KakaoTalk Message Analyzer MCP

카카오톡 대화에서 할일을 추출하는 세계 최초의 MCP (Model Context Protocol) 서버입니다.

---

## Features

### Core Features
- **채팅방 목록 조회** - 모든 카카오톡 채팅방 확인
- **친구/채팅방 검색** - 이름으로 1:1 채팅, 단체 채팅방 검색
- **메시지 조회** - 특정 채팅방의 대화 내용 확인
- **할일 추출** - AI 키워드 기반 할일/요청사항 자동 추출
- **긴급 할일 필터** - 급한 요청만 모아보기

### Supported Methods
1. **EDB 복호화** - PC 카카오톡 로컬 데이터베이스 직접 접근 (고급)
2. **TXT 파싱** - 카카오톡 내보내기 파일 분석 (간편)

---

## Installation

### 1. Clone & Install
```bash
cd C:\Users\sshin\Documents\kakaotalk-mcp
pip install -e .
```

### 2. Dependencies
```bash
pip install mcp pycryptodome chardet
```

---

## MCP Tools

### `kakaotalk_status`
카카오톡 MCP 상태 확인

### `list_chats`
모든 채팅방 목록 조회
```json
{"limit": 20}
```

### `search_chat`
친구 이름 또는 채팅방 이름으로 검색
```json
{"name": "홍길동", "exact": false}
```

### `get_messages`
특정 채팅방 메시지 조회
```json
{"chat_id": "123456789", "limit": 100}
```

### `extract_todos`
특정 채팅방에서 할일 추출
```json
{"chat_id": "123456789", "limit": 500}
```

### `extract_todos_by_name` (핵심 기능)
**친구 이름 또는 채팅방 이름으로 할일 추출**
```json
{"name": "프로젝트팀", "limit": 500}
```

### `search_messages`
키워드로 메시지 검색
```json
{"chat_id": "123456789", "keyword": "회의"}
```

### `get_urgent_todos`
모든 최근 채팅방에서 긴급 할일만 추출
```json
{"chat_limit": 10}
```

---

## Todo Detection Keywords

### 할일 키워드 (Korean)
- 해야, 해줘, 해주세요, 부탁, 요청
- 할 일, 할일, TODO
- 까지, 마감, deadline
- 확인, 검토, 리뷰
- 보내, 전달, 공유
- 작성, 준비, 완료
- 미팅, 회의, 콜
- 연락, 답장, 회신
- 수정, 변경, 업데이트

### 긴급 키워드
- 급, 빨리, ASAP, 긴급
- 오늘, 내일, 당장, 바로, 지금

---

## Configuration

### Claude Desktop
```json
{
  "mcpServers": {
    "kakaotalk": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "C:\\Users\\sshin\\Documents\\kakaotalk-mcp",
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

### Claude Code
```json
{
  "mcpServers": {
    "kakaotalk": {
      "command": "C:\\Users\\sshin\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
      "args": ["-m", "src.server"],
      "cwd": "C:\\Users\\sshin\\Documents\\kakaotalk-mcp",
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

---

## Data Locations

### Windows PC KakaoTalk
- **User Directory**: `%LocalAppData%\Kakao\KakaoTalk\users\{userHash}\`
- **Chat Data**: `chat_data\chatLogs_{chatId}.edb`
- **Chat List**: `chat_data\chatListInfo.edb`
- **User DB**: `TalkUserDB.edb`

### Registry Keys
- **Device Info**: `HKCU\Software\Kakao\KakaoTalk\DeviceInfo\`
- **Network Keys**: `HKLM\System\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\`

---

## Technical Details

### EDB Decryption
- **Encryption**: AES-CBC (4096 byte blocks)
- **Key Generation**: pragma + userId → MD5 hash
- **Pragma**: UUID + ModelName + SerialNumber → AES encrypt → SHA512 → Base64

### References
- [윈도우 카카오톡 DB 복호화 분석](https://blog.system32.kr/304)
- [kdevil2k/Kakaotalk_decDB](https://github.com/kdevil2k/Kakaotalk_decDB)
- [kks00/kakaotalk_msg_hook](https://github.com/kks00/kakaotalk_msg_hook)

---

## License
MIT License

## Author
Created with Claude - World's First KakaoTalk MCP (2024.12.09)
