# tests/conftest.py
# Ce fichier prépare l'application Flask pour les tests pytest

import pytest
from app import create_app


@pytest.fixture
def app():
    # Création de l'application Flask en mode test
    app = create_app()

    # Configuration spéciale pour les tests
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })

    return app


@pytest.fixture
def client(app):
    # Création d'un client de test pour simuler des requêtes HTTP
    return app.test_client()
