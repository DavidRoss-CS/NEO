# Agentic Trading Architecture (master)
Superproject that pins child repos, runs them together, and gates releases.


## Quick start (single repo mode)
1) docker compose -f docker-compose.dev.yml up -d
2) In one terminal: uvicorn repos/at-gateway/at_gateway/app:app --port 8081
3) In another: python -m repos.at_agent_mcp.at_agent_mcp.server 8082
4) In another: python -m repos.at_exec_sim.at_exec_sim.app 8083
5) curl -X POST http://localhost:8081/webhook/tradingview -H 'Content-Type: application/json' -d '{"instrument":"SI1!","price":"28.41","signal":"breakout_long","strength":0.72}'
