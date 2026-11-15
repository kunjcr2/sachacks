import base64
import hashlib
import hmac
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text
from rematch.common.config import KEYS


def _aad(clinic_id, patient_id):
    return json.dumps(["identity-v1",clinic_id,patient_id],separators=(",", ":")).encode()


def encrypt_identity(identity, clinic_id, patient_id, key):
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    nonce = os.urandom(12)
    encrypted = AESGCM(key).encrypt(nonce,json.dumps(identity,sort_keys=True).encode(),_aad(clinic_id,patient_id))
    return {"nonce_b64":base64.b64encode(nonce).decode(),"ciphertext_b64":base64.b64encode(encrypted).decode()}


def decrypt_identity(row, clinic_id, patient_id, key):
    return json.loads(AESGCM(key).decrypt(base64.b64decode(row["nonce_b64"]),base64.b64decode(row["ciphertext_b64"]),_aad(clinic_id,patient_id)))


def clinic_secrets(clinic_id):
    path = KEYS / f"{clinic_id}-vault.json"
    if not path.exists():
        KEYS.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({"key_b64":base64.b64encode(AESGCM.generate_key(256)).decode(),
                                    "pseudonym_secret":os.urandom(32).hex(),"key_id":f"{clinic_id}-v1"}))
    return json.loads(path.read_text())


class IdentityVault:
    def __init__(self, store, clinic_id, key, key_id):
        self.store,self.clinic_id,self.key,self.key_id = store,clinic_id,key,key_id

    def save(self, patient_id, identity, today):
        row = encrypt_identity(identity,self.clinic_id,patient_id,self.key)
        with self.store.engine.begin() as conn:
            conn.execute(text("INSERT INTO patient_identity_vault VALUES(:p,:k,:n,:c,:t,:t) ON CONFLICT(clinic_local_patient_id) DO UPDATE SET key_id=excluded.key_id,nonce_b64=excluded.nonce_b64,ciphertext_b64=excluded.ciphertext_b64,updated_at=excluded.updated_at"),
                         {"p":patient_id,"k":self.key_id,"n":row["nonce_b64"],"c":row["ciphertext_b64"],"t":today})
        # Exact identity fingerprints permit leak detection without vault decryption.
        fingerprints = [{"length":len(v.casefold()),"digest":self.fingerprint(v.casefold())}
                        for v in identity.values() if isinstance(v,str) and len(v)>=4]
        self.store.put("identity_fingerprints",patient_id,{"values":fingerprints})

    def fingerprint(self, value):
        return hmac.new(self.key,b"pii-guard-v1:"+value.encode(),hashlib.sha256).hexdigest()

    def reveal(self, patient_id):
        with self.store.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM patient_identity_vault WHERE clinic_local_patient_id=:p"),{"p":patient_id}).mappings().first()
        if not row:
            raise KeyError("Patient identity not found")
        return decrypt_identity(dict(row),self.clinic_id,patient_id,self.key)
