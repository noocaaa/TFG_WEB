from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, current_app
from flask_login import login_user, current_user, logout_user, login_required

from app import db, login_manager, bcrypt
from app.models import Users, Exercises, StudentProgress, Module, Question, StudentActivity, GlobalOrder, Theory, Notification, ExtraExercises

from sqlalchemy import func, text, and_

from datetime import datetime, timedelta

from werkzeug.utils import secure_filename

import os, subprocess, json, uuid, time, re

from app.views.module_views import get_extra_exercises, get_advanced_exercises, get_current_module_and_next_requirement_for_user, select_exercise_for_user

student_blueprint = Blueprint('student', __name__)

# con tal de evitar que haya skips consecutivos
MIN_EXERCISES_BETWEEN_SKIPS = 3
MAX_CONSECUTIVE_SKIPS = 1

def is_valid_json(data):
    try:
        json.loads(data)
        return True
    except ValueError:
        return False



@student_blueprint.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()


# --- GENERAL ---

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

@student_blueprint.route('/favicon.ico')
def favicon():
    return '', 204

@student_blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('control.login'))


# --- USUARIO ---

@student_blueprint.route('/', methods=['GET', 'POST'])
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

@student_blueprint.route('/registro', methods=['GET', 'POST'])
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

        # --- Hay que quitar el current module_id no nos sirve para nada de lo implementado. 
        new_user = Users(first_name=first_name, last_name=last_name, birth_date=birth_date, city=city, gender=gender, email=email, password=hashed_password, type_user="S", avatar_id=None, current_module_id="7")

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('control.login'))

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



@student_blueprint.route('/principal')
@login_required
def principal():
    if not current_user.is_authenticated:
        return redirect(url_for('control.login'))

    show_modal = not bool(current_user.avatar_id)

    user = current_user

    modules = Module.query.order_by(Module.id).all()
    modules_progress = []

    last_module_completely_done = None

    requirements = get_current_module_and_next_requirement_for_user(current_user.id)[1]

    id_req = requirements.requirement_id

    select_exercise_for_user(current_user.id, id_req)

    for module in modules:
        total_exercises = (
            db.session.query(Exercises)
            .join(GlobalOrder, Exercises.id == GlobalOrder.content_id)
            .filter(
                Exercises.module_id == module.id
            )
            .count()
        )

        completed_exercises = StudentProgress.query.filter_by(student_id=current_user.id, status="completed").join(Exercises).filter_by(module_id=module.id).count()

        completed_theory = StudentActivity.query.filter_by(student_id=current_user.id, content_type="Theory").count()

        total_theory = Theory.query.filter_by(module_id=module.id).count()

        extra_exercises_count = (
            db.session.query(ExtraExercises)
            .join(Exercises, ExtraExercises.exercise_id == Exercises.id)
            .filter(
                ExtraExercises.student_id == current_user.id,
                ExtraExercises.status == "dCompleted",
                Exercises.module_id == module.id
            )
            .count()
        )

        skipped_count = (
            db.session.query(StudentActivity)
            .join (Exercises, Exercises.id == StudentActivity.content_id)
            .filter(
                StudentActivity.student_id == current_user.id,
                StudentActivity.skipped == True,
                Exercises.module_id == module.id
            )
            .count()
        )

        if total_exercises > 0:
            progress = (completed_exercises + skipped_count + completed_theory) / (total_exercises + extra_exercises_count + total_theory) * 100
        else:
            progress = 0

        if progress == 100:
            last_module_completely_done = module.id + 1

        modules_progress.append({
            'module': module,
            'progress': progress,
            'available': False  # Inicialmente ponemos todos los módulos como no disponibles
        })

    if last_module_completely_done == None:
        last_module_completely_done = 14 # el primer modulo q tenemos en la BBDD

    for module_prog in modules_progress:
        module_id = module_prog['module'].id

        if module_id <= last_module_completely_done: 
            module_prog['available'] = True

    return render_template('principal.html', show_modal=show_modal, user=user, modules_progress=modules_progress)



