FROM nginxinc/nginx-unprivileged:alpine

COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/styles.css /usr/share/nginx/html/styles.css
COPY frontend/app.js /usr/share/nginx/html/app.js
COPY frontend/env-config.js /usr/share/nginx/html/env-config.js
COPY frontend/30-inject-config.sh /docker-entrypoint.d/30-inject-config.sh

USER root
RUN chmod +x /docker-entrypoint.d/30-inject-config.sh && \
    chmod -R g+rwX /usr/share/nginx/html
USER 101

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
