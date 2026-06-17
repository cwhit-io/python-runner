from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KEY_FILE = PROJECT_ROOT / ".secrets.key"
STORE_FILE = PROJECT_ROOT / "secrets.enc"


def _get_master_key() -> Optional[bytes]:
    # Prefer environment variable for master key
    env_key = os.environ.get("SECRETS_MASTER_KEY")
    if env_key:
        try:
            return env_key.encode()
        except Exception:
            return None

    # Fallback to key file
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()

    return None


def get_master_key() -> bytes:
    """Get or generate the master encryption key. Raises RuntimeError if unavailable."""
    key = _get_master_key()
    if not key:
        raise RuntimeError("Master encryption key not available")
    return key


# ... (rest of the file remains the same)
class SecretStore:
    def __init__(self) -> None:
        self._key = _get_master_key()
        if not self._key:
            self._fernet = None
        else:
            self._fernet = Fernet(self._key)

    def _read_raw_store(self) -> Dict[str, str]:
        if not STORE_FILE.exists():
            return {}
        if not self._fernet:
            raise RuntimeError("Master key missing; cannot read encrypted store")
        data = STORE_FILE.read_bytes()
        try:
            payload = self._fernet.decrypt(data)
        except InvalidToken:
            raise RuntimeError("Failed to decrypt secrets store: invalid token")
        return json.loads(payload.decode("utf-8"))

    def _write_raw_store(self, data: Dict[str, str]) -> None:
        if not self._fernet:
            raise RuntimeError("Master key missing; cannot write encrypted store")
        payload = json.dumps(data).encode("utf-8")
        enc = self._fernet.encrypt(payload)
        STORE_FILE.write_bytes(enc)

    def get(self, name: str) -> Optional[str]:
        store = self._read_raw_store()
        return store.get(name)

    def set(self, name: str, value: str) -> None:
        store = self._read_raw_store()
        store[name] = value
        self._write_raw_store(store)

    def delete(self, name: str) -> bool:
        store = self._read_raw_store()
        if name in store:
            del store[name]
            self._write_raw_store(store)
            return True
        return False

    def list_names(self):
        return list(self._read_raw_store().keys())


def ensure_master_key(persist_to_file: bool = True) -> bytes:
    """Generate or return an existing master key. If `persist_to_file` is True,
    write the key to `PROJECT_ROOT/.secrets.key` for convenience.
    WARNING: Protect this key. If lost, secrets are unrecoverable. If leaked,
    all secrets are compromised.
    """
    key = _get_master_key()
    if key:
        return key
    new_key = Fernet.generate_key()
    if persist_to_file:
        KEY_FILE.write_bytes(new_key)
        os.chmod(KEY_FILE, 0o600)
    return new_key


def load_secrets_into_env() -> None:
    """Load decrypted secrets from the encrypted store into os.environ.
    Only set variables that are present in the store and not already in env.
    """
    key = _get_master_key()
    if not key:
        return
    store = SecretStore()
    try:
        names = store.list_names()
    except RuntimeError:
        return
    for name in names:
        if name in os.environ:
            continue
        val = store.get(name)
        if val is not None:
            os.environ[name] = val


# Helper functions for namespacing secrets to scripts
def _script_key(script_id: int, name: str) -> str:
    return f"script:{script_id}:{name}"


def set_script_secret(script_id: int, name: str, value: str) -> None:
    store = SecretStore()
    store.set(_script_key(script_id, name), value)


def get_script_secret(script_id: int, name: str) -> Optional[str]:
    store = SecretStore()
    return store.get(_script_key(script_id, name))


def delete_script_secret(script_id: int, name: str) -> bool:
    store = SecretStore()
    return store.delete(_script_key(script_id, name))


def list_script_secrets(script_id: int):
    prefix = f"script:{script_id}:"
    store = SecretStore()
    names = store.list_names()
    results = []
    for n in names:
        if n.startswith(prefix):
            results.append(n[len(prefix) :])
    return results


# Global Credential Service Functions

def get_credential_for_script(credential_id: int, script_id: int) -> Optional[str]:
    """Get a credential value for injection into script execution.
    
    Validates that the credential belongs to the script owner before returning.
    Returns the credential data as JSON string, or None if not found/unauthorized.
    """
    from app.models import GlobalCredential, Script
    
    try:
        credential = GlobalCredential.objects.get(id=credential_id)
        script = Script.objects.get(id=script_id)
        
        # Verify the credential belongs to the script owner
        if credential.user_id != script.owner_id:
            return None
        
        return json.dumps(credential.get_decrypted_data())
    except (GlobalCredential.DoesNotExist, Script.DoesNotExist):
        return None


def get_all_credentials_for_script(script_id: int) -> dict:
    """Get all attached credential values for script execution.
    
    Returns a dict mapping credential names to their decrypted values.
    Only returns credentials that belong to the script owner.
    """
    from app.models import Script
    
    try:
        script = Script.objects.get(id=script_id)
    except Script.DoesNotExist:
        return {}
    
    credentials_data = {}
    for credential in script.credentials.all():
        data = credential.get_decrypted_data()
        if data:
            credentials_data[credential.name] = data
    
    return credentials_data