@student_blueprint.route('/module/<int:module_id>/exercise')
@login_required
def module_exercise(module_id):

    user = current_user

    # Functions to get queries
    def get_exercise(exercise_id):
        return Exercises.query.filter_by(id=exercise_id).first()

    def get_theory(theory_id):
        return Theory.query.filter_by(id=theory_id).first()
    
    # Extra Exercises Logic
    recommended_exercises = get_extra_exercises(current_user.id)
    pending_extra_exercise = ExtraExercises.query.filter_by(student_id=current_user.id, status='Assigned').first()

    if recommended_exercises and not pending_extra_exercise:
        for exercise in recommended_exercises:
            new_extra_exercise = ExtraExercises(student_id=current_user.id, exercise_id=exercise.id)
            db.session.add(new_extra_exercise)
        db.session.commit()
        exercise = get_exercise(recommended_exercises[0].id)
        return render_template('exercise.html', user=user, exercise=exercise, exercise_language=exercise.language)

    elif pending_extra_exercise:
        exercise = get_exercise(pending_extra_exercise.exercise_id)
        return render_template('exercise.html', user=user, exercise=exercise, exercise_language=exercise.language)

    # Skip Exercises Logic
    advanced_exercises = get_advanced_exercises(current_user.id)

    if advanced_exercises:
        # Obtener las últimas n actividades del estudiante
        recent_activities = (
            StudentActivity.query
            .filter_by(student_id=current_user.id)
            .order_by(StudentActivity.order_global.desc())
            .limit(MAX_CONSECUTIVE_SKIPS + MIN_EXERCISES_BETWEEN_SKIPS + 1)
            .all()
        )

        # Contar ejercicios realizados y skips
        exercise_count_since_last_skip = 0
        skip_count = 0

        for activity in recent_activities:
            if activity.skipped:
                if exercise_count_since_last_skip < MIN_EXERCISES_BETWEEN_SKIPS:
                    # No permitir otro skip
                    return redirect(url_for('student.principal'))  # Redirigir o manejar como prefieras.
                else:
                    # Se ha realizado un nuevo skip, reiniciar el contador de ejercicios
                    exercise_count_since_last_skip = 0
                    skip_count += 1
            else:
                # Se ha completado un ejercicio, incrementar el contador
                exercise_count_since_last_skip += 1

        if skip_count < MAX_CONSECUTIVE_SKIPS:
            for exercise in advanced_exercises:
                existing_activity = (
                    StudentActivity.query
                    .filter_by(content_id=exercise.id, student_id=current_user.id, content_type="Exercises")
                    .first()
                )

                if not existing_activity:
                    global_order_entry = (
                        GlobalOrder.query
                        .filter_by(content_id=exercise.id, content_type="Exercises")
                        .first()
                    )

                    if global_order_entry:
                        new_activity = StudentActivity(
                            student_id=current_user.id,
                            content_id=exercise.id,
                            order_global=global_order_entry.global_order,
                            done=False,
                            skipped=True,
                            content_type="Exercises"
                        )
                        db.session.add(new_activity)
            
            db.session.commit()

    # Next Exercise
    existing_order_globals = (
        db.session.query(StudentActivity.order_global)
        .filter_by(student_id=current_user.id)
    ).subquery()

    next_global_order_entry = (
        GlobalOrder.query
        .filter(
            GlobalOrder.content_type.in_(["Theory", "Exercises"]),
            ~GlobalOrder.global_order.in_(existing_order_globals)
        )
        .order_by(GlobalOrder.global_order)
        .first()
    )

    if not next_global_order_entry:
        return redirect(url_for('student.principal'))

    # Handle next content
    if next_global_order_entry.content_type == "Theory":
        theory = get_theory(next_global_order_entry.content_id)
        if theory and theory.module_id == module_id:
            return render_template('theory.html', user=user, content=theory, content_id=theory.id)

    elif next_global_order_entry.content_type == "Exercises":
        exercise = get_exercise(next_global_order_entry.content_id)
        if exercise and exercise.module_id != module_id:
            return redirect(url_for('student.module_exercise', module_id=exercise.module_id))
        if exercise:
            return render_template('exercise.html', user=user, exercise=exercise, exercise_language=exercise.language)

    # Redirect to principal if no action is taken.
    return redirect(url_for('student.principal'))





