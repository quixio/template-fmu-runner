#!/bin/sh

# Replace runtime placeholders with actual environment variable values
# This script runs when the container starts, before nginx

INDEX_FILE="/usr/share/nginx/html/index.html"

# Replace API_URL placeholder (use empty string if not set)
if [ -n "$API_URL" ]; then
    sed -i "s|__RUNTIME_API_URL__|$API_URL|g" "$INDEX_FILE"
else
    sed -i "s|__RUNTIME_API_URL__||g" "$INDEX_FILE"
fi

# Replace HTTP_AUTH_TOKEN placeholder (use empty string if not set)
if [ -n "$HTTP_AUTH_TOKEN" ]; then
    sed -i "s|__RUNTIME_HTTP_AUTH_TOKEN__|$HTTP_AUTH_TOKEN|g" "$INDEX_FILE"
else
    sed -i "s|__RUNTIME_HTTP_AUTH_TOKEN__||g" "$INDEX_FILE"
fi

echo "Runtime configuration injected:"
echo "  API_URL: ${API_URL:-<not set>}"
echo "  HTTP_AUTH_TOKEN: ${HTTP_AUTH_TOKEN:+<set>}${HTTP_AUTH_TOKEN:-<not set>}"

# Start nginx
exec nginx -g "daemon off;"
