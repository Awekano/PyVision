from app import create_app
import os
app = create_app()
app.config["RECORDINGS_DIR"] = os.path.abspath(os.path.join(app.root_path, "..", "recordings"))
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
