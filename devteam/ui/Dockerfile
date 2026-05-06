FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
ARG VITE_DEVTEAM_TOKEN=devteam-secret
ENV VITE_DEVTEAM_TOKEN=$VITE_DEVTEAM_TOKEN

RUN npm run build

FROM caddy:2.10-alpine
COPY --from=builder /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
