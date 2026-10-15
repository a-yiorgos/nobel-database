#!/bin/sh
cat <<EOF > /usr/share/nginx/html/env-config.js
window.API_SERVICE_URL = "${API_SERVICE_URL:-}";
EOF
