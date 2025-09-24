# NATS Bootstrap Init Job
FROM natsio/nats-box:latest

WORKDIR /scripts

# Copy initialization scripts
COPY scripts/init-nats.sh /scripts/init-nats.sh

# Make scripts executable
RUN chmod +x /scripts/init-nats.sh

# Default command - use shell form to avoid entrypoint issues
CMD ["/bin/sh", "/scripts/init-nats.sh"]