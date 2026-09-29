"""Explicitly install the optional local rembg model. No user photos are involved."""

import os
from app.settings import get_settings

if __name__ == "__main__":
    os.environ["U2NET_HOME"] = str(get_settings().background_model_dir.resolve())
    from rembg import new_session

    new_session("u2netp", providers=["CPUExecutionProvider"])
    print("Background model ready. Restart the API and check the connection in the app.")
