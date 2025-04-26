#!/bin/sh
if [ -z "$AVAX_C_WEBSOCKET_URL" ]; then
  echo "WARNING: AVAX_C_WEBSOCKET_URL is not set. Some processors may not function correctly."
fi
exec /app/benthos -c "$BENTHOS_CONFIG"