@student_blueprint.route('/mark_theory_as_read/<int:content_id>', methods=['POST'])
@login_required
def mark_theory_as_read(content_id):
    student_id = current_user.id
    
    # Obtener el order_global desde la tabla global_order
    global_order_record = GlobalOrder.query.filter_by(content_id=content_id, content_type='Theory').first()

    if not global_order_record:
        # manejar el error si no se encuentra el registro
        flash('Error al marcar la teoría como leída.', 'danger')
        return redirect(url_for('student.principal'))
    
    order_global = global_order_record.global_order
    
    # Crear un nuevo registro en studentactivity
    activity = StudentActivity(
        student_id=student_id,
        content_id=content_id,
        order_global=order_global,
        done=True,
        content_type='Theory'
    )
    
    db.session.add(activity)
    db.session.commit()

    # Obtener el module_id asociado al content_id
    content_record = Theory.query.filter_by(id=content_id).first()

    if not content_record:
        flash('Error al obtener el módulo asociado.', 'danger')
        return redirect(url_for('student.principal'))

    module_id = content_record.module_id

    return redirect(url_for('student.module_exercise', module_id=module_id))



@student_blueprint.route('/almacenar_avatar', methods=['POST'])
@login_required
def almacenar_avatar():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    avatar_elegido = request.form.get('avatar_elegido')
    
    if current_user:
        current_user.avatar_id = avatar_elegido
        db.session.commit()

    return redirect(url_for('student.principal'))


# --  Ejercicios, almacenaje, y visualización

@student_blueprint.route('/contenido', methods=['GET', 'POST'])
@login_required
def contenido():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    user = current_user

    if request.method == 'POST':
        # maneja el método POST aquí
        pass
    else:
        # maneja el método GET aquí
        avatar_id = current_user.avatar_id
        return render_template('contenido.html', user=user)

@student_blueprint.route('/contenido/view/<int:exercise_id>')
@login_required
def view_exercise(exercise_id):
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    user = current_user

    exercise = Exercises.query.get(exercise_id)
    if not exercise:
        flash('Exercise not found!', 'error')
        return redirect(url_for('student.principal'))
    return render_template('contenido.html', exercise=exercise, user=user)


def extract_classname(source_code):
    match = re.search(r'\bclass\s+(\w+)', source_code)
    if match:
        return match.group(1)
    return None



