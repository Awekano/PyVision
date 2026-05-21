import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="eryma_user",
        password="mot_de_passe",
        database="eryma_db"
    )

def add_event(event_type, description, video_filename=None, image_filename=None, camera_name="Camera 1"):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        INSERT INTO events (event_type, camera_name, description, video_filename, image_filename)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (event_type, camera_name, description, video_filename, image_filename))
    conn.commit()

    cursor.close()
    conn.close()
