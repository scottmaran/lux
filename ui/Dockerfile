FROM node:20.11.1-bookworm-slim@sha256:357deca6eb61149534d32faaf5e4b2e4fa3549c2be610ee1019bf340ea8c51ec AS build

WORKDIR /ui

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

FROM python:3.11.8-slim-bookworm@sha256:90f8795536170fd08236d2ceb74fe7065dbf74f738d8b84bfbf263656654dc9b

LABEL org.opencontainers.image.title="lux-ui" \
      org.opencontainers.image.source="https://github.com/scottmaran/lux" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

WORKDIR /ui

COPY server.py /ui/server.py
COPY --from=build /ui/build /ui/build

ENV UI_BIND=0.0.0.0
ENV UI_PORT=8090
ENV UI_LOG_ROOT=/logs

EXPOSE 8090

CMD ["python3", "/ui/server.py"]
