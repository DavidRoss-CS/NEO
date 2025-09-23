# Testing Strategy

**Comprehensive testing approach for the Agentic Trading observability stack.**

## Overview

This document outlines the testing strategy for monitoring, metrics, alerts, and dashboards in the Agentic Trading Architecture. Our goal is to ensure observability systems are reliable, accurate, and provide actionable insights when incidents occur.

## Testing Philosophy

### Core Principles

1. **Test in Production**: Use production-like data and conditions
2. **Chaos Engineering**: Proactively inject failures to validate monitoring
3. **Continuous Validation**: Automated testing of monitoring systems
4. **Observability Coverage**: Ensure all services are properly monitored
5. **Alert Quality**: Minimize false positives while catching real issues

### Testing Pyramid

```
                    ┌─────────────────┐
                    │  Manual Tests   │  ← Incident simulations
                    │   (Quarterly)   │     End-to-end scenarios
                    └─────────────────┘
                  ┌───────────────────────┐
                  │  Integration Tests    │  ← Alert workflows
                  │     (Weekly)          │     Cross-service metrics
                  └───────────────────────┘
              ┌─────────────────────────────────┐
              │      Unit Tests                 │  ← Metric calculations
              │      (Continuous)               │     Dashboard queries
              └─────────────────────────────────┘
```

## Test Categories

### 1. Metric Collection Tests

**Purpose**: Verify metrics are collected accurately and consistently

#### Prometheus Scrape Tests

```bash
#!/bin/bash
# test_metric_collection.sh

echo "Testing Prometheus metric collection..."

# Test all targets are up
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up") | .labels.instance'

# Test specific metrics exist
metrics=(
  "gateway_webhooks_total"
  "agent_messages_processed_total"
  "orchestrator_workflows_total"
  "nats_consumer_pending_messages"
  "redis_connected_clients"
)

for metric in "${metrics[@]}"; do
  result=$(curl -s "http://localhost:9090/api/v1/query?query=${metric}" | jq '.data.result | length')
  if [ "$result" -eq 0 ]; then
    echo "ERROR: Metric $metric not found"
  else
    echo "✓ Metric $metric: $result series"
  fi
done
```

#### Metric Accuracy Tests

```python
# test_metric_accuracy.py
import requests
import json
import time
from datetime import datetime, timedelta

class MetricAccuracyTest:
    def __init__(self, prometheus_url="http://localhost:9090"):
        self.prometheus_url = prometheus_url

    def test_counter_increases(self):
        """Test that counters only increase."""
        query = "gateway_webhooks_total"

        # Get current value
        initial_value = self._query_metric(query)

        # Trigger webhook (test data)
        self._send_test_webhook()

        # Wait and check increase
        time.sleep(5)
        final_value = self._query_metric(query)

        assert final_value > initial_value, f"Counter did not increase: {initial_value} -> {final_value}"

    def test_histogram_buckets(self):
        """Test histogram bucket consistency."""
        query = "gateway_processing_duration_seconds_bucket"
        buckets = self._query_metric(query, return_all=True)

        # Check bucket counts are monotonic
        for series in buckets:
            values = [(float(label['le']), float(series['value'][1])) for label in series['metric'] if 'le' in label]
            values.sort()

            for i in range(1, len(values)):
                assert values[i][1] >= values[i-1][1], f"Histogram buckets not monotonic: {values}"

    def test_gauge_range(self):
        """Test gauge values are within expected ranges."""
        tests = [
            ("agent_confidence_score", 0, 1),
            ("redis_memory_usage_percent", 0, 100),
            ("container_cpu_usage_percent", 0, 100)
        ]

        for metric, min_val, max_val in tests:
            value = self._query_metric(metric)
            assert min_val <= value <= max_val, f"{metric} out of range: {value}"

    def _query_metric(self, query, return_all=False):
        """Query Prometheus for metric value."""
        response = requests.get(f"{self.prometheus_url}/api/v1/query",
                              params={"query": query})
        data = response.json()

        if return_all:
            return data['data']['result']

        if data['data']['result']:
            return float(data['data']['result'][0]['value'][1])
        return 0

    def _send_test_webhook(self):
        """Send test webhook to gateway."""
        test_payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "instrument": "EURUSD",
            "action": "buy",
            "confidence": 0.85
        }
        requests.post("http://localhost:8001/webhook/test", json=test_payload)

# Run tests
if __name__ == "__main__":
    test = MetricAccuracyTest()
    test.test_counter_increases()
    test.test_histogram_buckets()
    test.test_gauge_range()
    print("✓ All metric accuracy tests passed")
```

