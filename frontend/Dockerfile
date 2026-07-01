# --- Build stage ---
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies (leverage layer caching)
COPY package.json package-lock.json* ./
RUN npm ci || npm install

# Copy source and build
COPY . .

# Allow overriding the API base at build time (baked into the static bundle)
ARG VITE_API_BASE=/api/v1
ENV VITE_API_BASE=$VITE_API_BASE

RUN npm run build

# --- Runtime stage ---
FROM nginx:alpine AS runtime

# SPA-aware nginx config with /api reverse proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static assets from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
