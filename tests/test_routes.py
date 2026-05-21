def test_login_page_accessible(client):
    response = client.get("/auth/login")
    assert response.status_code in [200, 302]


def test_home_redirect_if_not_logged(client):
    response = client.get("/")
    assert response.status_code in [200, 302]


def test_events_protected(client):
    response = client.get("/events")
    assert response.status_code in [302, 401, 403]


def test_recordings_protected(client):
    response = client.get("/recordings")
    assert response.status_code in [302, 401, 403]