def some_compile_function(source_code, language, user_inputs):
    # Guardar el código en un archivo temporal
    filename = 'temp_code'
    executable_name = None

    if language == 'CPP':
        filename += '.cpp'
        executable_name = os.path.join(os.getcwd(), 'temp_output')
    elif language == 'JAVA':
        filename += '.java'
    elif language == 'PYTHON':
        filename += '.py'
    elif language == 'HTML':
        filename += '.html'
    else:
        return jsonify({"error": "Lenguaje no soportado"}), 400

    with open(filename, 'w') as f:
        f.write(source_code)

    # Intentar compilar el código
    try:
        if language == 'CPP':
            subprocess.check_output(['g++', filename, '-o', executable_name], stderr=subprocess.STDOUT)
        elif language == 'JAVA':
            subprocess.check_output(['javac', filename], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return e.output.decode('utf-8')

    # Si la compilación fue exitosa, intentar ejecutar el código
    try:
        input_data = '\n'.join(user_inputs)  # Combina todas las entradas con saltos de línea
        if language == 'CPP':
            time.sleep(0.1)  # Agregar retraso de medio segundo
            process = subprocess.Popen(executable_name, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True)
            output, error = process.communicate(input=input_data) # Aquí es donde pasas la entrada del usuario
            if process.returncode != 0:  # Esto es para manejar errores en la ejecución
                return error
            return output
        elif language == 'JAVA':
            class_name = extract_classname(source_code)
            if not class_name:
                return "Error: No se pudo determinar el nombre de la clase en el código fuente."
            time.sleep(0.1)  # Agregar retraso de medio segundo
            process = subprocess.Popen(['java', '-cp', '.', class_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True)
            output, error = process.communicate(input=input_data) # Aquí es donde pasas la entrada del usuario
            if process.returncode != 0:  # Esto es para manejar errores en la ejecución
                return error
            return output
        elif language == 'PYTHON':
            time.sleep(0.1)
            process = subprocess.Popen(['python', filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True)
            output, error = process.communicate(input=input_data)
            if process.returncode != 0:
                return error
            return output
        elif language == 'HTML':
            # No se necesita ejecución para HTML, simplemente se devuelve el código fuente.
            return source_code
    except subprocess.CalledProcessError as e:
        return e.output.decode('utf-8')
    finally:
        if os.path.exists(filename):
            os.remove(filename)
        if language == 'CPP' and os.path.exists(executable_name):
            os.remove(executable_name)
        elif language == 'JAVA' and os.path.exists(f'{class_name}.class'):
            os.remove(f'{class_name}.class')



@student_blueprint.route('/compile', methods=['POST'])
@login_required
def compile_code():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    # Obtener el código y el lenguaje del cuerpo de la petición
    source_code = request.form.get('source_code')
    language = request.form.get('language')
    
    # Obtener las entradas del usuario
    user_inputs = request.form.getlist('user_inputs[]') # Esto asume que las entradas se envían como una lista llamada 'user_inputs[]'
    
    # Compilación y ejecución del código con las entradas del usuario
    result = some_compile_function(source_code, language, user_inputs)
    
    return jsonify({"output": result})



def get_solution_for_exercise(exercise_name, module_id):
    # Buscar en la base de datos el ejercicio por su nombre y módulo
    try:
        exercise = Exercises.query.filter(
            func.trim(Exercises.name) == exercise_name.strip(),
            Exercises.module_id == module_id
        ).first()        
        if exercise:
            return exercise.solution
        else:
            return "No se encontró el ejercicio"
    except Exception as e:
        return str(e)



# -----


@student_blueprint.route('/biblioteca')
@login_required
def biblioteca():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
        
    user = current_user

    return render_template('biblioteca.html', user=user)
  
@student_blueprint.route('/preguntas')
@login_required
def preguntas():    
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    # Asumiendo que tienes un modelo 'Question' que representa las preguntas en la base de datos
    student_questions = Question.query.filter_by(student_id=current_user.id).all()

    # Obtención de los ejercicios que tienen comentarios del profesor para el estudiante
    commented_exercises = StudentProgress.query.filter(
        StudentProgress.student_id == current_user.id,
        StudentProgress.comments != None  # O usa una verificación más adecuada para los comentarios no vacíos
    ).all()

    return render_template('preguntas.html', user=current_user, student_questions=student_questions, commented_exercises=commented_exercises)


@student_blueprint.route('/submit_question', methods=['POST'])
@login_required
def submit_question(): 
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:
        return redirect(url_for('control.login'))

    question_text = request.form.get('question_text')
    file = request.files['attachment']
    filename = None
    if file:
        # Obtener la extensión del archivo
        file_ext = os.path.splitext(file.filename)[1]
        # Generar un nombre de archivo único
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}{file_ext}"
        filename = secure_filename(unique_filename)
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))

    new_question = Question(student_id=current_user.id, question_text=question_text, attachment_name=filename)
    db.session.add(new_question)
    db.session.commit()

    return redirect(url_for('student.preguntas'))


@student_blueprint.route('/rankings')
@login_required
def rankings():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
        
    # Obtener la fecha actual
    today = datetime.today().date()
    
    # Calcular el inicio de la semana y del mes
    start_week = today - timedelta(days=7)
    start_month = today.replace(day=1)
    
    # Consultas SQL para obtener el top 5 de estudiantes en diferentes periodos de tiempo
    daily_query = """
    SELECT student_id, first_name, last_name, COUNT(exercise_id) AS exercises_done
    FROM student_progress
    JOIN users ON student_progress.student_id = users.id
    WHERE completion_date = :today AND status = 'completed'
    GROUP BY student_id, first_name, last_name
    ORDER BY exercises_done DESC
    LIMIT 5;
    """

    weekly_query = text("""
    SELECT student_id, first_name, last_name, COUNT(exercise_id) AS exercises_done
    FROM student_progress
    JOIN users ON student_progress.student_id = users.id
    WHERE completion_date BETWEEN :start_week AND :today
    GROUP BY student_id, first_name, last_name
    ORDER BY exercises_done DESC
    LIMIT 5;
    """)

    monthly_query = """
    SELECT student_id, first_name, last_name, COUNT(exercise_id) AS exercises_done
    FROM student_progress
    JOIN users ON student_progress.student_id = users.id
    WHERE completion_date BETWEEN :start_month AND :end_date AND status = 'completed'
    GROUP BY student_id, first_name, last_name
    ORDER BY exercises_done DESC
    LIMIT 5;
    """

    # Wrap SQL queries
    daily_ranking = db.session.execute(text(daily_query), {'today': today}).fetchall()
    weekly_ranking = db.session.execute(weekly_query, {"start_week": start_week, "today": today}).fetchall()
    monthly_ranking = db.session.execute(text(monthly_query), {'start_month': start_month, 'end_date': today}).fetchall()


    return render_template('rankings.html', user=current_user, daily_ranking=daily_ranking, weekly_ranking=weekly_ranking, monthly_ranking=monthly_ranking)


