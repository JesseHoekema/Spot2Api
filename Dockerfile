FROM python:3.10-slim

# Install FFmpeg and other dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY spotify_mp3_server.py .

# Create downloads directory
RUN mkdir -p downloads

# Expose the port
EXPOSE 2354

# Run the application
CMD ["python", "spotify_mp3_server.py"]