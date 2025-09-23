# ADR-0001: Repository Boundaries

## Status
Accepted

## Context

As the agentic trading system grows, we need clear boundaries between components to enable:
- Independent development and deployment cycles
- Clear ownership and responsibility
- Parallel development by multiple teams
- Isolated testing and failure domains
- Technology stack flexibility per domain

The alternative of a monorepo would create tight coupling, shared dependencies, and coordination overhead that slows development velocity.

## Decision

We will organize the system into separate repositories with the following boundaries:

### Repository Structure
- **at-gateway**: External data ingestion and webhook handling
- **at-core**: Shared contracts, schemas, and common utilities
- **at-agent-mcp**: AI agents and strategy implementations
- **at-exec-sim**: Trade execution and simulation engine
- **at-observability**: Monitoring, metrics, and alerting

### Communication Rules
1. **No cross-repo imports**: Repositories communicate only through NATS events
2. **Contract-first**: All inter-service communication uses versioned schemas from at-core
3. **Independent deployment**: Each repo can be deployed without coordinating with others
4. **Isolated testing**: Each repo maintains its own test suite and CI/CD pipeline

### Shared Resources
- Event schemas and contracts live in at-core
- Common utilities are duplicated rather than shared
- Documentation templates are maintained in the umbrella repository

## Consequences

### Positive
- **Parallel development**: Teams can work independently without blocking each other
- **Clear ownership**: Each repo has defined maintainers and responsibilities
- **Easier refactoring**: Changes within a repo don't affect others if contracts remain stable
- **Technology flexibility**: Each repo can choose appropriate tools and frameworks
- **Blast radius containment**: Issues in one repo don't directly impact others

### Negative
- **Documentation overhead**: Each repo needs comprehensive docs and contracts
- **Testing complexity**: Integration testing requires coordinating multiple repos
- **Code duplication**: Common utilities may be duplicated across repos
- **Initial setup cost**: More upfront work to establish contracts and boundaries

### Mitigation Strategies
- Comprehensive contract testing to catch integration issues early
- Shared documentation templates to reduce documentation burden
- Regular architecture reviews to ensure boundaries remain appropriate
- Automated tooling to detect contract drift between repos