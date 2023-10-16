from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv, find_dotenv
from flask_wtf import CSRFProtect

import os

# Inicializar las extensiones
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
cors = CORS()

load_dotenv(find_dotenv())

def create_app():
    # Inicializar la instancia de Flask
    app = Flask(__name__)

    # Configuraciones básicas (por ejemplo, configuración de la base de datos)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS') == 'True'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER')
    app.config['STATIC_FOLDER'] = os.getenv('STATIC_FOLDER')

    # Configuración para enviar correos automaticamente
    # app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
    # app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
    # app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    # app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    # app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS')
    # app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL')


    # Crear la carpeta de subida si no existe
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


    # Inicializar las extensiones con la app
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "http://127.0.0.1:5000", "supports_credentials": True}})

    login_manager.login_view = 'student.login'
    login_manager.login_message = "Please log in to access this page."

    # Importar y registrar las vistas (Blueprints) al final para evitar referencias circulares
    from app.views import admin_blueprint, student_blueprint, teacher_blueprint, control_blueprint, module_blueprint
    
    app.register_blueprint(admin_blueprint)
    app.register_blueprint(student_blueprint)
    app.register_blueprint(teacher_blueprint)
    app.register_blueprint(control_blueprint)
    app.register_blueprint(module_blueprint)

    return app
