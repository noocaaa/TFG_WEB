#!/usr/bin/python3

from datetime import datetime, timedelta
from app.models  import Users

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import os

def get_inactive_users():
    inactivity_threshold = timedelta(days=7)  
    inactive_users = (
        Users.query
        .filter(datetime.now() - Users.last_seen > inactivity_threshold)
        .all()
    )
    return inactive_users

def send_reengagement_email(user_email):
    # Credenciales del correo electrónico
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')

    # Configurar el servidor SMTP
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)

    # Crear el mensaje
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user_email
    msg['Subject'] = '¡Continúa tu Aprendizaje!'

    body = ("¡Hola de nuevo!<br><br>"
            "Hemos notado que ha pasado un tiempo desde tu última visita a nuestra plataforma de aprendizaje. "
            "¡Te hemos echado de menos!<br>"
            "Hay muchos nuevos contenidos y actividades esperándote. "
            "Inicia sesión ahora y continúa tu viaje de aprendizaje.<br><br>"
            "¡Esperamos verte pronto!<br>"
            "- Tu Equipo de [Nombre de la Plataforma]")
    msg.attach(MIMEText(body, 'html'))

    # Enviar el correo
    try:
        server.sendmail(sender_email, user_email, msg.as_string())
        print(f"Correo enviado a {user_email}")
    except smtplib.SMTPException as e:
        print(f"Error al enviar el correo a {user_email}: {str(e)}")
    finally:
        server.quit()

# ---- EJECUCION DE LAS FUNCIONES ----

print ("holaholainitt")
# Obtener usuarios inactivos
inactive_users = get_inactive_users()

# Enviar correo electrónico a cada usuario inactivo
for user in inactive_users:
    send_reengagement_email(user.email)
