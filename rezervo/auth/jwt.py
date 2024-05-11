import jwt


def decode_jwt_sub(token, signing_key, algorithms, api_audience, issuer):
    return decode_jwt(token, signing_key, algorithms, api_audience, issuer).get(
        "sub", None
    )


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
