"""Workspace invites and role changes."""

from tests.conftest import register


def _owner(client):
    session = register(client)
    workspace = client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    ).json()[0]
    return workspace, session["access_token"]


def test_existing_user_is_added_immediately(client):
    workspace, token = _owner(client)
    guest = register(client, email="guest@example.com", full_name="Guest User")
    invited = client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "guest@example.com", "role": "viewer"},
    )
    assert invited.status_code == 200, invited.text
    visible = client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {guest['access_token']}"},
    ).json()
    match = next(item for item in visible if item["id"] == workspace["id"])
    assert match["role"] == "viewer"
    denied = client.post(
        f"/api/v1/workspaces/{workspace['id']}/datasets/sample",
        headers={"Authorization": f"Bearer {guest['access_token']}"},
    )
    assert denied.status_code == 403


def test_pending_invite_is_accepted_on_registration(client):
    workspace, token = _owner(client)
    invited = client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "later@example.com", "role": "analyst"},
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["invites"][0]["email"] == "later@example.com"
    guest = register(client, email="later@example.com", full_name="Later User")
    visible = client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {guest['access_token']}"},
    ).json()
    match = next(item for item in visible if item["id"] == workspace["id"])
    assert match["role"] == "analyst"


def test_outsider_cannot_list_members_and_viewer_cannot_invite(client):
    workspace, token = _owner(client)
    outsider = register(client, email="out@example.com", full_name="Out User")
    hidden = client.get(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers={"Authorization": f"Bearer {outsider['access_token']}"},
    )
    assert hidden.status_code == 404
    client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "out@example.com", "role": "viewer"},
    )
    denied = client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers={"Authorization": f"Bearer {outsider['access_token']}"},
        json={"email": "third@example.com", "role": "analyst"},
    )
    assert denied.status_code == 403


def test_last_owner_cannot_be_demoted(client):
    workspace, token = _owner(client)
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    demoted = client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{me['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "analyst"},
    )
    assert demoted.status_code == 422, demoted.text
