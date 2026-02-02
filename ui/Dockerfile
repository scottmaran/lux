FROM node:20-slim AS build

WORKDIR /ui

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM python:3.11-slim

WORKDIR /ui

COPY server.py /ui/server.py
COPY --from=build /ui/build /ui/build

ENV UI_BIND=0.0.0.0
ENV UI_PORT=8090
ENV UI_LOG_ROOT=/logs

EXPOSE 8090

CMD ["python3", "/ui/server.py"]
