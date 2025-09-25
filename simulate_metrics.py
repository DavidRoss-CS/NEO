#!/usr/bin/env python3
"""
NEO Metrics Simulator - Generate fake metrics for dashboard testing
"""
import time
import random
import json
from prometheus_client import start_http_server, Counter, Histogram, Gauge
from prometheus_client.core import CollectorRegistry, REGISTRY

# Create custom registry to avoid conflicts
CUSTOM_REGISTRY = CollectorRegistry()

# Define NEO metrics (matching our dashboard queries)
gateway_webhooks_total = Counter(
    'gateway_webhooks_processed_total',
    'Total webhooks processed',
    ['status'],
    registry=CUSTOM_REGISTRY
)

orchestrator_agent_requests = Counter(
    'orchestrator_agent_requests_total',
    'Total agent requests',
    ['agent_type', 'status'],
    registry=CUSTOM_REGISTRY
)

orchestrator_processing_duration = Histogram(
    'orchestrator_agent_processing_duration_seconds',
    'Agent processing duration',
    ['agent_type'],
    registry=CUSTOM_REGISTRY
)

orchestrator_active_agents = Gauge(
    'orchestrator_active_agents',
    'Number of active agents',
    ['agent_type'],
    registry=CUSTOM_REGISTRY
)

output_notifications_delivered = Counter(
    'output_notifications_delivered_total',
    'Notifications delivered',
    ['channel', 'status'],
    registry=CUSTOM_REGISTRY
)

output_delivery_duration = Histogram(
    'output_notification_delivery_duration_seconds',
    'Notification delivery duration',
    ['channel'],
    registry=CUSTOM_REGISTRY
)

paper_trading_balance = Gauge(
    'paper_trading_balance',
    'Current paper trading balance',
    registry=CUSTOM_REGISTRY
)

paper_trading_portfolio_value = Gauge(
    'paper_trading_portfolio_value',
    'Portfolio value',
    registry=CUSTOM_REGISTRY
)

output_trades_executed = Counter(
    'output_trades_executed_total',
    'Paper trades executed',
    ['status'],
    registry=CUSTOM_REGISTRY
)

def simulate_trading_activity():
    """Simulate realistic NEO trading system activity"""
    print("🚀 Starting NEO Metrics Simulator...")
    print("📊 Generating realistic trading activity...")

    # Initialize some baseline values
    paper_trading_balance.set(10000)
    paper_trading_portfolio_value.set(10000)

    orchestrator_active_agents.labels(agent_type='gpt_trend_analyzer').set(2)
    orchestrator_active_agents.labels(agent_type='claude_strategy').set(1)

    while True:
        # Simulate webhook activity
        if random.random() < 0.8:  # 80% success rate
            gateway_webhooks_total.labels(status='success').inc()

            # Simulate agent processing
            agent_types = ['gpt_trend_analyzer', 'claude_strategy', 'momentum_scanner']
            agent_type = random.choice(agent_types)

            if random.random() < 0.95:  # 95% agent success rate
                orchestrator_agent_requests.labels(agent_type=agent_type, status='success').inc()

                # Simulate processing duration (1-4 seconds)
                duration = random.uniform(1.0, 4.0)
                orchestrator_processing_duration.labels(agent_type=agent_type).observe(duration)

                # Simulate output delivery
                channels = ['slack', 'telegram', 'paper_trading']
                for channel in channels:
                    if random.random() < 0.9:  # 90% delivery success
                        output_notifications_delivered.labels(channel=channel, status='success').inc()

                        # Delivery duration (0.5-2 seconds)
                        delivery_time = random.uniform(0.5, 2.0)
                        output_delivery_duration.labels(channel=channel).observe(delivery_time)

                        # Simulate paper trade
                        if channel == 'paper_trading' and random.random() < 0.7:
                            output_trades_executed.labels(status='filled').inc()

                            # Update portfolio (small random changes)
                            current_balance = paper_trading_balance._value._value
                            current_portfolio = paper_trading_portfolio_value._value._value

                            change = random.uniform(-50, 100)  # -$50 to +$100
                            new_portfolio = max(5000, current_portfolio + change)  # Don't go below $5k

                            paper_trading_portfolio_value.set(new_portfolio)
                    else:
                        output_notifications_delivered.labels(channel=channel, status='error').inc()
            else:
                orchestrator_agent_requests.labels(agent_type=agent_type, status='error').inc()
        else:
            gateway_webhooks_total.labels(status='error').inc()

        # Random sleep between 0.5-3 seconds to simulate realistic activity
        time.sleep(random.uniform(0.5, 3.0))

if __name__ == '__main__':
    print("🎯 NEO Metrics Simulator v1.0.0")
    print("================================")
    print("📈 Serving metrics on http://localhost:8050/metrics")
    print("🔄 Simulating live trading activity...")

    # Start metrics server on port 8050
    start_http_server(8050, registry=CUSTOM_REGISTRY)

    try:
        simulate_trading_activity()
    except KeyboardInterrupt:
        print("\n⏹️ Metrics simulator stopped")