@student_blueprint.route('/clanes')
@login_required
def clanes():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('clanes.html', user=current_user)

@student_blueprint.route('/configuracion', methods=['GET', 'POST'])
@login_required
def configuracion():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    if request.method == 'POST':
        new_email = request.form.get('email')
        new_password = request.form.get('password')
        new_avatar = request.form.get('avatar_elegido')

        if new_email:
            current_user.email = new_email
        if new_password:
            current_user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        if new_avatar:
            current_user.avatar_id = new_avatar

        db.session.commit()
        flash('Configuración actualizada con éxito', 'success')
        return redirect(url_for('student.principal'))

    return render_template('configuracion.html', user=current_user,)

@student_blueprint.route('/logo_guide')
@login_required
def logo_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('logo_guide.html', user=current_user)

@student_blueprint.route('/cpp_guide')
@login_required
def cpp_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    return render_template('cpp_guide.html', user=current_user)

@student_blueprint.route('/python_guide')
@login_required
def python_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('python_guide.html', user=current_user)

@student_blueprint.route('/java_guide')
@login_required
def java_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    return render_template('java_guide.html', user=current_user)

@student_blueprint.route('/web_guide')
@login_required
def web_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    user=current_user

    return render_template('web_guide.html')

@student_blueprint.route('/web_guide/html')
@login_required
def html_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('html_guide.html', user=current_user)

@student_blueprint.route('/web_guide/css')
@login_required
def css_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('css_guide.html', user=current_user)

@student_blueprint.route('/web_guide/javascript')
@login_required
def javascript_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('javascript_guide.html', user=current_user)



#  -------------------------------------------------------------------------------------


def find_next_content_id(user_id):
    next_global_order = db.session.query(GlobalOrder.global_order).\
        outerjoin(StudentActivity, and_(StudentActivity.content_id == GlobalOrder.content_id, StudentActivity.student_id == user_id)).\
        filter(StudentActivity.id == None).\
        order_by(GlobalOrder.global_order).\
        first()
    if not next_global_order:
        return None
    next_content = GlobalOrder.query.filter_by(global_order=next_global_order[0]).first()
    if not next_content:
        return None
    return next_content.content_id

def get_module_id_for_content(content_id, content_type):
    # Dependiendo del tipo de contenido, consulta la tabla adecuada
    if content_type == "Exercises":
        content = Exercises.query.get(content_id)
    elif content_type == "Theory":
        content = Theory.query.get(content_id)
    else:
        return None
    
    # Si encontramos el contenido, devuelve el module_id, de lo contrario, None
    return content.module_id if content else None


@student_blueprint.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()
    notifications_data = [{"id": n.id, "message": n.message} for n in notifications]
    return jsonify(notifications_data)


