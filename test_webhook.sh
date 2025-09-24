#!/bin/bash

TIMESTAMP=$(date +%s)
NONCE="nonce-$(date +%s)"
PAYLOAD='{"instrument":"EURUSD","price":"1.0850","signal":"buy","strength":0.85}'
MESSAGE="${TIMESTAMP}.${NONCE}.${PAYLOAD}"
SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "test-secret" -hex | cut -d' ' -f2)

echo "Testing webhook with proper authentication..."
echo "Timestamp: $TIMESTAMP"
echo "Nonce: $NONCE"
echo "Payload: $PAYLOAD"
echo "Signature: $SIGNATURE"
echo ""

curl -X POST http://localhost:8001/webhook/tradingview \
  -H 'Content-Type: application/json' \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-Nonce: $NONCE" \
  -H "X-Signature: $SIGNATURE" \
  -d "$PAYLOAD"