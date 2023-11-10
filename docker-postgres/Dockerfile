FROM postgres:latest

# Copiar el script de backup a /docker-entrypoint-initdb.d
COPY backup.sql /docker-entrypoint-initdb.d/

# El script de backup se ejecutará automáticamente al iniciar el contenedor
