FROM python:3.11-slim

WORKDIR /ui

COPY . /ui

ENV UI_BIND=0.0.0.0
ENV UI_PORT=8090
ENV UI_LOG_ROOT=/logs

EXPOSE 8090

CMD ["python3", "/ui/server.py"]
