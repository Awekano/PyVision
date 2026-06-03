# database.py
# Ce fichier permet de se connecter directement à la base MariaDB/MySQL
# Il contient aussi une fonction simple pour ajouter un événement

import mysql.connector


def get_db_connection():
    # Connexion à la base de données du projet
    return mysql.connector.connect(
        host="localhost",
        user="eryma_user",
        password="mot_de_passe",
        database="eryma_db"
    )


def add_event(event_type, description, video_filename=None, image_filename=None, camera_name="Camera 1"):
    # Ouverture de la connexion à la base de données
    conn = get_db_connection()
    cursor = conn.cursor()

    # Requête SQL pour ajouter un événement
    query = """
        INSERT INTO events (event_type, camera_name, description, video_filename, image_filename)
        VALUES (%s, %s, %s, %s, %s)
    """

    # Exécution de la requête avec les valeurs données
    cursor.execute(query, (event_type, camera_name, description, video_filename, image_filename))

    # Validation de l'ajout dans la base
    conn.commit()

    # Fermeture propre du curseur et de la connexion
    cursor.close()
    conn.close()
