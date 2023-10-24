from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, current_app
from flask_login import current_user, login_required

from app import db, bcrypt
from app.models import Exercises, StudentProgress, Module, Question, Notification, ModuleRequirementOrder, ExerciseRequirement

from sqlalchemy import func, text

from datetime import datetime, timedelta

from werkzeug.utils import secure_filename

import os, subprocess, json, uuid, time, re

from app.views.module_views import assign_exercise_to_student, mark_requirement_as_completed, get_current_module_and_next_requirement_for_user, select_exercise_for_user, get_exercise, all_exercises_completed_for_requirement, get_theory, get_next_theory_for_user

student_blueprint = Blueprint('student', __name__)

# --- USUARIO ---

def get_completed_exercises_count_for_module(user_id, module_id):
    # Primero, obtenemos todos los requisitos para el módulo
    requirements = ModuleRequirementOrder.query.filter_by(module_id=module_id).all()
    
    total_completed = 0
    extra = 0

    for requirement in requirements:
        count = db.session.query(StudentProgress)\
                  .join(Exercises, Exercises.id == StudentProgress.exercise_id)\
                  .join(ExerciseRequirement, ExerciseRequirement.exercise_id == Exercises.id)\
                  .filter(StudentProgress.student_id == user_id,
                          StudentProgress.status == "completed",
                          ExerciseRequirement.requirement_id == requirement.requirement_id,
                          Exercises.is_key_exercise == False)\
                   .count()
        if count > 4:
            extra += count - 4
        total_completed += count
        
    return total_completed, extra


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

    for module in modules:
        # Número de ejercicios clave para el módulo
        key_exercises = Exercises.query.filter_by(module_id=module.id, is_key_exercise=True).count()

        # Requerimientos del módulo
        module_requirements = ModuleRequirementOrder.query.filter_by(module_id=module.id).count()

        # Total de ejercicios completados por el estudiante en ese módulo
        completed_exercises, extra = get_completed_exercises_count_for_module(user.id, module.id)

        # Obtiene el porcentaje del progreso usando la fórmula dada.
        if module_requirements + key_exercises == 0:
            progress = 0
        else:
            progress = (completed_exercises / (module_requirements * 4 + key_exercises + extra)) * 100  

        if progress == 100:
            last_module_completely_done = module.id + 1

        modules_progress.append({
            'module': module,
            'progress': progress,
            'requirements': module_requirements,
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

    # Check if there's an exercise in progress for the student.
    in_progress_exercise = db.session.query(StudentProgress)\
                                    .filter_by(student_id=current_user.id, status='in progress')\
                                    .first()

    # If there's an exercise in progress, display it.
    if in_progress_exercise:
        exercise = get_exercise(in_progress_exercise.exercise_id)
        return render_template('exercise.html', user=user, exercise=exercise, exercise_language=exercise.language)

    # Get the current module and next requirement
    _, next_req = get_current_module_and_next_requirement_for_user(current_user.id)

    if all_exercises_completed_for_requirement(current_user.id, next_req.requirement_id):
            mark_requirement_as_completed(current_user.id, next_req.requirement_id, module_id)
            _, next_req = get_current_module_and_next_requirement_for_user(current_user.id)

    # If there's a pending requirement in the module
    if next_req:
        next_theory_id = get_next_theory_for_user(current_user.id, next_req.requirement_id)
        if next_theory_id:
            theory = get_theory(next_theory_id)
            # Assuming you have a theory template to display theory content
            return render_template('theory.html', user=user, content=theory, content_id=theory.id)

        # If there's no pending theory, proceed with exercise logic
        selected_exercise = select_exercise_for_user(current_user.id, next_req.requirement_id)

        if selected_exercise:
            assign_exercise_to_student(current_user.id, selected_exercise)
            exercise = get_exercise(selected_exercise.id)

            return render_template('exercise.html', user=user, exercise=exercise, exercise_language=exercise.language)

    # Redirect to main if no action is taken.
    return redirect(url_for('student.principal'))


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

# -----
  
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




#  -------- NOTIFICATIONS --------


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
