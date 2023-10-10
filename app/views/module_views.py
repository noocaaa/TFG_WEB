from flask import Blueprint

from app.models import StudentProgress, Exercises

from sqlalchemy import func, text, and_
from sqlalchemy import or_

module_blueprint = Blueprint('module', __name__)


# Número de ejercicios extra basándose en el rendimiento del estudiante.
def determine_number_of_extra_exercises(student_id, recent_num=5, max_extra_exercises=6):
    recent_exercises = (StudentProgress.query
                        .filter_by(student_id=student_id)
                        .order_by(StudentProgress.completion_date.desc())
                        .limit(recent_num)
                        .all())

    if len(recent_exercises) < recent_num:
        return 0
    
    failed_exercises = sum(1 for exercise in recent_exercises if exercise.status == "failed")
    failure_rate = failed_exercises / recent_num
    
    # Recoger los tiempos de todos los ejercicios para encontrar el mínimo y el máximo
    all_times = [e.time_spent for e in recent_exercises]
    min_time = min(all_times)
    max_time = max(all_times)
    
    # Evitar la división por cero si min_time == max_time
    if min_time == max_time:
        normalized_time_last_exercise = 1
    else:
        # Normalizar el tiempo del último ejercicio con respecto al rango [min_time, max_time]
        time_spent_last_exercise = recent_exercises[0].time_spent

        # Si hay 0 por algun motivo
        if time_spent_last_exercise == 0:
            time_spent_last_exercise = min_time

        normalized_time_last_exercise = (time_spent_last_exercise - min_time) / (max_time - min_time)
    
    # Ajustar los pesos según tu propia lógica y pruebas
    weight_failure_rate = 0.7
    weight_time = 0.3

    # De esta manera se penaliza los que tarden muy poco o los que tarden mucho
    normalized_time = abs(0.5 - normalized_time_last_exercise) * 2
    
    weighted_sum = (weight_failure_rate * failure_rate + weight_time * normalized_time)
    
    recommended_exercises = max(0, round(weighted_sum * max_extra_exercises))  

    return recommended_exercises



# Obtención de ejercicios adicionales en base a los ejercicios fallados por el estudiante, y que tengan requerimientos similares no identicos.
def get_extra_exercises(student_id):
    difficulty_areas = set()
    
    # Paso 1: Identificar Áreas de Dificultad
    failed_exercises = StudentProgress.query.filter_by(student_id=student_id, status='failed').all()

    for progress in failed_exercises:
        exercise = Exercises.query.get(progress.exercise_id)

        if exercise and exercise.requirements:
            difficulty_areas.update(exercise.requirements.split(', '))

    # Paso 2: Buscar Ejercicios Adicionales
    # Obtén todos los ejercicios que matcheen con las áreas de dificultad
    potential_extra_exercises = Exercises.query.filter(
        or_(*[Exercises.requirements.ilike(f"%{area}%") for area in difficulty_areas])
    ).all()

    # Filtra los ejercicios que el estudiante ya ha intentado o completado
    attempted_exercise_ids = {progress.exercise_id for progress in StudentProgress.query.filter_by(student_id=student_id).all()}
    extra_exercises = [exercise for exercise in potential_extra_exercises if exercise.id not in attempted_exercise_ids]
    
    num_extra_exercises = determine_number_of_extra_exercises(student_id)

    # Paso 3: Recomendar Ejercicios
    recommended_exercises = extra_exercises[:num_extra_exercises]

    return recommended_exercises
