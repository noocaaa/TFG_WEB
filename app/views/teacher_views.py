from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import current_user, login_required

from app import db, bcrypt
from app.models import Users, Exercises, StudentProgress, Question, StudentActivity, Notification


from sqlalchemy import func

from datetime import datetime, timedelta

import os

teacher_blueprint = Blueprint('teacher', __name__)

ITEMS_PER_PAGE = 15  # Número de usuarios a mostrar por página

@teacher_blueprint.route('/teacher_dashboard')
@login_required
def teacher_dashboard():
    # Comprobar si el usuario es un profesor
    if current_user.type_user != 'X':
        flash('No tienes permisos para acceder a esta sección.', 'error')
        return redirect(url_for('control.login'))

    # Recuperar preguntas no respondidas y ordenarlas por fecha
    unanswered_questions = Question.query.filter((Question.answer_text == None) | (Question.answer_text == "")).order_by(Question.asked_date.desc()).all()

    # Recuperar usuarios para cada pregunta
    for question in unanswered_questions:
        question.student = Users.query.get(question.student_id)

    # Identificar estudiantes con alertas (última conexión hace más de una semana o nunca se han conectado)
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    alert_students = Users.query.filter(
        (Users.type_user == "S") &
        ((Users.last_seen == None) | 
        (Users.last_seen < one_week_ago))
    ).all()

    # Lista de ejercicios realizados en menos de 30 segundos y que están en estado "completado"
    fast_exercises = StudentProgress.query.filter(
        StudentProgress.time_spent < 30,
        StudentProgress.status == 'completed'
    ).all()

    # Lista de usuarios que han fallado más de dos veces un ejercicio
    failed_exercises = db.session.query(
        StudentProgress.student_id, 
        StudentProgress.exercise_id,
        func.count(StudentProgress.exercise_id).label('fail_count')
    ).filter(
        StudentProgress.status == 'failed'
    ).group_by(
        StudentProgress.student_id, 
        StudentProgress.exercise_id
    ).having(
        func.count(StudentProgress.exercise_id) > 2
    ).all()

    # Lista de usuarios que suelen equivocarse mucho
    frequent_failures = db.session.query(
        StudentProgress.student_id,
        func.count(StudentProgress.exercise_id).label('fail_count')
    ).filter(
        StudentProgress.status == 'failed'
    ).group_by(
        StudentProgress.student_id
    ).having(
        func.count(StudentProgress.exercise_id) > 5
    ).all()

    # Datos para la gráfica
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)

    exercise_counts = db.session.query(
        func.date(StudentProgress.start_date).label('exercise_date'),
        func.count(StudentProgress.id).label('exercise_count')
    ).filter(
        StudentProgress.start_date.between(start_date, end_date)
    ).group_by(
        func.date(StudentProgress.start_date)
    ).all()

    exercises_to_review = StudentProgress.query.filter_by(status='under_review').all()


    return render_template('teacher_dashboard.html', username=current_user.first_name, questions=unanswered_questions, alert_students=alert_students, fast_exercises=fast_exercises, failed_exercises=failed_exercises, frequent_failures=frequent_failures, exercise_counts=exercise_counts, exercises_to_review=exercises_to_review)

@teacher_blueprint.route('/change_password', methods=['POST'])
@login_required
def change_password():
    if current_user.type_user != 'X':
        flash('No tienes permisos para acceder a esta sección.', 'error')
        return redirect(url_for('control.login'))
    
    # Obtener los datos del formulario
    current_password = request.form.get('currentPassword')
    new_password = request.form.get('newPassword')
    confirm_password = request.form.get('confirmPassword')

    # Verificar que la contraseña actual sea correcta
    if not bcrypt.check_password_hash(current_user.password, current_password):
        error_msg = 'La contraseña actual es incorrecta'
        return render_template('teacher_dashboard.html', error=error_msg)
    
    # Asegurarse de que la nueva contraseña y la confirmación coincidan
    if new_password != confirm_password:
        error_msg = 'La nueva contraseña y la confirmación no coinciden'
        return render_template('teacher_dashboard.html', error=error_msg)
    
    # Cambiar la contraseña del usuario en la base de datos
    hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    current_user.password = hashed_password
    db.session.commit()

    flash('Contraseña cambiada con éxito', 'success')
    return redirect(url_for('teacher.teacher_dashboard'))


@teacher_blueprint.route('/answer/<int:question_id>', methods=['GET', 'POST'])
@login_required
def answer_question(question_id):
    if current_user.type_user != 'X':
        flash('No tienes permisos para acceder a esta sección.', 'error')
        return redirect(url_for('control.login'))
    
    question = Question.query.get(question_id)
    
    if not question:
        flash('Pregunta no encontrada.', 'danger')
        return redirect(url_for('teacher.teacher_dashboard'))
    
    if request.method == 'POST':
        answer_text = request.form.get('answer_text')
        if answer_text:
            question.answer_text = answer_text
            question.answered_date = datetime.now()
            
            # Mensaje amigable y animado
            notification_message = f"Tu profesor ya ha a respondido tu pregunta: '{question.question_text}'. ¡Haz clic en Aceptar para verla!"
            
            # Crear una nueva notificación
            notification = Notification(
                user_id=question.student_id,
                message=notification_message,
                timestamp=datetime.now(),
                is_read=False
            )

            # Añadir y comprometer la notificación a la base de datos
            db.session.add(notification)
            db.session.commit()

            return redirect(url_for('teacher.teacher_dashboard'))
        else:
            flash('La respuesta no puede estar vacía.', 'danger')
    
    return render_template('answer_question.html', question=question)

