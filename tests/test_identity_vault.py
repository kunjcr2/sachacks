import os
import json
import pytest
from cryptography.exceptions import InvalidTag
from rematch.clinic.identity_vault import encrypt_identity,decrypt_identity


def test_identity_crypto():
    key = os.urandom(32)
    identity = {"name":"Fictional Person","email":"fictional@example.test","mrn":"FAKE-MRN-123"}
    a = encrypt_identity(identity,"a","p",key)
    b = encrypt_identity(identity,"a","p",key)
    assert a!=b and a["nonce_b64"]!=b["nonce_b64"]
    assert decrypt_identity(a,"a","p",key)==identity
    for clinic,patient,k in [("b","p",key),("a","other",key),("a","p",os.urandom(32))]:
        with pytest.raises(InvalidTag):
            decrypt_identity(a,clinic,patient,k)
    assert all(v not in json.dumps(a) for v in identity.values())
