import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("SIGEV_PORT", "5055"))
    app.run(host="127.0.0.1", port=port)
