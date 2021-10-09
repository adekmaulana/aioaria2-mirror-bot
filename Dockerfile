# Build Python package and dependencies
FROM python:3.9-alpine AS python-build
RUN apk add --no-cache \
        git \
        libffi-dev \
        musl-dev \
        gcc \
        g++ \
        make \
        zlib-dev \
        openssl-dev \
        libxml2-dev \
        libxslt-dev
RUN mkdir -p /opt/venv
WORKDIR /opt/venv
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN mkdir -p /src
WORKDIR /src

# Install bot package and dependencies
COPY . .
RUN pip install --upgrade pip
RUN pip install wheel
RUN pip install aiohttp[speedups]
RUN pip install uvloop
RUN pip install .


# Package everything
FROM python:3.9-alpine AS final
# Update system first
RUN apk update

# Install optional native tools (for full functionality)
RUN apk add --no-cache \
        curl \
        neofetch \
        git \
        nss
# Install native dependencies
RUN apk add --no-cache \
        libffi \
        musl \
        gcc \
        g++ \
        make \
        libwebp \
        openssl \
        zlib \
        busybox \
        sqlite \
        libxml2 \
        libxslt \
        libssh2 \
        ca-certificates \
        ffmpeg

# Create bot user
RUN adduser -D bot

# Copy Python venv
ENV PATH="/opt/venv/bin:$PATH"
COPY --from=python-build /opt/venv /opt/venv

# Download aria with sftp and gzip support
ARG ARIA2=aria2-1.36.0-r0.apk
RUN curl -LJO https://raw.githubusercontent.com/adekmaulana/docker/master/aria2/$ARIA2
RUN apk add --allow-untrusted --no-cache $ARIA2

# Certs for aria2 https websocket
RUN mkdir -p /home/bot/.cache/bot/.certs

# Initialize mkcert
RUN curl -LJO https://github.com/FiloSottile/mkcert/releases/download/v1.4.3/mkcert-v1.4.3-linux-amd64
RUN mv mkcert-v1.4.3-linux-amd64 /usr/local/bin/mkcert
RUN chmod +x /usr/local/bin/mkcert

RUN mkcert -install
RUN mkcert -key-file /home/bot/.cache/bot/.certs/key.pem -cert-file /home/bot/.cache/bot/.certs/cert.pem localhost 127.0.0.1

# Change permission of home folder
RUN chown -hR bot /home/bot

# Set runtime settings
USER bot
WORKDIR /home/bot
CMD ["bot"]
