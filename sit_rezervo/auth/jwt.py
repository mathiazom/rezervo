import jwt


def decode_jwt(token, domain, algorithms, api_audience, issuer):
    jwks_url = f"https://{domain}/.well-known/jwks.json"
    jwks_client = jwt.PyJWKClient(jwks_url)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
    except (jwt.exceptions.PyJWKClientError, jwt.exceptions.DecodeError) as error:
        return {"status": "error", "msg": error.__str__()}
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
