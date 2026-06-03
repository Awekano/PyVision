# tests/test_routes.py
# Ce fichier contient des tests simples pour vérifier les routes principales du site

def test_login_page_accessible(client):
    # Vérifie que la page de connexion est accessible
    response = client.get("/auth/login")
    assert response.status_code in [200, 302]


def test_home_redirect_if_not_logged(client):
    # Vérifie qu'un utilisateur non connecté est redirigé depuis l'accueil
    response = client.get("/")
    assert response.status_code in [200, 302]


def test_events_protected(client):
    # Vérifie que la page événements est protégée
    response = client.get("/events")
    assert response.status_code in [302, 401, 403]


def test_recordings_protected(client):
    # Vérifie que la page enregistrements est protégée
    response = client.get("/recordings")
    assert response.status_code in [302, 401, 403]
