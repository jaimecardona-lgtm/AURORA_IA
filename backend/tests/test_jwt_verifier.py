"""Verificación criptográfica del JWT: firma, expiración, iss, aud, algoritmo y claims."""

import time
import uuid

import jwt
import pytest

from app.security.jwt_verifier import (
    InvalidTokenError,
    JwksUnavailableError,
    SupabaseJwtVerifier,
    jwks_key_resolver,
)
from tests.conftest import AUDIENCE, ISSUER


def test_token_valido_devuelve_usuario(verifier, make_token):
    uid = str(uuid.uuid4())
    usuario = verifier.verify(make_token(sub=uid))
    assert str(usuario.id) == uid
    assert usuario.email == "alumna@prueba.local"


def test_token_expirado_se_rechaza(verifier, make_token):
    with pytest.raises(InvalidTokenError, match="expirado"):
        verifier.verify(make_token(exp_offset=-120))


def test_firma_de_otra_clave_se_rechaza(verifier, make_token, otra_clave_privada):
    with pytest.raises(InvalidTokenError):
        verifier.verify(make_token(key=otra_clave_privada))


def test_issuer_incorrecto_se_rechaza(verifier, make_token):
    with pytest.raises(InvalidTokenError, match="Emisor"):
        verifier.verify(make_token(iss="https://otro-proyecto.supabase.co/auth/v1"))


def test_audiencia_incorrecta_se_rechaza(verifier, make_token):
    with pytest.raises(InvalidTokenError, match="Audiencia"):
        verifier.verify(make_token(aud="anon"))


def test_sub_que_no_es_uuid_se_rechaza(verifier, make_token):
    with pytest.raises(InvalidTokenError, match="UUID"):
        verifier.verify(make_token(sub="no-es-uuid"))


def test_claim_obligatorio_ausente_se_rechaza(verifier, rsa_private_key):
    payload = {"sub": str(uuid.uuid4()), "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 60}
    token = jwt.encode(payload, rsa_private_key, algorithm="RS256", headers={"kid": "k"})
    with pytest.raises(InvalidTokenError, match="iat"):
        verifier.verify(token)


def test_algoritmo_hs256_se_rechaza_aunque_la_firma_sea_valida_en_hmac(verifier):
    """Evita la confusión de algoritmos: un token HS256 no se acepta aunque esté bien firmado."""
    payload = {
        "sub": str(uuid.uuid4()), "iss": ISSUER, "aud": AUDIENCE,
        "iat": int(time.time()), "exp": int(time.time()) + 60,
    }
    secreto = "secreto-compartido-falso-de-32-bytes-o-mas"
    token = jwt.encode(payload, secreto, algorithm="HS256", headers={"kid": "k"})
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


def test_algoritmo_none_se_rechaza(verifier):
    """Un token sin firma (alg=none) se construye a mano porque PyJWT no lo firma."""
    import base64
    import json

    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    payload = {
        "sub": str(uuid.uuid4()), "iss": ISSUER, "aud": AUDIENCE,
        "iat": int(time.time()), "exp": int(time.time()) + 60,
    }
    token = f"{b64({'alg': 'none', 'typ': 'JWT', 'kid': 'k'})}.{b64(payload)}."
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


@pytest.mark.parametrize("token", ["", "   ", "no.es.jwt", "abc"])
def test_token_vacio_o_malformado_se_rechaza(verifier, token):
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


def test_jwks_inaccesible_produce_503_no_401(make_token):
    """Si el proveedor no responde no debe parecer un token inválido."""
    resolver = jwks_key_resolver("http://127.0.0.1:9/.well-known/jwks.json", timeout_seconds=1)
    verifier = SupabaseJwtVerifier(issuer=ISSUER, audience=AUDIENCE, resolve_key=resolver)
    with pytest.raises(JwksUnavailableError):
        verifier.verify(make_token())
