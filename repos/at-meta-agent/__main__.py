"""Entry point for running the meta-agent service."""

import uvicorn
from at_meta_agent.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)