@student_blueprint.route('/api/mark_notification_read/<notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    try:
        notification_id = int(notification_id)
    except ValueError:
        return "Invalid notification_id", 400  # Bad Request

    notification = Notification.query.get(notification_id)
    if notification and notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return '', 204  # No content



# ---------------------- CORRECIÓN EJERCICIO ----------------------


def check_requirements(source_code, requirements):
    for req in requirements:
        if req.name not in source_code: 
            return False, f"El código fuente no cumple con el requisito: {req.name}"
    return True, "Todos los requisitos satisfechos"




@student_blueprint.route('/correct_exercise', methods=['POST'])
@login_required
def correct_exercise():
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    source_code = request.form.get('source_code')
    language = request.form.get('language')
    content_id = request.form.get('exercise_id')

    start_time = int(request.form.get('start_time'))
    start_time = datetime.fromtimestamp(start_time / 1000.0)

    end_time = int(request.form.get('end_time'))
    end_time = datetime.fromtimestamp(end_time / 1000.0)

    extra_exercise = ExtraExercises.query.filter_by(exercise_id=content_id).first()
    extra = extra_exercise is not None

    current_content = None if extra else GlobalOrder.query.filter_by(content_id=int(content_id)).first()
    
    if not current_content and not extra:
        return jsonify({"status": "error", "message": "El contenido no existe."})
    
    if current_content and current_content.content_type == "Theory":
        student_activity = StudentActivity.query.filter_by(student_id=current_user.id, content_id=content_id).first()
        if not student_activity:
            new_activity = StudentActivity(student_id=current_user.id, content_id=content_id, order_global=current_content.global_order, done=True, content_type="Theory")
            db.session.add(new_activity)
            db.session.commit()
        return jsonify({"status": "theory_completed"})
    
    exercise = Exercises.query.get(content_id)
    if not exercise:
        return jsonify({"status": "error", "message": "El ejercicio no existe."})

    requirements = exercise.requirements if exercise.requirements else []

    is_requirements_satisfied, requirements_message = check_requirements(source_code, requirements)

    time_spent = (end_time - start_time).seconds  

    if not is_requirements_satisfied:
        new_progress = StudentProgress(
            student_id=current_user.id, 
            exercise_id=content_id, 
            status="failed", 
            solution_code=source_code,
            start_date=start_time, 
            completion_date=end_time, 
            time_spent=time_spent
        )

        db.session.add(new_progress)

        db.session.commit()

        return jsonify({"status": "incorrect", "message": requirements_message})

    user_inputs = request.form.getlist('user_inputs[]')

    try:
        once_decoded = json.loads(exercise.test_verification)
        test_verification = json.loads(once_decoded)
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid test_verification format"})
    
    if list(test_verification.keys()) == ["A"] and test_verification["A"] == "B":
        result = some_compile_function(source_code, language, user_inputs)
        is_correct = (result.strip() == str(exercise.solution).strip())
    else:
        first_key = list(test_verification.keys())[0]
        result = some_compile_function(source_code, language, first_key)
        is_correct = (str(test_verification[first_key]).strip() == result.strip())
    
    if language == "html":
        status = "under_review"
    else:
        status = "completed" if is_correct else "failed"

    new_progress = StudentProgress(
        student_id=current_user.id, 
        exercise_id=content_id, 
        status=status, 
        solution_code=source_code,
        start_date=start_time, 
        completion_date=end_time, 
        time_spent=time_spent
    )

    db.session.add(new_progress)
    
    if not extra:
        student_activity = StudentActivity.query.filter_by(student_id=current_user.id, content_id=content_id).first()
        if not student_activity:
            new_activity = StudentActivity(student_id=current_user.id, content_id=content_id, order_global=current_content.global_order, done=True, content_type="Exercises")
            db.session.add(new_activity)
        else:
            student_activity.done = True
    else:
        extra_exercise_entry = ExtraExercises.query.filter_by(student_id=current_user.id, exercise_id=content_id, status='Assigned').first()
        if extra_exercise_entry:
            extra_exercise_entry.status = "Completed"
            extra_exercise_entry.completed_date = datetime.now()
    
    db.session.commit()

    next_global_order = db.session.query(GlobalOrder.global_order).\
        outerjoin(StudentActivity, and_(StudentActivity.content_id == GlobalOrder.content_id, StudentActivity.student_id == current_user.id)).\
        filter(StudentActivity.id == None).\
        order_by(GlobalOrder.global_order).\
        first()

    if not next_global_order:
        return jsonify({"status": status, "next_content_id": None})
    
    next_content = GlobalOrder.query.filter_by(global_order=next_global_order[0]).first()

    if not next_content:
        return jsonify({"status": status, "next_content_id": None})

    return jsonify({"status": status, "next_content_id": next_content.content_id})



@student_blueprint.route('/time_out', methods=['POST'])
@login_required
def time_out():
    source_code = request.form.get('source_code')
    content_id = request.form.get('exercise_id')

    start_time = int(request.form.get('start_time'))
    start_time = datetime.fromtimestamp(start_time / 1000.0)

    end_time = int(request.form.get('end_time'))
    end_time = datetime.fromtimestamp(end_time / 1000.0)

    time_spent = (end_time - start_time).seconds  

    status = "failed"

    new_progress = StudentProgress(
        student_id=current_user.id, 
        exercise_id=content_id, 
        status=status, 
        solution_code=source_code,
        start_date=start_time, 
        completion_date=end_time, 
        time_spent=time_spent
    )

    db.session.add(new_progress)

    db.session.commit()

    return jsonify({"status": "done"})