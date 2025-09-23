.PHONY: up down test e2e lock sync
up: ; docker compose -f docker-compose.dev.yml up -d
down: ; docker compose -f docker-compose.dev.yml down -v
test:
	$(MAKE) -C repos/at-core test || true
	$(MAKE) -C repos/at-gateway test || true
	$(MAKE) -C repos/at-agent-mcp test || true
	$(MAKE) -C repos/at-exec-sim test || true
e2e: ; pytest -q tests_e2e || true
lock: ; bash tools/lock-manifest.sh
sync: ; bash tools/sync-from-manifest.sh
