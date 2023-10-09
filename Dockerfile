FROM debian:bullseye-slim

# Instala g++ y herramientas esenciales
RUN apt-get update && apt-get install -y \
    g++ \
    && rm -rf /var/lib/apt/lists/*