### 2. Dashboard Tests

**Purpose**: Validate dashboard queries and visualizations

#### Query Validation Tests

```python
# test_dashboard_queries.py
import json
import requests
from typing import List, Dict

class DashboardQueryTest:
    def __init__(self, grafana_url="http://localhost:3000",
                 prometheus_url="http://localhost:9090"):
        self.grafana_url = grafana_url
        self.prometheus_url = prometheus_url
        self.auth = ("admin", "admin")  # Default Grafana credentials

    def test_all_dashboards(self):
        """Test all dashboard queries return data."""
        dashboards = [
            "gateway.json",
            "agents.json"
        ]

        for dashboard_file in dashboards:
            self._test_dashboard_file(dashboard_file)

    def _test_dashboard_file(self, dashboard_file: str):
        """Test all queries in a dashboard file."""
        with open(f"grafana_dashboards/{dashboard_file}") as f:
            dashboard = json.load(f)

        print(f"Testing dashboard: {dashboard.get('title', dashboard_file)}")

        for panel in dashboard.get('panels', []):
            for target in panel.get('targets', []):
                if 'expr' in target:
                    self._test_prometheus_query(target['expr'],
                                              panel.get('title', 'Unknown'))

    def _test_prometheus_query(self, query: str, panel_title: str):
        """Test a Prometheus query returns valid data."""
        try:
            response = requests.get(f"{self.prometheus_url}/api/v1/query",
                                  params={"query": query},
                                  timeout=10)
            response.raise_for_status()

            data = response.json()
            if data['status'] != 'success':
                raise Exception(f"Query failed: {data.get('error', 'Unknown error')}")

            result_count = len(data['data']['result'])
            print(f"  ✓ {panel_title}: {result_count} series")

            # Check for common query issues
            if result_count == 0:
                print(f"    ⚠ No data returned for query: {query}")

        except Exception as e:
            print(f"  ✗ {panel_title}: Query error - {e}")
            print(f"    Query: {query}")

    def test_dashboard_variables(self):
        """Test dashboard template variables work."""
        # Test agent type variable
        query = "label_values(agent_messages_processed_total, agent_type)"
        response = requests.get(f"{self.prometheus_url}/api/v1/label/agent_type/values")

        if response.status_code == 200:
            values = response.json()['data']
            assert len(values) > 0, "No agent types found"
            print(f"✓ Agent type variable: {values}")
        else:
            print("✗ Agent type variable query failed")

# Run tests
if __name__ == "__main__":
    test = DashboardQueryTest()
    test.test_all_dashboards()
    test.test_dashboard_variables()
```

#### Visual Regression Tests

