from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_user, current_user, logout_user

from app import db, login_manager, bcrypt
from app.models import Users, Exercises, StudentProgress, StudentModules

from datetime import datetime

control_blueprint = Blueprint('control', __name__)

# Funciones utilitarias
def validate_password(password):
    # Reglas que la contraseña debe cumplir
    if len(password) < 8:
        return False
    if not any(char.isdigit() for char in password):
        return False
    if not any(char.isupper() for char in password):
        return False
    return True

@control_blueprint.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

@control_blueprint.route('/favicon.ico')
def favicon():
    return '', 204

@control_blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('control.login'))

@control_blueprint.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = Users.query.filter_by(email=email).first()
        if user and user.check_password(password, bcrypt):
            login_user(user)
            if user.type_user == 'T': #notación para admin
                return redirect(url_for('admin.admin_dashboard'))
            elif user.type_user == 'X': #notacion para profesores
                return redirect(url_for('teacher.teacher_dashboard'))
            else:
                return redirect(url_for('student.principal'))
        else:
            return render_template('login.html', error="Usuario o contraseña incorrectos")
    return render_template('login.html')

@control_blueprint.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        birth_date = request.form.get('birth_date')
        city = request.form.get('city')
        gender = request.form.get('gender')
        email = request.form.get('email')
        password = request.form.get('password')

        # Verificar si el correo ya existe
        existing_user = Users.query.filter_by(email=email).first()
        if existing_user:
            return render_template('registro.html', error="Ese correo ya está registrado")

        # Verificar si la contraseña cumple con los requisitos
        if not validate_password(password):
            return render_template('registro.html', error="La contraseña no cumple con los requisitos")

        # Hash the password using Flask-Bcrypt
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        new_user = Users(first_name=first_name, last_name=last_name, birth_date=birth_date, city=city, gender=gender, email=email, password=hashed_password, type_user="S", avatar_id=None, current_module_id="14")

        db.session.add(new_user)
        db.session.commit()

        # Insertamos el módulo con ID 14 para el nuevo usuario
        new_student_module = StudentModules(student_id=new_user.id, module_id=14, current_exercise_id=None, completed=False)
        db.session.add(new_student_module)
        db.session.commit()

        first_exercise = Exercises.query.filter_by(module_id=14).order_by(Exercises.id).first()

        # Verificar si encontramos un ejercicio
        if first_exercise:
            # Insertar un registro en student_progress con el estado inicial
            new_student_progress = StudentProgress(student_id=new_user.id, exercise_id=first_exercise.id, status='pending', completion_date=None, grade=None, time_spent=0)
            db.session.add(new_student_progress)
            db.session.commit()

        return render_template('login.html')

    return render_template('registro.html')

def validate_password(password):
    # Reglas que la contraseña debe cumplir
    if len(password) < 8:
        return False
    if not any(char.isdigit() for char in password):
        return False
    if not any(char.isupper() for char in password):
        return False
    return True