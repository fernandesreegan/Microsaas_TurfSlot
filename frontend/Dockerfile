# syntax=docker/dockerfile:1
# ---------- Stage 1: build ----------
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ARG VITE_API_URL=http://localhost:8000
ARG VITE_MAX_SLOTS_PER_BOOKING=4
ENV VITE_API_URL=$VITE_API_URL \
    VITE_MAX_SLOTS_PER_BOOKING=$VITE_MAX_SLOTS_PER_BOOKING

RUN npm run build

# ---------- Stage 2: serve ----------
FROM nginx:alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