```python
# test_dashboard_visuals.py
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class DashboardVisualTest:
    def __init__(self):
        self.driver = webdriver.Chrome()  # Requires chromedriver
        self.base_url = "http://localhost:3000"

    def setup(self):
        """Login to Grafana."""
        self.driver.get(f"{self.base_url}/login")

        # Login with default credentials
        username = self.driver.find_element(By.NAME, "user")
        password = self.driver.find_element(By.NAME, "password")

        username.send_keys("admin")
        password.send_keys("admin")

        login_button = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='login-submit']")
        login_button.click()

        # Wait for dashboard to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='dashboard']"))
        )

    def test_dashboard_loads(self, dashboard_uid: str):
        """Test dashboard loads without errors."""
        self.driver.get(f"{self.base_url}/d/{dashboard_uid}")

        # Wait for panels to load
        time.sleep(5)

        # Check for error panels
        error_panels = self.driver.find_elements(By.CSS_SELECTOR, ".panel-content .alert-error")

        assert len(error_panels) == 0, f"Found {len(error_panels)} error panels"

        # Take screenshot for visual comparison
        self.driver.save_screenshot(f"screenshots/{dashboard_uid}.png")

        print(f"✓ Dashboard {dashboard_uid} loaded successfully")

    def test_all_dashboards(self):
        """Test all dashboards load properly."""
        dashboards = [
            "gateway-001",
            "agents-001"
        ]

        for dashboard_uid in dashboards:
            self.test_dashboard_loads(dashboard_uid)

    def teardown(self):
        """Close browser."""
        self.driver.quit()

# Run tests
if __name__ == "__main__":
    test = DashboardVisualTest()
    test.setup()
    try:
        test.test_all_dashboards()
    finally:
        test.teardown()
```

### 3. Alert Tests

**Purpose**: Ensure alerts fire correctly and escalation works

#### Alert Rule Tests

```bash
#!/bin/bash
# test_alert_rules.sh

echo "Testing Prometheus alert rules..."

# Validate alert rule syntax
promtool check rules prometheus/alerts/*.yml
if [ $? -ne 0 ]; then
    echo "✗ Alert rule syntax errors found"
    exit 1
fi
echo "✓ Alert rule syntax valid"

# Test alert rule evaluation
promtool query instant http://localhost:9090 'ALERTS{alertstate="firing"}'
echo "✓ Alert rule evaluation test complete"

# Test specific alert conditions
test_alerts=(
    "up{job=\"gateway\"} == 0"  # Gateway down
    "rate(gateway_validation_errors_total[5m]) / rate(gateway_webhooks_total[5m]) > 0.01"  # High error rate
    "histogram_quantile(0.95, rate(gateway_processing_duration_seconds_bucket[5m])) > 0.5"  # High latency
)

for alert_expr in "${test_alerts[@]}"; do
    echo "Testing alert: $alert_expr"
    promtool query instant http://localhost:9090 "$alert_expr"
done
```

#### Chaos Engineering Tests

