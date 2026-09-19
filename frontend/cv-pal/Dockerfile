# syntax=docker/dockerfile:1

FROM node:24-alpine AS builder

WORKDIR /app

# npm ci needs both files and installs exactly what the lock file pins.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build -- --configuration=selfhost


# nginx-unprivileged runs as a non-root user and listens on 8080, so no capability to
# bind privileged ports is needed anywhere in the stack.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder --chown=nginx:nginx /app/dist/cv-pal/browser /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:8080/"]
