#!/usr/bin/env python3
"""
NEO Real-World Trading Pipeline Demonstration

This script demonstrates the complete NEO trading pipeline with:
1. TradingView webhook simulation
2. Real trading signals (BTCUSD, ETHUSDT, etc.)
3. HMAC authentication
4. Metrics collection
5. Dashboard visualization

Usage: python3 test_real_world_trading.py
"""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
import aiohttp
import sys
import os

# Configuration
GATEWAY_URL = "http://localhost:8001"
HMAC_SECRET = "test-secret"
GRAFANA_URL = "http://localhost:3000"
PROMETHEUS_URL = "http://localhost:9090"

def generate_hmac_signature(body: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook authentication"""
    signature = hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"

def create_trading_signals():
    """Create realistic trading signals for testing"""
    signals = [
        {
            "description": "Bitcoin Long Signal - Strong Bullish Momentum",
            "payload": {
                "time": datetime.now(timezone.utc).isoformat(),
                "ticker": "BTCUSD",
                "strategy": {
                    "market_position": "long",
                    "market_position_size": "0.5",
                    "strategy_name": "Momentum Breakout"
                },
                "order": {
                    "action": "buy",
                    "contracts": 0.25,
                    "price": 65000,
                    "stop_loss": 62000,
                    "take_profit": 70000
                },
                "analysis": {
                    "rsi": 68.5,
                    "macd_signal": "bullish_cross",
                    "volume_trend": "increasing",
                    "confidence": 0.82
                }
            }
        },
        {
            "description": "Ethereum Short Signal - Resistance Rejection",
            "payload": {
                "time": datetime.now(timezone.utc).isoformat(),
                "ticker": "ETHUSDT",
                "strategy": {
                    "market_position": "short",
                    "market_position_size": "0.3",
                    "strategy_name": "Resistance Trade"
                },
                "order": {
                    "action": "sell",
                    "contracts": 1.5,
                    "price": 3200,
                    "stop_loss": 3300,
                    "take_profit": 3000
                },
                "analysis": {
                    "rsi": 78.2,
                    "resistance_level": 3250,
                    "volume_divergence": "negative",
                    "confidence": 0.75
                }
            }
        },
        {
            "description": "BNB Long Signal - Support Bounce",
            "payload": {
                "time": datetime.now(timezone.utc).isoformat(),
                "ticker": "BNBUSD",
                "strategy": {
                    "market_position": "long",
                    "market_position_size": "0.2",
                    "strategy_name": "Support Bounce"
                },
                "order": {
                    "action": "buy",
                    "contracts": 10,
                    "price": 520,
                    "stop_loss": 500,
                    "take_profit": 550
                },
                "analysis": {
                    "support_level": 515,
                    "bounce_strength": "strong",
                    "volume_confirmation": True,
                    "confidence": 0.68
                }
            }
        }
    ]
    return signals

async def send_webhook(session, signal_data, endpoint="tradingview"):
    """Send authenticated webhook to NEO Gateway"""
    url = f"{GATEWAY_URL}/webhook/{endpoint}"
    body = json.dumps(signal_data)
    signature = generate_hmac_signature(body, HMAC_SECRET)

    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "User-Agent": "NEO-Trading-Test/1.0"
    }

    try:
        async with session.post(url, data=body, headers=headers) as response:
            status = response.status
            text = await response.text()
            return {
                "status": status,
                "response": text,
                "success": status == 200
            }
    except Exception as e:
        return {
            "status": 0,
            "response": str(e),
            "success": False
        }

async def check_service_health():
    """Check if NEO services are running"""
    services = {
        "Gateway": f"{GATEWAY_URL}/healthz",
        "Prometheus": f"{PROMETHEUS_URL}/-/healthy",
        "Grafana": f"{GRAFANA_URL}/api/health"
    }

    async with aiohttp.ClientSession() as session:
        health_status = {}
        for service, url in services.items():
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    health_status[service] = {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "url": url
                    }
            except Exception as e:
                health_status[service] = {
                    "status": "unreachable",
                    "error": str(e),
                    "url": url
                }
        return health_status

async def get_gateway_metrics():
    """Retrieve current Gateway metrics"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GATEWAY_URL}/metrics") as response:
                if response.status == 200:
                    text = await response.text()
                    # Extract key metrics
                    metrics = {}
                    for line in text.split('\n'):
                        if line.startswith('gateway_webhooks_received_total'):
                            parts = line.split()
                            if len(parts) >= 2:
                                metrics['webhooks_received'] = float(parts[-1])
                        elif line.startswith('gateway_webhook_duration_seconds_count'):
                            parts = line.split()
                            if len(parts) >= 2:
                                metrics['webhooks_processed'] = float(parts[-1])
                        elif line.startswith('gateway_validation_errors_total'):
                            parts = line.split()
                            if len(parts) >= 2 and 'replay' in line:
                                metrics['replay_errors'] = float(parts[-1])
                    return metrics
                else:
                    return {"error": f"HTTP {response.status}"}
    except Exception as e:
        return {"error": str(e)}