```python
# test_chaos_scenarios.py
import subprocess
import time
import requests
import docker

class ChaosEngineeringTest:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.prometheus_url = "http://localhost:9090"

    def test_gateway_failure(self):
        """Test gateway failure detection and recovery."""
        print("Starting gateway failure test...")

        # Stop gateway container
        gateway_container = self.docker_client.containers.get("at-gateway")
        gateway_container.stop()

        # Wait for alert to fire
        time.sleep(120)  # Wait 2 minutes for alert

        # Check if alert fired
        alert_fired = self._check_alert_firing("GatewayDown")
        assert alert_fired, "Gateway down alert did not fire"

        # Restart gateway
        gateway_container.start()

        # Wait for recovery
        time.sleep(60)

        # Check alert cleared
        alert_cleared = not self._check_alert_firing("GatewayDown")
        assert alert_cleared, "Gateway down alert did not clear"

        print("✓ Gateway failure test passed")

    def test_high_error_rate(self):
        """Test high error rate alert."""
        print("Starting high error rate test...")

        # Inject errors by sending malformed webhooks
        for _ in range(100):
            try:
                requests.post("http://localhost:8001/webhook/tradingview",
                            json={"invalid": "data"},
                            timeout=1)
            except:
                pass  # Expected to fail

        # Wait for alert
        time.sleep(300)  # 5 minutes

        alert_fired = self._check_alert_firing("GatewayHighErrorRate")
        assert alert_fired, "High error rate alert did not fire"

        print("✓ High error rate test passed")

    def test_nats_partition(self):
        """Test NATS network partition."""
        print("Starting NATS partition test...")

        # Block NATS traffic using iptables
        subprocess.run(["docker", "exec", "at-gateway",
                       "iptables", "-A", "OUTPUT", "-p", "tcp",
                       "--dport", "4222", "-j", "DROP"],
                      capture_output=True)

        # Wait for alert
        time.sleep(180)  # 3 minutes

        alert_fired = self._check_alert_firing("NATSPublishFailure")
        assert alert_fired, "NATS publish failure alert did not fire"

        # Restore connectivity
        subprocess.run(["docker", "exec", "at-gateway",
                       "iptables", "-D", "OUTPUT", "-p", "tcp",
                       "--dport", "4222", "-j", "DROP"],
                      capture_output=True)

        print("✓ NATS partition test passed")

    def _check_alert_firing(self, alert_name: str) -> bool:
        """Check if specific alert is firing."""
        response = requests.get(f"{self.prometheus_url}/api/v1/alerts")
        alerts = response.json()['data']['alerts']

        for alert in alerts:
            if (alert['labels'].get('alertname') == alert_name and
                alert['state'] == 'firing'):
                return True
        return False

# Run chaos tests
if __name__ == "__main__":
    test = ChaosEngineeringTest()
    test.test_gateway_failure()
    test.test_high_error_rate()
    test.test_nats_partition()
    print("✓ All chaos engineering tests passed")
```

### 4. End-to-End Scenario Tests

**Purpose**: Test complete incident scenarios

#### Incident Simulation Tests

