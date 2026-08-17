# Production image for the frontend.
#
# A Vite SPA is static files, so it is built once and served by a web server —
# no Node in the runtime image.
#
# **A real constraint, stated rather than worked around:** Vite inlines
# `VITE_API_BASE_URL` into the bundle at BUILD time. This image therefore
# encodes the API host it was built for, and cannot be promoted unmodified from
# one environment to another with a different API. The usual fix is to emit a
# small runtime `env.js` and substitute it on container start; it is
# deliberately not done here, because no second environment exists yet to
# promote across, and building the indirection first would be guessing at its
# shape. When a second environment appears, that is the change to make — and a
# journal entry to write.

FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Required: `client.ts` throws at runtime if this was not set, rather than
# silently pointing the bundle at the visitor's own machine (OPS-2).
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN test -n "$VITE_API_BASE_URL" \
    || (echo "VITE_API_BASE_URL build arg is required" >&2 && exit 1) \
    && npm run build


# nginx-unprivileged rather than plain nginx: it already runs as non-root on
# port 8080, instead of needing that retrofitted by hand.
FROM nginxinc/nginx-unprivileged:alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/ || exit 1
