ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.24
FROM ${BUILD_FROM}

# All dependencies ship musllinux wheels for aarch64/amd64, so nothing compiles here
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt

WORKDIR /app
COPY frameart /app/frameart
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
