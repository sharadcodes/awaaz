FROM node:22.16-alpine AS dependencies

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM dependencies AS test

COPY . .
CMD ["npm", "test"]

FROM test AS build

RUN npm run build

FROM nginx:1.28.0-alpine

ENV API_UPSTREAM=http://api:8000 \
    NGINX_ENVSUBST_FILTER=API_UPSTREAM

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/health || exit 1
