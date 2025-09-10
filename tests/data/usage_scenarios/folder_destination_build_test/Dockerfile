FROM alpine

# During build, files are at /tmp/repo regardless of folder-destination
# But during runtime, they should be at the folder-destination path
COPY test_file.txt /app/test_file.txt

# Keep container running  
CMD ["sleep", "infinity"]
