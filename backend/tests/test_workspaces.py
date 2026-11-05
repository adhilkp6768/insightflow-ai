from tests.conftest import register


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_user_only_sees_own_workspace(client):
    ada = register(client, email="ada@example.com", full_name="Ada Lovelace")
    grace = register(client, email="grace@example.com", full_name="Grace Hopper")

    ada_list = client.get("/api/v1/workspaces", headers=_auth(ada["access_token"]))
    assert ada_list.status_code == 200
    ada_workspaces = ada_list.json()
    assert len(ada_workspaces) == 1
    assert ada_workspaces[0]["name"] == "Ada's workspace"
    assert ada_workspaces[0]["role"] == "owner"
    assert ada_workspaces[0]["slug"] == "ada-lovelace"

    grace_list = client.get("/api/v1/workspaces", headers=_auth(grace["access_token"]))
    assert [item["slug"] for item in grace_list.json()] == ["grace-hopper"]

    hidden = client.get(
        f"/api/v1/workspaces/{ada_workspaces[0]['id']}",
        headers=_auth(grace["access_token"]),
    )
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "not_found"

    visible = client.get(
        f"/api/v1/workspaces/{ada_workspaces[0]['id']}",
        headers=_auth(ada["access_token"]),
    )
    assert visible.status_code == 200
    assert visible.json()["id"] == ada_workspaces[0]["id"]
