# Architecture Overview
- Split services: gateway, agent, exec-sim, core, ops.
- Event topics: signals.* → decisions.* → orders.* → exec.reports.*
- Partition key: instrument. Ordering guaranteed per key.