@teacher_blueprint.route('/asked_questions/<filename>')
@login_required
def asked_questions(filename):
    # Construye la ruta completa al archivo
    file_path = os.path.abspath(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
    
    # Verifica si el archivo existe
    if os.path.exists(file_path):
        # Envía el archivo
        return send_file(file_path, as_attachment=True)
    else:
        # Si el archivo no existe, devuelve un error 404
        return "File not found", 404


@teacher_blueprint.route('/control/user_list', methods=['GET', 'POST'])
@login_required
def user_list():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    # Número de página (por defecto 1 si no se especifica)
    page = request.args.get('page', 1, type=int)

    # Término de búsqueda
    search_term = request.form.get('search', '')

    # Consulta base: solo estudiantes
    query = Users.query.filter_by(type_user="S")

    # Si hay término de búsqueda, filtrar por él
    if search_term:
        query = query.filter(Users.first_name.ilike(f"%{search_term}%") | Users.last_name.ilike(f"%{search_term}%"))

    # Ordenar y paginar resultados
    users = query.order_by(Users.first_name, Users.last_name).paginate(page=page, per_page=ITEMS_PER_PAGE, error_out=False)

    return render_template('user_list.html', users=users, search_term=search_term)



@teacher_blueprint.route('/control/exercise_list', methods=['GET', 'POST'])
@login_required
def exercise_list():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    # Número de página (por defecto 1 si no se especifica)
    page = request.args.get('page', 1, type=int)

    # Término de búsqueda
    search_term = request.form.get('search', '')
    status = request.form.get('status')
    date = request.form.get('start_date')

    # Consulta base: todos los registros de ejercicio
    query = StudentProgress.query

    # Si hay término de búsqueda, filtrar por él (en este caso, filtramos por student_id)
    if search_term:
        query = query.filter(StudentProgress.student_id == search_term)

    # Si hay un estado seleccionado, filtrar por él
    if status:
        query = query.filter(StudentProgress.status == status)

    # Si se ha seleccionado una fecha, filtrar por ella
    if date:
        # Convertimos la fecha de string a objeto date (si estás usando otra base de datos o ORM, es posible que no necesites este paso)
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        query = query.filter(StudentProgress.date == date_obj)

    # Ordenar y paginar resultados (aquí lo ordenamos por id, pero puedes elegir otro campo si prefieres)
    exercises = query.order_by(StudentProgress.id).paginate(page=page, per_page=ITEMS_PER_PAGE, error_out=False)

    return render_template('exercise_list.html', exercises=exercises, search_term=search_term, status=status, date=date)


# ------------------------------------------------------


@teacher_blueprint.route('/review_exercise/<int:exercise_id>', methods=['GET', 'POST'])
@login_required
def review_exercise(exercise_id):
    # Comprobar si el usuario es un profesor
    if current_user.type_user != 'X':
        flash('No tienes permisos para acceder a esta sección.', 'error')
        return redirect(url_for('control.login'))

    # Obtener el ejercicio pendiente de revisión
    progress = StudentProgress.query.get_or_404(exercise_id)
    exercise = Exercises.query.get(progress.exercise_id)
    student = Users.query.get(progress.student_id)
    solution_code = progress.solution_code

    if request.method == 'POST':
        status = request.form.get('exercise_status')
        comments = request.form.get('correction_text')

        # Actualizar el estado y los comentarios del ejercicio basado en la revisión del profesor
        progress.status = status
        progress.comments = comments

        # Si el ejercicio es marcado como failed, se crea una nueva entrada con estado "pending"
        if status == "failed":

            notification_message = f"Tu ejercicio '{exercise.name}' ha sido revisado y necesita ser corregido. ¡Haz clic en Aceptar para ver los comentarios!"

            new_progress = StudentProgress(
                student_id=student.id,
                exercise_id=exercise.id,
                status="pending",
                comments=comments,
                start_date=datetime.utcnow()  # O usa una fecha/hora específica
            )
            db.session.add(new_progress)

            # Actualizar una tabla de actividad del estudiante, con tal de marcar el progreso del propio estudiante. 
            student_activity = StudentActivity.query.filter_by(student_id=student.id, content_id=exercise.id).first()

            if student_activity:
                student_activity.done = False

        else:
            notification_message = f"¡Buenas noticias! Tu ejercicio '{exercise.name}' ha sido revisado y marcado como válido."

        # Crear una nueva notificación
        notification = Notification(
            user_id=student.id,  # Asegurándonos de notificar al estudiante
            message=notification_message,
            timestamp=datetime.now(),
            is_read=False
        )

        # Guardar los cambios en la base de datos
        db.session.add(notification)
        db.session.commit()

        flash('Revisión completada con éxito.', 'success')
        return redirect(url_for('teacher.teacher_dashboard'))

    return render_template('review_exercise.html', exercise=exercise, student=student, progress=progress, solution_code=solution_code)
    
