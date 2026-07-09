from __future__ import annotations

import uvicorn

from entity_linker.service import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