```python
# test_incident_scenarios.py
import time
import requests
import subprocess
from concurrent.futures import ThreadPoolExecutor

class IncidentScenarioTest:
    def __init__(self):
        self.base_urls = {
            "gateway": "http://localhost:8001",
            "prometheus": "http://localhost:9090",
            "grafana": "http://localhost:3000"
        }

    def test_trading_signal_flow(self):
        """Test complete trading signal processing flow."""
        print("Testing end-to-end trading signal flow...")

        # Send trading signal
        signal_payload = {
            "timestamp": "2024-01-15T10:30:00Z",
            "instrument": "EURUSD",
            "action": "buy",
            "confidence": 0.85,
            "price": 1.0850,
            "stop_loss": 1.0800,
            "take_profit": 1.0950
        }

        correlation_id = f"test_{int(time.time())}"
        headers = {"X-Correlation-ID": correlation_id}

        # 1. Send webhook to gateway
        response = requests.post(f"{self.base_urls['gateway']}/webhook/tradingview",
                               json=signal_payload, headers=headers)
        assert response.status_code == 200, "Gateway webhook failed"

        # 2. Wait for processing
        time.sleep(10)

        # 3. Verify metrics updated
        metrics_to_check = [
            "gateway_webhooks_total",
            "agent_messages_processed_total",
            "orchestrator_workflows_total"
        ]

        for metric in metrics_to_check:
            value = self._get_metric_value(metric)
            assert value > 0, f"Metric {metric} not updated"

        # 4. Check logs contain correlation ID
        log_found = self._check_logs_for_correlation_id(correlation_id)
        assert log_found, f"Correlation ID {correlation_id} not found in logs"

        print("✓ Trading signal flow test passed")

    def test_high_load_scenario(self):
        """Test system behavior under high load."""
        print("Testing high load scenario...")

        # Generate high load
        def send_webhook():
            requests.post(f"{self.base_urls['gateway']}/webhook/tradingview",
                         json={"instrument": "EURUSD", "action": "buy"})

        # Send 1000 concurrent webhooks
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(send_webhook) for _ in range(1000)]

            # Wait for completion
            for future in futures:
                future.result()

        # Check system still responsive
        time.sleep(30)  # Allow processing

        # Verify services still healthy
        health_checks = [
            ("Gateway", f"{self.base_urls['gateway']}/healthz"),
            ("Prometheus", f"{self.base_urls['prometheus']}/-/healthy")
        ]

        for service_name, url in health_checks:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, f"{service_name} unhealthy after load test"

        print("✓ High load scenario test passed")

    def test_partial_failure_scenario(self):
        """Test system behavior with partial failures."""
        print("Testing partial failure scenario...")

        # Stop one agent
        subprocess.run(["docker", "stop", "at-agent-momentum"], capture_output=True)

        # Continue sending signals
        for i in range(10):
            requests.post(f"{self.base_urls['gateway']}/webhook/tradingview",
                         json={"instrument": "EURUSD", "action": "buy"})
            time.sleep(1)

        # Check other agents still processing
        remaining_agents = ["risk", "sentiment", "correlation"]
        for agent in remaining_agents:
            metric = f"agent_messages_processed_total{{agent_type=\"{agent}\"}}"
            value = self._get_metric_value(metric)
            assert value > 0, f"Agent {agent} not processing messages"

        # Restart stopped agent
        subprocess.run(["docker", "start", "at-agent-momentum"], capture_output=True)

        time.sleep(10)  # Allow recovery

        print("✓ Partial failure scenario test passed")

    def _get_metric_value(self, metric: str) -> float:
        """Get current value of Prometheus metric."""
        response = requests.get(f"{self.base_urls['prometheus']}/api/v1/query",
                              params={"query": metric})
        data = response.json()

        if data['data']['result']:
            return float(data['data']['result'][0]['value'][1])
        return 0

    def _check_logs_for_correlation_id(self, correlation_id: str) -> bool:
        """Check if correlation ID appears in service logs."""
        services = ["at-gateway", "at-agent-momentum", "at-orchestrator"]

        for service in services:
            result = subprocess.run(["docker", "logs", service, "--since", "1m"],
                                  capture_output=True, text=True)
            if correlation_id in result.stdout:
                return True

        return False

# Run scenario tests
if __name__ == "__main__":
    test = IncidentScenarioTest()
    test.test_trading_signal_flow()
    test.test_high_load_scenario()
    test.test_partial_failure_scenario()
    print("✓ All incident scenario tests passed")
```

## Test Automation

### Continuous Integration

```yaml
# .github/workflows/observability-tests.yml
name: Observability Tests

on:
  push:
    paths:
      - 'repos/at-observability/**'
  pull_request:
    paths:
      - 'repos/at-observability/**'
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM

jobs:
  test-metrics:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start observability stack
        run: |
          cd repos/at-observability
          docker compose up -d
          sleep 30  # Wait for services to start

      - name: Test Prometheus configuration
        run: |
          promtool check config repos/at-observability/prometheus.yml

      - name: Test alert rules
        run: |
          promtool check rules repos/at-observability/prometheus/alerts/*.yml

      - name: Run metric collection tests
        run: |
          python repos/at-observability/tests/test_metric_accuracy.py

      - name: Test dashboard queries
        run: |
          python repos/at-observability/tests/test_dashboard_queries.py

      - name: Run chaos tests
        run: |
          python repos/at-observability/tests/test_chaos_scenarios.py

  test-dashboards:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Validate dashboard JSON
        run: |
          cd repos/at-observability/grafana_dashboards
          for file in *.json; do
            jq empty "$file" || exit 1
          done

      - name: Test dashboard imports
        run: |
          # Start Grafana
          docker run -d -p 3000:3000 grafana/grafana:latest
          sleep 30

          # Import dashboards via API
          cd repos/at-observability/grafana_dashboards
          for file in *.json; do
            curl -X POST \
              -H "Content-Type: application/json" \
              -d @"$file" \
              http://admin:admin@localhost:3000/api/dashboards/db
          done
```

### Production Testing

