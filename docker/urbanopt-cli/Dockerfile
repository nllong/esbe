FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ARG URBANOPT_VERSION=1.2.0
ENV GDAL_CONFIG=/usr/bin/gdal-config

# Install base utilities needed to fetch and install URBANopt CLI.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    bash \
    git \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libsm6 \
    build-essential \
    python3-dev \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Install URBANopt CLI from GitHub Releases Debian package.
RUN set -eux; \
    ARCH="$(dpkg --print-architecture)"; \
    if [ "$ARCH" = "amd64" ]; then UO_ARCH="x86_64"; \
    elif [ "$ARCH" = "arm64" ]; then UO_ARCH="arm64"; \
    else echo "Unsupported architecture: $ARCH" >&2; exit 1; fi; \
    RELEASE_API="https://api.github.com/repos/urbanopt/urbanopt-cli/releases/tags/v${URBANOPT_VERSION}"; \
    UO_DEB="$(curl -fsSL "$RELEASE_API" | grep -o "URBANoptCLI-${URBANOPT_VERSION}\.[A-Za-z0-9]\+-Ubuntu-22.04-${UO_ARCH}\.deb" | head -n 1)"; \
    if [ -z "$UO_DEB" ]; then echo "Could not find Ubuntu 22.04 asset for arch ${UO_ARCH} in release v${URBANOPT_VERSION}" >&2; exit 1; fi; \
    UO_URL="https://github.com/urbanopt/urbanopt-cli/releases/download/v${URBANOPT_VERSION}/${UO_DEB}"; \
    echo "Downloading from: $UO_URL"; \
    curl -fL "$UO_URL" -o /tmp/urbanopt-cli.deb; \
    echo "Installing .deb package..."; \
    apt-get update && apt-get install -y /tmp/urbanopt-cli.deb; \
    rm -f /tmp/urbanopt-cli.deb; \
    echo "URBANopt CLI installed successfully"

# Run setup-env.sh to generate ~/.env_uo.sh, then place it in profile.d for
# login shells. The entrypoint below sources it for all other invocations.
RUN bash /usr/local/urbanopt-cli-*/setup-env.sh \
    && cp ~/.env_uo.sh /etc/profile.d/urbanopt-cli.sh

# Install Python dependencies for URBANopt
RUN bash -c "source /etc/profile.d/urbanopt-cli.sh && uo install_python"

# Entrypoint that sources the URBANopt env vars before any command, ensuring
# PATH and other variables are available regardless of shell invocation mode.
COPY docker/urbanopt-cli/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]


WORKDIR /workspace

CMD ["uo", "--help"]
