"""Entry point for running the broker adapter service."""

import uvicorn
from at_broker_adapters.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8006)