```bash
#!/bin/bash
# production_health_check.sh

echo "Running production observability health check..."

# Check all Prometheus targets
FAILING_TARGETS=$(curl -s http://prometheus:9090/api/v1/targets | \
  jq -r '.data.activeTargets[] | select(.health != "up") | .labels.instance')

if [ -n "$FAILING_TARGETS" ]; then
    echo "CRITICAL: Failing targets detected:"
    echo "$FAILING_TARGETS"
    exit 1
fi

# Check alert manager connectivity
curl -f http://prometheus:9090/api/v1/alertmanagers || {
    echo "CRITICAL: Alertmanager connectivity failed"
    exit 1
}

# Check Grafana datasource
curl -f -u admin:$GRAFANA_PASSWORD \
  http://grafana:3000/api/datasources/proxy/1/-/healthy || {
    echo "CRITICAL: Grafana datasource unhealthy"
    exit 1
}

# Check recent metric ingestion
RECENT_METRICS=$(curl -s "http://prometheus:9090/api/v1/query?query=up" | \
  jq '.data.result | length')

if [ "$RECENT_METRICS" -eq 0 ]; then
    echo "CRITICAL: No recent metrics found"
    exit 1
fi

echo "✓ Production observability health check passed"
echo "✓ $RECENT_METRICS active targets monitored"
```

## Test Data Management

### Synthetic Data Generation

```python
# generate_test_data.py
import random
import time
import requests
from datetime import datetime, timedelta

class TestDataGenerator:
    def __init__(self):
        self.gateway_url = "http://localhost:8001"
        self.instruments = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
        self.actions = ["buy", "sell", "hold"]

    def generate_normal_traffic(self, duration_minutes: int = 60):
        """Generate normal trading signal traffic."""
        end_time = datetime.now() + timedelta(minutes=duration_minutes)

        while datetime.now() < end_time:
            # Generate 1-5 signals per minute
            signals_count = random.randint(1, 5)

            for _ in range(signals_count):
                self._send_trading_signal()
                time.sleep(random.uniform(0.1, 2.0))

            time.sleep(60 - signals_count * 1.0)  # Wait rest of minute

    def generate_error_traffic(self, error_rate: float = 0.1):
        """Generate traffic with specified error rate."""
        for _ in range(100):
            if random.random() < error_rate:
                # Send malformed signal
                self._send_malformed_signal()
            else:
                # Send normal signal
                self._send_trading_signal()

            time.sleep(0.1)

    def generate_high_latency_scenario(self):
        """Generate scenario that causes high latency."""
        # Send large batch simultaneously
        import threading

        def send_burst():
            for _ in range(10):
                self._send_trading_signal()

        threads = [threading.Thread(target=send_burst) for _ in range(20)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

    def _send_trading_signal(self):
        """Send a valid trading signal."""
        signal = {
            "timestamp": datetime.utcnow().isoformat(),
            "instrument": random.choice(self.instruments),
            "action": random.choice(self.actions),
            "confidence": round(random.uniform(0.6, 0.95), 2),
            "price": round(random.uniform(1.0, 1.5), 4),
            "stop_loss": round(random.uniform(0.95, 1.0), 4),
            "take_profit": round(random.uniform(1.5, 2.0), 4)
        }

        try:
            requests.post(f"{self.gateway_url}/webhook/tradingview",
                         json=signal, timeout=5)
        except requests.RequestException:
            pass  # Expected in some test scenarios

    def _send_malformed_signal(self):
        """Send an invalid trading signal."""
        malformed_signals = [
            {},  # Empty
            {"invalid": "structure"},  # Wrong fields
            {"instrument": None},  # Null values
            {"confidence": "not_a_number"},  # Wrong types
        ]

        signal = random.choice(malformed_signals)

        try:
            requests.post(f"{self.gateway_url}/webhook/tradingview",
                         json=signal, timeout=5)
        except requests.RequestException:
            pass  # Expected to fail

# Usage
if __name__ == "__main__":
    generator = TestDataGenerator()
    generator.generate_normal_traffic(duration_minutes=30)
```

