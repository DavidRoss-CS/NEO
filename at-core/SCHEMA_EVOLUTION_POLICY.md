# Schema Evolution Policy

This document references the comprehensive schema evolution policy maintained in the workspace.

**Full Policy Location**: `/workspace/schema_evolution_policy.md`

## Quick Reference

### Version Changes
- **MAJOR** (x.0.0): Breaking changes (rename/remove fields, new required fields, type changes)
- **MINOR** (x.y.0): Additive changes (new optional fields, new enum values with tolerant consumers)
- **PATCH** (x.y.z): Non-functional changes (documentation, descriptions)

### Current Schema Versions
- **SignalEventV1**: 1.0.0 (initial release)
- **AgentOutputV1**: 1.0.0 (initial release)
- **OrderIntentV1**: 1.0.0 (initial release)

### Schema Owners
- **SignalEventV1**: Platform Team
- **AgentOutputV1**: AI/ML Team
- **OrderIntentV1**: Execution Team

### Change Process
1. Propose schema change in GitHub issue
2. Get approval from schema owner + affected service owners
3. Update schema file (never mutate existing - create new version)
4. Update validation utilities and tests
5. Document migration plan if MAJOR change
6. Release with proper versioning and changelog

### Emergency Contacts
- Schema questions: Check workspace documentation
- Breaking changes: Follow dual-publish procedure
- Validation failures: Check DLQ and error logs

For complete details on the schema evolution process, migration procedures, and governance, see the full policy document in the workspace directory.