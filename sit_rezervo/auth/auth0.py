from sit_rezervo.auth.jwt import decode_jwt


def sub_from_jwt(token, domain, algorithms, api_audience, issuer):
    return decode_jwt(
        token.credentials,
        domain,
        algorithms,
        api_audience,
        issuer
    ).get("sub", None)
