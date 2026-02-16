FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
ARG NUXT_PUBLIC_API_BASE=/api/v1
ARG NUXT_PUBLIC_SITE_URL=https://lk.chatmedbot.ru
ARG NUXT_PUBLIC_DOMAIN=lk.chatmedbot.ru
ARG NUXT_PUBLIC_NODE_ENV=production
ENV NUXT_PUBLIC_API_BASE=${NUXT_PUBLIC_API_BASE}
ENV NUXT_PUBLIC_SITE_URL=${NUXT_PUBLIC_SITE_URL}
ENV NUXT_PUBLIC_DOMAIN=${NUXT_PUBLIC_DOMAIN}
ENV NUXT_PUBLIC_NODE_ENV=${NUXT_PUBLIC_NODE_ENV}
RUN npm run build

FROM caddy:2.10-alpine

COPY --from=builder /app/.output/public /usr/share/caddy
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80
