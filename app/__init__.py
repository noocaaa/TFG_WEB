from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

import os

# Inicializar las extensiones
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
cors = CORS()
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

def create_app():
    # Inicializar la instancia de Flask
    app = Flask(__name__)

    # Configuraciones básicas (por ejemplo, configuración de la base de datos)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS') == 'True'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER')
    app.config['STATIC_FOLDER'] = os.getenv('STATIC_FOLDER')


    # Crear la carpeta de subida si no existe
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Inicializar las extensiones con la app
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    cors.init_app(app)

    login_manager.login_view = 'login'
    login_manager.login_message = "Please log in to access this page."

    # Importar y registrar las vistas (Blueprints) al final para evitar referencias circulares
    from app.views import admin_blueprint, student_blueprint, teacher_blueprint, control_blueprint
    app.register_blueprint(admin_blueprint)
    app.register_blueprint(student_blueprint)
    app.register_blueprint(teacher_blueprint)
    app.register_blueprint(control_blueprint)

    return app