async def main():
    """Main demonstration function"""
    print("🚀 NEO v1.0.0 Real-World Trading Pipeline Demo")
    print("=" * 50)

    # Check service health
    print("\n📊 Checking NEO Service Health...")
    health = await check_service_health()

    for service, status in health.items():
        if status['status'] == 'healthy':
            print(f"   ✅ {service}: {status['status']}")
        else:
            print(f"   ❌ {service}: {status['status']} ({status.get('error', 'N/A')})")

    # Check if Gateway is available
    if health['Gateway']['status'] != 'healthy':
        print("\n⚠️  Gateway service not available. Please start the NEO infrastructure first.")
        print("   Run: docker-compose -f docker-compose.minimal.yml up -d")
        return

    print(f"\n📈 Gateway available at: {GATEWAY_URL}")
    print(f"📊 Monitoring available at: {GRAFANA_URL}")

    # Get initial metrics
    print("\n📊 Current Gateway Metrics:")
    initial_metrics = await get_gateway_metrics()
    if 'error' not in initial_metrics:
        for metric, value in initial_metrics.items():
            print(f"   {metric}: {value}")
    else:
        print(f"   Error retrieving metrics: {initial_metrics['error']}")

    # Generate and send trading signals
    print("\n💹 Generating Real-World Trading Signals...")
    signals = create_trading_signals()

    async with aiohttp.ClientSession() as session:
        results = []

        for i, signal in enumerate(signals, 1):
            print(f"\n📡 Signal {i}/3: {signal['description']}")

            # Send the webhook
            result = await send_webhook(session, signal['payload'])
            results.append(result)

            if result['success']:
                print(f"   ✅ Successfully processed (HTTP {result['status']})")
            else:
                print(f"   ❌ Failed (HTTP {result['status']}): {result['response']}")

            # Wait between signals to see metrics update
            if i < len(signals):
                print("   ⏳ Waiting 3 seconds before next signal...")
                await asyncio.sleep(3)

    # Get final metrics
    print("\n📊 Updated Gateway Metrics:")
    final_metrics = await get_gateway_metrics()
    if 'error' not in final_metrics:
        for metric, value in final_metrics.items():
            print(f"   {metric}: {value}")
    else:
        print(f"   Error retrieving metrics: {final_metrics['error']}")

    # Summary
    successful = sum(1 for r in results if r['success'])
    print(f"\n🎯 Demo Summary:")
    print(f"   Signals Sent: {len(results)}")
    print(f"   Successfully Processed: {successful}")
    print(f"   Failed: {len(results) - successful}")

    if successful > 0:
        print(f"\n🎉 Success! Your NEO Gateway processed {successful} real-world trading signals!")
        print("\n📊 Next Steps:")
        print(f"   • Open Grafana dashboards: {GRAFANA_URL}")
        print(f"   • Check Prometheus metrics: {PROMETHEUS_URL}")
        print("   • View live performance data in the Gateway dashboard")
    else:
        print("\n⚠️  No signals were processed successfully. Check service configuration.")

if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ required")
        sys.exit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")