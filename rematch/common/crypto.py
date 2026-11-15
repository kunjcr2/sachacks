import base64
import json
from nacl.public import PrivateKey,PublicKey,SealedBox
from rematch.common.config import KEYS
from rematch.common.schemas import CandidatePacket


def sponsor_private_key():
    path = KEYS/"sponsor-private.key"
    if not path.exists():
        KEYS.mkdir(parents=True,exist_ok=True)
        path.write_bytes(bytes(PrivateKey.generate()))
    return PrivateKey(path.read_bytes())


def encrypt_packet(packet:CandidatePacket,public_key_b64:str):
    return base64.b64encode(SealedBox(PublicKey(base64.b64decode(public_key_b64))).encrypt(packet.model_dump_json().encode())).decode()


def decrypt_packet(ciphertext_b64:str,private_key:PrivateKey):
    plain = SealedBox(private_key).decrypt(base64.b64decode(ciphertext_b64))
    return CandidatePacket.model_validate_json(plain)
