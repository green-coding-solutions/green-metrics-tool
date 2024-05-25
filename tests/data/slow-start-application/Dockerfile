FROM alpine

# Define health check
# HEALTHCHECK --interval=1s CMD pgrep 'stress-ng'
# HEALTHCHECK --start-interval=1s --start-period=10s --interval=1s --timeout=1s --retries=10 CMD pgrep 'stress-ng'

COPY start.sh /start.sh
RUN chmod +x /start.sh
CMD ["/start.sh"]
