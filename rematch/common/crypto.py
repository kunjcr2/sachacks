"""Central AES-GCM vault. Keys never enter SQLite; ownership is authenticated."""
import base64
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class Vault:
    def __init__(self, key_path):
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            with key_path.open('xb') as handle:
                handle.write(AESGCM.generate_key(bit_length=256))
        self.cipher = AESGCM(key_path.read_bytes())

    @staticmethod
    def aad(owner, kind):
        return json.dumps(['rematch-central-v1', owner, kind, 1]).encode()

    def seal(self, owner, kind, payload):
        nonce = os.urandom(12)
        body = self.cipher.encrypt(nonce, json.dumps(payload).encode(), self.aad(owner, kind))
        return {'schema_version': 1, 'nonce': base64.b64encode(nonce).decode(), 'ciphertext': base64.b64encode(body).decode()}

    def open(self, owner, kind, envelope):
        if envelope['schema_version'] != 1:
            raise ValueError('Unsupported encrypted schema')
        return json.loads(self.cipher.decrypt(base64.b64decode(envelope['nonce']), base64.b64decode(envelope['ciphertext']), self.aad(owner, kind)))
