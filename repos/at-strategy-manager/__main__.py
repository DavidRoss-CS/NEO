"""Entry point for running the strategy manager service."""

import uvicorn
from at_strategy_manager.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007)