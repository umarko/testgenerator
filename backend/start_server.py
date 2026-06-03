import sys
import traceback
from pathlib import Path

import uvicorn


if __name__ == "__main__":
    log_path = Path(__file__).with_name("server.log")
    with log_path.open("a", encoding="utf-8") as log_file:
        sys.stdout = log_file
        sys.stderr = log_file
        log_file.write("Starting QA Test Case Generator API on http://127.0.0.1:8000\n")
        log_file.flush()
        try:
            uvicorn.run(
                "app.main:app",
                host="127.0.0.1",
                port=8000,
                log_config=None,
                access_log=True,
            )
        except Exception:
            traceback.print_exc(file=log_file)
            log_file.flush()
            raise
