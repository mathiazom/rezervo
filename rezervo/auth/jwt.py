import jwt

from rezervo.auth.fusionauth import get_jwt_public_key


def decode_jwt_sub(token, algorithms, api_audience, issuer):
    def decode_sub():
        return decode_jwt(
            token, get_jwt_public_key(), algorithms, api_audience, issuer
        ).get("sub", None)

    sub = decode_sub()
    if sub is None:
        get_jwt_public_key.cache_clear()
        sub = decode_sub()
    return sub


def decode_jwt(token, signing_key, algorithms, api_audience, issuer):
    try:
        return jwt.decode(
            token,
            signing_key,
            algorithms=algorithms,
            audience=api_audience,
            issuer=issuer,
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}
