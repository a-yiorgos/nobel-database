FROM nginxinc/nginx-unprivileged:alpine

COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY frontend/default.conf.template /etc/nginx/templates/default.conf.template
COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/styles.css /usr/share/nginx/html/styles.css
COPY frontend/app.js /usr/share/nginx/html/app.js

ENV API_SERVICE_URL=http://nobel-api-service:8000
ENV NGINX_ENVSUBST_FILTER=API_SERVICE_URL

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
