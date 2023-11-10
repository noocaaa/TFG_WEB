# Usa una imagen base de Python
FROM python:3.8

# Instala las herramientas del sistema necesarias
RUN apt-get update && apt-get install -y \
    cppcheck \
    clang \
    checkstyle \
    cppcheck \
    clang-tools \
    llvm 

# Establece un directorio de trabajo
WORKDIR /

# Copia el archivo de requerimientos primero para aprovechar la cache de Docker
COPY requirements.txt /

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# # Copia el resto de tu código
# COPY ./app /app
# COPY ./run.py /
# COPY ./.env /

# # Expone el puerto que usa tu app
# EXPOSE 5000

# # El comando para arrancar la app
# CMD ["flask", "run"]