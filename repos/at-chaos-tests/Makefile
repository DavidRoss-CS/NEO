# Chaos Testing Makefile

.PHONY: help test-mild test-severe test-backpressure test-duplicates test-suite stop-all

help:
	@echo "Chaos Testing Commands:"
	@echo "  test-mild        - Run mild latency test (50ms)"
	@echo "  test-severe      - Run severe latency test (500ms)"
	@echo "  test-backpressure - Run 10x backpressure test"
	@echo "  test-duplicates  - Run duplicate message test"
	@echo "  test-suite       - Run comprehensive test suite"
	@echo "  stop-all         - Stop all active experiments"
	@echo "  status           - Show active experiments"

test-mild:
	@echo "🧪 Running mild latency test..."
	@curl -X POST http://localhost:8008/experiments \
		-H "Content-Type: application/json" \
		-d '{"type": "nats_latency", "delay_ms": 50, "duration_s": 120}' | jq

test-severe:
	@echo "🧪 Running severe latency test..."
	@curl -X POST http://localhost:8008/experiments \
		-H "Content-Type: application/json" \
		-d '{"type": "nats_latency", "delay_ms": 500, "duration_s": 180}' | jq

test-backpressure:
	@echo "🧪 Running backpressure test..."
	@curl -X POST http://localhost:8008/experiments \
		-H "Content-Type: application/json" \
		-d '{"type": "backpressure", "rate_multiplier": 10, "duration_s": 300}' | jq

test-duplicates:
	@echo "🧪 Running duplicate message test..."
	@curl -X POST http://localhost:8008/experiments \
		-H "Content-Type: application/json" \
		-d '{"type": "duplicate_messages", "duplicate_rate": 0.2, "duration_s": 240}' | jq

test-suite:
	@echo "🧪 Running comprehensive chaos test suite..."
	@echo "Starting latency injection..."
	@curl -s -X POST http://localhost:8008/experiments \
		-H "Content-Type: application/json" \
		-d '{"type": "nats_latency", "delay_ms": 100, "duration_s": 600}' | jq
	@sleep 60
	@echo "Adding backpressure..."
	@curl -s -X POST http://localhost:8008/experiments \
		-H "Content-Type: application/json" \
		-d '{"type": "backpressure", "rate_multiplier": 5, "duration_s": 300}' | jq
	@sleep 60
	@echo "Adding duplicate messages..."
	@curl -s -X POST http://localhost:8008/experiments \
		-H "Content-Type: application/json" \
		-d '{"type": "duplicate_messages", "duplicate_rate": 0.1, "duration_s": 240}' | jq

stop-all:
	@echo "🛑 Stopping all chaos experiments..."
	@for exp_id in $$(curl -s http://localhost:8008/experiments | jq -r '.experiments[]?.experiment_id // empty'); do \
		echo "Stopping experiment: $$exp_id"; \
		curl -X DELETE "http://localhost:8008/experiments/$$exp_id"; \
	done

status:
	@echo "📊 Active chaos experiments:"
	@curl -s http://localhost:8008/experiments | jq '.experiments[]? // empty'

templates:
	@echo "📋 Available experiment templates:"
	@curl -s http://localhost:8008/templates | jq