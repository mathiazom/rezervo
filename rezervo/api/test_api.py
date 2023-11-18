from fastapi.testclient import TestClient

from rezervo.api.api import api
from rezervo.schemas.config.user import IntegrationIdentifier

client = TestClient(api)


def test_features():
    response = client.get("/features")
    assert response.status_code == 403
    # TODO: authed test


def test_integration_config():
    for integration in IntegrationIdentifier:
        get_res = client.get(f"/{integration.value}/config")
        assert get_res.status_code == 403
        put_res = client.put(f"/{integration.value}/config")
        assert put_res.status_code == 403
        # TODO: authed test


def test_integration_user():
    for integration in IntegrationIdentifier:
        get_res = client.get(f"/{integration.value}/user")
        assert get_res.status_code == 403
        put_res = client.put(f"/{integration.value}/user")
        assert put_res.status_code == 403
        # TODO: authed test
