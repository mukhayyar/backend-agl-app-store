# flat-manager — Debian Bookworm runtime image
# The pre-built flat-manager binary must be placed at docker/flat-manager/flat-manager
# before building. The deploy.sh script copies it automatically.
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libostree-1-1 \
    libpq5 \
    libgpgme11 \
    libgpg-error0 \
    liblzma5 \
    zlib1g \
    gpg \
    gpg-agent \
    ostree \
    && rm -rf /var/lib/apt/lists/*

COPY flat-manager /usr/local/bin/flat-manager
RUN chmod +x /usr/local/bin/flat-manager
COPY flat-manager-client /usr/local/bin/flat-manager-client
RUN chmod +x /usr/local/bin/flat-manager-client
COPY gentoken /usr/local/bin/gentoken
RUN chmod +x /usr/local/bin/gentoken

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["flat-manager", "-c", "/etc/flat-manager/config.json"]
