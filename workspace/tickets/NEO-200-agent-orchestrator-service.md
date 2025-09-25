# NEO-200: Agent Orchestrator Service Implementation

**Phase**: 2 - GPT Agent Integration
**Priority**: CRITICAL
**Status**: 🔄 IN_PROGRESS
**Assignee**: Claude
**Created**: 2025-09-24

## Scope

Implement the agent orchestrator service that manages GPT agents via MCP (Model Context Protocol) for intelligent signal analysis and decision making.

### Files to Create
- `repos/at-agent-orchestrator/` (new service directory)
- `repos/at-agent-orchestrator/at_agent_orchestrator/app.py`
- `repos/at-agent-orchestrator/at_agent_orchestrator/mcp_client.py`
- `repos/at-agent-orchestrator/at_agent_orchestrator/agent_manager.py`
- `repos/at-agent-orchestrator/at_agent_orchestrator/context_store.py`
- `repos/at-agent-orchestrator/requirements.txt`
- `repos/at-agent-orchestrator/Dockerfile`
- `repos/at-agent-orchestrator/tests/`

### Technical Requirements
- FastAPI service on port 8010
- MCP integration for GPT-4/Claude agents
- NATS subscription to `intents.agent_run.*`
- NATS publishing to `decisions.agent_output.*`
- Persistent context management with Redis
- Agent lifecycle management (spawn/terminate)
- Structured logging and metrics

## Definition of Done

### Functional Requirements
- [ ] Service subscribes to agent run intents from enhanced gateway
- [ ] MCP client connects to GPT/Claude agents
- [ ] Context persistence across agent conversations
- [ ] Agent output validation using AgentOutputV1 schema
- [ ] Publishes agent decisions to appropriate NATS subjects
- [ ] Health checks and service monitoring

### Technical Requirements
- [ ] Docker container builds and runs
- [ ] Integration with Phase 0 schema registry
- [ ] Feature flag support (FF_AGENT_GPT)
- [ ] Error handling with DLQ routing
- [ ] Comprehensive logging with correlation IDs
- [ ] Prometheus metrics for agent performance

### Testing Requirements
- [ ] Unit tests for agent management
- [ ] MCP client integration tests
- [ ] Context store tests with Redis mock
- [ ] End-to-end workflow tests
- [ ] Performance testing under load

## Implementation Steps

1. Create service directory structure
2. Implement FastAPI application with NATS integration
3. Build MCP client for GPT/Claude communication
4. Implement agent manager for lifecycle control
5. Add Redis-based context storage
6. Create comprehensive test suite
7. Add Docker configuration
8. Update docker-compose files

## Dependencies

- Phase 0: Schema registry (✅ Complete)
- Phase 1: Enhanced gateway (✅ Complete)
- Redis for context storage
- MCP-compatible agents (GPT-4, Claude)

## Integration Points

### Input Sources
- `intents.agent_run.{agent}` from enhanced gateway
- Manual agent triggers via REST API

### Output Destinations
- `decisions.agent_output.{agent}.{severity}`
- `audit.events` for agent activity logging

### External Services
- Redis for context persistence
- OpenAI API for GPT agents
- Anthropic API for Claude agents

## Success Criteria

- Agent orchestrator receives signal events and generates intelligent analysis
- Context persists across multiple agent interactions
- Output complies with AgentOutputV1 schema
- Performance SLO: Agent response within 5 seconds P95
- Zero message loss with proper error handling

## Rollback Procedure

```bash
# Stop new service
docker-compose stop agent-orchestrator
# Remove from compose files
git checkout HEAD -- docker-compose*.yml
# Remove service directory
rm -rf repos/at-agent-orchestrator/
```

## Notes

- This service bridges traditional trading signals with AI-powered analysis
- Context management is critical for coherent multi-turn conversations
- Feature flag FF_AGENT_GPT controls service activation
- Integration with existing at-agent-mcp patterns where possible

**Last Updated**: 2025-09-24