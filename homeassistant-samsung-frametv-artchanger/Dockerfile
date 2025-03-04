ARG BUILD_FROM
FROM $BUILD_FROM

# Install dependencies
RUN \
  apk add --no-cache \
    python3 py3-pip git curl tar

# Download and install dezoomify-rs based on the platform
RUN if [ "$(uname -m)" = "x86_64" ]; then \
      DEZOOMIFY_URL="https://github.com/vivalatech/dezoomify-rs/releases/download/master/dezoomify-rs-x86_64-unknown-linux-musl.tgz"; \
    elif [ "$(uname -m)" = "aarch64" ]; then \
      DEZOOMIFY_URL="https://github.com/vivalatech/dezoomify-rs/releases/download/master/dezoomify-rs-aarch64-unknown-linux-musl.tgz"; \
    elif [ "$(uname -m)" = "armv7l" ]; then \
      DEZOOMIFY_URL="https://github.com/vivalatech/dezoomify-rs/releases/download/master/dezoomify-rs-armv7-unknown-linux-musleabihf.tgz"; \
    elif [ "$(uname -m)" = "armv6l" ]; then \
      DEZOOMIFY_URL="https://github.com/vivalatech/dezoomify-rs/releases/download/master/dezoomify-rs-arm-unknown-linux-musleabihf.tgz"; \
    else \
      DEZOOMIFY_URL="https://github.com/vivalatech/dezoomify-rs/releases/download/master/dezoomify-rs-i686-unknown-linux-musl.tgz"; \
    fi && \
    curl -L ${DEZOOMIFY_URL} | tar xz -C /usr/local/bin

# Install Python dependencies
RUN \
    pip3 install git+https://github.com/NickWaterton/samsung-tv-ws-api.git pillow pillow_heif

# Copy data for add-on
COPY run.sh /
COPY *.py /
RUN mkdir -p /sources/
COPY sources/*.py /sources/
RUN mkdir -p /utils/
COPY utils/*.py /utils/

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
