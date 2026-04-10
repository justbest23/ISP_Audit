FROM python:3.12-slim

# System deps: nothing needed beyond pip for this app
WORKDIR /app

# Install Python dependencies first (better layer caching —
# only reinstalls if requirements.txt changes, not on every code change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the dashboard
COPY dash_speed.py .

# The log directory lives on the host and is mounted in at runtime.
# We don't copy it into the image — see docker-compose.yml.

# Run with gunicorn instead of the Dash dev server.
# Workers=1 is correct here: Dash callbacks share in-memory state
# and the dcc.Store cache would be inconsistent across multiple workers.
EXPOSE 8050
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "1", "--timeout", "120", "--access-logfile", "-", "dash_speed:server"]
