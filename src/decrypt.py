"""
KakaoTalk EDB Decryption Module
Decrypts chatLogs_*.edb files using AES-CBC
"""
import base64
import hashlib
import sqlite3
import tempfile
import os
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from .registry import get_network_interface_keys, get_kakaotalk_device_info


def generate_pragma(uuid: str, model_name: str, serial_number: str, key: bytes) -> str:
    """
    Generate pragma string for key derivation.
    """
    iv = bytes([0] * 16)
    pragma = f"{uuid}|{model_name}|{serial_number}"
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_pragma = cipher.encrypt(pad(pragma.encode(), AES.block_size))
    hashed_pragma = hashlib.sha512(encrypted_pragma).digest()
    encoded_hashed_pragma = base64.b64encode(hashed_pragma)
    return encoded_hashed_pragma.decode()


def generate_key_and_iv(pragma: str, user_id: str) -> Tuple[bytes, bytes]:
    """
    Generate AES key and IV from pragma and userId.
    """
    key = pragma + user_id
    while len(key) < 512:
        key += key
    key = key[:512]
    key_hash = hashlib.md5(key.encode()).digest()
    iv = hashlib.md5(base64.b64encode(key_hash)).digest()
    return key_hash, iv


def decrypt_database(key: bytes, iv: bytes, enc_db: bytes) -> bytes:
    """
    Decrypt EDB database using AES-CBC with 4096 byte blocks.
    """
    dec_db = b''
    i = 0
    while i < len(enc_db):
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_data = cipher.decrypt(enc_db[i:i+4096])
        dec_db += decrypted_data
        i += 4096
    return dec_db


def verify_sqlite_header(data: bytes) -> bool:
    """
    Check if decrypted data is a valid SQLite database.
    SQLite files start with "SQLite format 3\x00"
    """
    return data[:16] == b'SQLite format 3\x00'


def find_user_id(pragma: str, enc_db: bytes, max_attempts: int = 100000) -> Optional[str]:
    """
    Find the correct userId by brute force.
    Try userId from 1 to max_attempts.
    """
    for user_id in range(1, max_attempts + 1):
        key, iv = generate_key_and_iv(pragma, str(user_id))
        dec_db = decrypt_database(key, iv, enc_db[:4096])  # Only decrypt first block

        if verify_sqlite_header(dec_db):
            return str(user_id)

        if user_id % 10000 == 0:
            print(f"Tried {user_id} userIds...")

    return None


class KakaoDecryptor:
    """
    KakaoTalk EDB file decryptor.
    """

    def __init__(self):
        self.device_info = get_kakaotalk_device_info()
        self.network_keys = get_network_interface_keys()
        self._cached_credentials = None

    def _find_working_credentials(self, enc_db: bytes) -> Optional[Dict]:
        """
        Find working UUID, model, serial, network key, and userId combination.
        """
        if self._cached_credentials:
            return self._cached_credentials

        if not self.device_info:
            print("No device info found in registry")
            return None

        uuid = self.device_info.get("uuid", "")
        model = self.device_info.get("model", "")
        serial = self.device_info.get("serial", "")

        if not all([uuid, model, serial]):
            print("Incomplete device info")
            return None

        # Try each network interface key
        for net_key in self.network_keys:
            key_bytes = bytes.fromhex(net_key)
            if len(key_bytes) != 16:
                continue

            pragma = generate_pragma(uuid, model, serial, key_bytes)

            # Try to find userId (brute force first 50000)
            user_id = find_user_id(pragma, enc_db, max_attempts=50000)

            if user_id:
                self._cached_credentials = {
                    "uuid": uuid,
                    "model": model,
                    "serial": serial,
                    "network_key": net_key,
                    "pragma": pragma,
                    "user_id": user_id,
                }
                return self._cached_credentials

        return None

    def decrypt_file(self, edb_path: str) -> Optional[bytes]:
        """
        Decrypt an EDB file and return the decrypted SQLite database.
        """
        with open(edb_path, 'rb') as f:
            enc_db = f.read()

        creds = self._find_working_credentials(enc_db)
        if not creds:
            print(f"Could not find working credentials for {edb_path}")
            return None

        key, iv = generate_key_and_iv(creds["pragma"], creds["user_id"])
        dec_db = decrypt_database(key, iv, enc_db)

        if not verify_sqlite_header(dec_db):
            print("Decryption failed - invalid SQLite header")
            return None

        return dec_db

    def decrypt_to_temp_file(self, edb_path: str) -> Optional[str]:
        """
        Decrypt EDB file and save to a temporary SQLite file.
        Returns the path to the temp file.
        """
        dec_db = self.decrypt_file(edb_path)
        if not dec_db:
            return None

        # Create temp file
        fd, temp_path = tempfile.mkstemp(suffix='.db')
        os.write(fd, dec_db)
        os.close(fd)

        return temp_path

    def get_messages_from_edb(self, edb_path: str) -> List[Dict]:
        """
        Decrypt EDB file and extract messages.
        """
        temp_path = self.decrypt_to_temp_file(edb_path)
        if not temp_path:
            return []

        try:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()

            # Get table info
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            messages = []

            # Try to find messages table (usually chatLogs or similar)
            for table_name, in tables:
                if 'log' in table_name.lower() or 'message' in table_name.lower():
                    try:
                        cursor.execute(f"SELECT * FROM {table_name} ORDER BY sendAt DESC LIMIT 1000")
                        columns = [desc[0] for desc in cursor.description]

                        for row in cursor.fetchall():
                            msg = dict(zip(columns, row))
                            messages.append(msg)
                    except Exception as e:
                        print(f"Error reading table {table_name}: {e}")

            conn.close()
            return messages

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    decryptor = KakaoDecryptor()
    print(f"Device Info: {decryptor.device_info}")
    print(f"Network Keys: {len(decryptor.network_keys)} found")
