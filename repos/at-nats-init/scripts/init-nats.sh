#!/bin/bash

# NATS JetStream Bootstrap Initialization
# Creates streams and consumers for the trading system

set -e

NATS_URL=${NATS_URL:-"nats://nats:4222"}
STREAM_NAME=${STREAM_NAME:-"trading-events"}
MAX_RETRIES=${MAX_RETRIES:-30}
RETRY_DELAY=${RETRY_DELAY:-2}

echo "🚀 Starting NATS JetStream initialization..."
echo "NATS URL: $NATS_URL"
echo "Stream: $STREAM_NAME"

# Wait for NATS to be available
echo "⏳ Waiting for NATS server..."
for i in $(seq 1 $MAX_RETRIES); do
    if nats -s "$NATS_URL" account info >/dev/null 2>&1; then
        echo "✅ NATS server is ready"
        break
    fi
    echo "🔄 Attempt $i/$MAX_RETRIES failed, retrying in ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
done

if ! nats -s "$NATS_URL" account info >/dev/null 2>&1; then
    echo "❌ Failed to connect to NATS after $MAX_RETRIES attempts"
    exit 1
fi

# Create or update the main trading stream
echo "📡 Creating/updating stream: $STREAM_NAME"
nats -s "$NATS_URL" str add "$STREAM_NAME" \
    --subjects "signals.*,decisions.*,executions.*" \
    --storage file \
    --retention limits \
    --dupe-window 2m \
    --replicas 1 \
    --max-age 7d \
    --max-msgs 1000000 \
    --defaults 2>/dev/null || {

    # If stream exists, update it
    echo "🔄 Stream exists, updating subjects..."
    nats -s "$NATS_URL" str edit "$STREAM_NAME" \
        --subjects "signals.*,decisions.*,executions.*" \
        --force
}

echo "✅ Stream $STREAM_NAME configured"

# Create consumers
echo "👥 Creating consumers..."

# Agent MCP consumer for normalized signals
echo "🤖 Creating mcp-signals consumer..."
nats -s "$NATS_URL" con add "$STREAM_NAME" mcp-signals \
    --filter "signals.normalized" \
    --deliver all \
    --ack explicit \
    --replay instant \
    --pull \
    --defaults 2>/dev/null || echo "ℹ️  Consumer mcp-signals already exists"

# Exec-sim consumer for order intents - reset with better config
echo "⚡ Creating/resetting exec-intents consumer..."
# Remove old consumer if exists
nats -s "$NATS_URL" con rm "$STREAM_NAME" exec-intents --force 2>/dev/null || true

# Create with robust configuration
nats -s "$NATS_URL" con add "$STREAM_NAME" exec-intents \
    --filter "decisions.order_intent" \
    --deliver new \
    --ack explicit \
    --replay instant \
    --max-ack-pending 2048 \
    --inactive-threshold 30m \
    --pull \
    --defaults 2>/dev/null || echo "ℹ️  Consumer exec-intents already exists"

# Meta-agent consumer for decisions (optional)
echo "🧠 Creating meta-decisions consumer..."
nats -s "$NATS_URL" con add "$STREAM_NAME" meta-decisions \
    --filter "decisions.*" \
    --deliver new \
    --ack explicit \
    --replay instant \
    --pull \
    --defaults 2>/dev/null || echo "ℹ️  Consumer meta-decisions already exists"

# Audit consumer for all events (optional)
echo "📋 Creating audit-all consumer..."
nats -s "$NATS_URL" con add "$STREAM_NAME" audit-all \
    --filter "" \
    --deliver all \
    --ack explicit \
    --replay instant \
    --pull \
    --defaults 2>/dev/null || echo "ℹ️  Consumer audit-all already exists"

echo "🎉 NATS JetStream initialization completed!"
echo ""
echo "📊 Stream status:"
nats -s "$NATS_URL" str info "$STREAM_NAME"
echo ""
echo "👥 Consumers:"
nats -s "$NATS_URL" con ls "$STREAM_NAME"

echo "✨ Initialization successful!"