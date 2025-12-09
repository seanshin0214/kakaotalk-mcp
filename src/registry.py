"""
KakaoTalk Registry Info Extractor
Extracts UUID, ModelName, SerialNumber from Windows Registry
"""
import winreg
import os
import sys
from typing import Optional, Dict, List
from pathlib import Path


def get_kakaotalk_device_info() -> Optional[Dict[str, str]]:
    """
    Get KakaoTalk device info from registry.
    Location: HKEY_CURRENT_USER\\Software\\Kakao\\KakaoTalk\\DeviceInfo\\{timestamp}
    """
    try:
        base_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Kakao\KakaoTalk\DeviceInfo"
        )

        # Find the timestamp subfolder
        i = 0
        device_key_name = None
        while True:
            try:
                subkey_name = winreg.EnumKey(base_key, i)
                device_key_name = subkey_name
                break
            except OSError:
                break
            i += 1

        if not device_key_name:
            return None

        device_key = winreg.OpenKey(base_key, device_key_name)

        # Read values
        result = {"device_key": device_key_name}

        try:
            uuid_value, _ = winreg.QueryValueEx(device_key, "sys_uuid")
            result["uuid"] = uuid_value
        except FileNotFoundError:
            pass

        try:
            model_value, _ = winreg.QueryValueEx(device_key, "hdd_model")
            result["model"] = model_value
        except FileNotFoundError:
            pass

        try:
            serial_value, _ = winreg.QueryValueEx(device_key, "hdd_serial")
            result["serial"] = serial_value
        except FileNotFoundError:
            pass

        winreg.CloseKey(device_key)
        winreg.CloseKey(base_key)

        return result

    except Exception as e:
        print(f"Error reading registry: {e}", file=sys.stderr)
        return None


def get_network_interface_keys() -> List[str]:
    """
    Get network interface GUIDs from registry.
    These are used to generate the encryption key.
    Location: HKLM\\System\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces
    """
    keys = []
    try:
        base_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"System\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
        )

        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(base_key, i)
                # Remove curly braces and dashes
                clean_key = subkey_name.replace("{", "").replace("}", "").replace("-", "")
                keys.append(clean_key)
                i += 1
            except OSError:
                break

        winreg.CloseKey(base_key)

    except Exception as e:
        print(f"Error reading network interfaces: {e}", file=sys.stderr)

    return keys


def get_kakaotalk_user_dir() -> Optional[str]:
    """
    Get the KakaoTalk user directory path.
    Location: %LocalAppData%\\Kakao\\KakaoTalk\\users\\{userDir}
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return None

    kakao_users_path = Path(local_appdata) / "Kakao" / "KakaoTalk" / "users"

    if not kakao_users_path.exists():
        return None

    # Find user directory (there should be one hash-named folder)
    for item in kakao_users_path.iterdir():
        if item.is_dir() and len(item.name) == 40:  # SHA1 hash length
            return str(item)

    return None


def get_chat_data_path() -> Optional[str]:
    """
    Get the chat_data directory path.
    """
    user_dir = get_kakaotalk_user_dir()
    if not user_dir:
        return None

    chat_data_path = Path(user_dir) / "chat_data"
    if chat_data_path.exists():
        return str(chat_data_path)

    return None


def list_chat_files() -> List[Dict[str, any]]:
    """
    List all chatLogs_*.edb files with their info.
    """
    chat_data = get_chat_data_path()
    if not chat_data:
        return []

    chat_files = []
    chat_data_path = Path(chat_data)

    for file in chat_data_path.glob("chatLogs_*.edb"):
        # Skip WAL and SHM files
        if file.suffix in [".edb-wal", ".edb-shm"]:
            continue
        if "-wal" in file.name or "-shm" in file.name:
            continue

        chat_id = file.stem.replace("chatLogs_", "")
        stat = file.stat()

        chat_files.append({
            "path": str(file),
            "chat_id": chat_id,
            "size": stat.st_size,
            "modified": stat.st_mtime,
        })

    # Sort by modification time (most recent first)
    chat_files.sort(key=lambda x: x["modified"], reverse=True)

    return chat_files


if __name__ == "__main__":
    print("=== KakaoTalk Registry Info ===")

    device_info = get_kakaotalk_device_info()
    print(f"Device Info: {device_info}")

    network_keys = get_network_interface_keys()
    print(f"Network Interface Keys: {len(network_keys)} found")
    for key in network_keys[:5]:
        print(f"  - {key}")

    user_dir = get_kakaotalk_user_dir()
    print(f"User Directory: {user_dir}")

    chat_files = list_chat_files()
    print(f"Chat Files: {len(chat_files)} found")
    for cf in chat_files[:5]:
        print(f"  - {cf['chat_id']}: {cf['size']} bytes")