## Performance Testing

### Load Testing

```python
# load_test.py
import asyncio
import aiohttp
import time
from statistics import mean, median

class LoadTest:
    def __init__(self, target_url: str, concurrent_users: int = 50):
        self.target_url = target_url
        self.concurrent_users = concurrent_users
        self.results = []

    async def run_load_test(self, duration_seconds: int = 300):
        """Run load test for specified duration."""
        print(f"Starting load test: {self.concurrent_users} users for {duration_seconds}s")

        async with aiohttp.ClientSession() as session:
            tasks = []

            for user_id in range(self.concurrent_users):
                task = asyncio.create_task(
                    self._user_scenario(session, user_id, duration_seconds)
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

        self._analyze_results()

    async def _user_scenario(self, session: aiohttp.ClientSession,
                           user_id: int, duration_seconds: int):
        """Simulate a user's behavior."""
        end_time = time.time() + duration_seconds

        while time.time() < end_time:
            start_time = time.time()

            try:
                async with session.post(
                    f"{self.target_url}/webhook/tradingview",
                    json=self._generate_signal(),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    await response.text()

                    result = {
                        "user_id": user_id,
                        "timestamp": start_time,
                        "response_time": time.time() - start_time,
                        "status_code": response.status,
                        "success": response.status == 200
                    }
                    self.results.append(result)

            except Exception as e:
                result = {
                    "user_id": user_id,
                    "timestamp": start_time,
                    "response_time": None,
                    "status_code": None,
                    "success": False,
                    "error": str(e)
                }
                self.results.append(result)

            # Wait between requests (1-3 seconds)
            await asyncio.sleep(random.uniform(1, 3))

    def _generate_signal(self) -> dict:
        """Generate trading signal for load testing."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "instrument": "EURUSD",
            "action": "buy",
            "confidence": 0.8
        }

    def _analyze_results(self):
        """Analyze load test results."""
        successful_requests = [r for r in self.results if r['success']]
        failed_requests = [r for r in self.results if not r['success']]

        response_times = [r['response_time'] for r in successful_requests
                         if r['response_time'] is not None]

        print("\nLoad Test Results:")
        print(f"Total requests: {len(self.results)}")
        print(f"Successful: {len(successful_requests)}")
        print(f"Failed: {len(failed_requests)}")
        print(f"Success rate: {len(successful_requests) / len(self.results) * 100:.2f}%")

        if response_times:
            print(f"Average response time: {mean(response_times):.3f}s")
            print(f"Median response time: {median(response_times):.3f}s")
            print(f"95th percentile: {sorted(response_times)[int(len(response_times) * 0.95)]:.3f}s")
            print(f"Max response time: {max(response_times):.3f}s")

# Run load test
if __name__ == "__main__":
    test = LoadTest("http://localhost:8001", concurrent_users=100)
    asyncio.run(test.run_load_test(duration_seconds=600))  # 10 minutes
```

## Test Environment Setup

### Docker Compose for Testing

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  prometheus-test:
    image: prom/prometheus:v2.45.0
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus:/etc/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=1d'  # Short retention for testing
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana-test:
    image: grafana/grafana:10.0.0
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning

  # Mock services for testing
  mock-gateway:
    image: nginx:alpine
    ports:
      - "8001:80"
    volumes:
      - ./test/mock-responses:/usr/share/nginx/html

  test-runner:
    build:
      context: .
      dockerfile: test/Dockerfile
    depends_on:
      - prometheus-test
      - grafana-test
    volumes:
      - ./test:/app/test
    command: python -m pytest test/ -v
```

---

**Next Steps**: Set up automated testing pipeline and integrate chaos engineering practices into regular testing cycles.