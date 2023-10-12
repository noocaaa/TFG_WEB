from flask import Blueprint

from collections import defaultdict

from app.models import StudentProgress, Exercises, GlobalOrder

from sqlalchemy import or_, and_

module_blueprint = Blueprint('module', __name__)



# --------- AÑADIR EJERCICIOS ---------


# Número de ejercicios extra basándose en el rendimiento del estudiante.
def determine_number_of_extra_exercises(student_id, requirement, recent_num=5, max_extra_exercises=6, failure_rate_threshold=0.2):
    recent_exercises = (StudentProgress.query
                        .join(Exercises, StudentProgress.exercise_id == Exercises.id)
                        .filter(and_(StudentProgress.student_id == student_id, Exercises.requirements.ilike(f"%{requirement}%")))
                        .order_by(StudentProgress.completion_date.desc())
                        .limit(recent_num)
                        .all())

    # print("recent: ", recent_exercises)

    # Hasta que el estudiante no haya realizado el recent_num no se puede establecer si avanzar o añadir ejercicios
    if len(recent_exercises) < recent_num:
        return 0
    
    failed_exercises = sum(1 for exercise in recent_exercises if exercise.status == "failed")
    failure_rate = failed_exercises / recent_num

    # print ("failed rate: ", failure_rate)

    # Si la tasa de fallos es demasiado baja, no asignar ejercicios adicionales
    if failure_rate < failure_rate_threshold:
        return 0

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
    
    # print ("time: ", normalized_time)

    weighted_sum = (weight_failure_rate * failure_rate + weight_time * normalized_time)
    
    recommended_exercises = max(0, round(weighted_sum * max_extra_exercises))  

    return recommended_exercises



# Obtención de ejercicios adicionales en base a los ejercicios fallados por el estudiante, y que tengan requerimientos similares no identicos.
def get_extra_exercises(student_id):
    difficulty_areas_counts = {}
    
    # Paso 1: Identificar Áreas de Dificultad y contar ocurrencias
    failed_exercises = StudentProgress.query.filter_by(student_id=student_id, status='failed').all()

    for progress in failed_exercises:
        exercise = Exercises.query.get(progress.exercise_id)

        if exercise and exercise.requirements:
            requirements = exercise.requirements.split(' ')
            for requirement in requirements:
                difficulty_areas_counts[requirement] = difficulty_areas_counts.get(requirement, 0) + 1

    # Seleccionar el requirement que ha sido fallado más veces
    primary_requirement = max(difficulty_areas_counts, key=difficulty_areas_counts.get, default=None)
    
    # print("primary requirement: ", primary_requirement)

    if not primary_requirement:
        return []

    # Paso 2: Buscar Ejercicios Adicionales
    potential_extra_exercises = Exercises.query.filter(
        Exercises.requirements.ilike(f"%{primary_requirement}%")
    ).all()

    attempted_exercise_ids = {progress.exercise_id for progress in StudentProgress.query.filter_by(student_id=student_id).all()}
    extra_exercises = [exercise for exercise in potential_extra_exercises if exercise.id not in attempted_exercise_ids]
    
    num_extra_exercises = determine_number_of_extra_exercises(student_id, primary_requirement)

    # print("num extra: ", num_extra_exercises)

    # Paso 3: Recomendar Ejercicios
    recommended_exercises = extra_exercises[:num_extra_exercises]

    # print ("recommended: ", recommended_exercises)

    return recommended_exercises











# --------- AVANZAR EJERCICIOS ---------

# Funcion que evalua el tiempo, para que no sea extremadamente pequeño ni grande,  y premie un tiempo medio o un poco inferior.
def time_score(actual_time, min_time, max_time):
    # Asegurando que min_time < max_time para evitar división por cero.
    if min_time == max_time:
        return 1  # O cualquier valor que tenga sentido en este contexto.
    
    # Normalizando el actual_time entre 0 y 1
    normalized_time = (actual_time - min_time) / (max_time - min_time)
    
    # Asegurando que el tiempo está en el rango [0,1]
    score = min(max(normalized_time, 0), 1)
    
    return score



# Devuelve el numero de ejercicios que se podrían saltar del estudiante
def determine_number_of_skipped_exercises(student_id, primary_requirement, recent_num=6, max_skip_exercises=3, pass_rate_threshold=0.6):
    recent_exercises = (StudentProgress.query
                        .filter_by(student_id=student_id)
                        .join(Exercises, StudentProgress.exercise_id == Exercises.id)
                        .filter(Exercises.requirements.ilike(f"%{primary_requirement}%"))
                        .order_by(StudentProgress.completion_date.desc())
                        .limit(recent_num)
                        .all())
    
    print ("longitud ejers encontrados: ", len(recent_exercises))
    print (recent_exercises)
    # Hasta que el estudiante no haya realizado el recent_num no se puede establecer si avanzar o añadir ejercicios
    if len(recent_exercises) < recent_num:
        return 0

    passed_exercises = sum(1 for exercise in recent_exercises if exercise.status == "completed")
    pass_rate = passed_exercises / recent_num
    
    # Si la tasa de aprobación está por debajo del umbral, no se salta ningún ejercicio
    if pass_rate < pass_rate_threshold:
        return 0

    # Recoger los tiempos de todos los ejercicios para encontrar el mínimo y el máximo
    all_times = [e.time_spent for e in recent_exercises]
    min_time = min(all_times)
    max_time = max(all_times)

    # Normalizar el tiempo del último ejercicio con respecto al rango [min_time, max_time]
    time_spent_last_exercise = recent_exercises[0].time_spent

    # Si hay 0 por algun motivo
    if time_spent_last_exercise == 0:
        time_spent_last_exercise = min_time

    time_performance = time_score(time_spent_last_exercise, min_time, max_time)

    # Ajustar los pesos según tu propia lógica y pruebas
    weight_pass_rate = 0.7
    weight_time = 0.3
    
    weighted_sum = (weight_pass_rate * pass_rate + weight_time * time_performance)

    print ("pass rate: ", pass_rate)
    print ("time_performance: ", time_performance)
    print ("suma de pesos: ", weighted_sum)

    recommended_skips = max(0, round(weighted_sum * max_skip_exercises))  

    return recommended_skips


# Devuelve los ejercicios que se deberían saltar
def get_advanced_exercises(student_id, min_successes=5, min_success_rate=0.8):
    proficiency_areas = set()
    
    # Paso 1: Identificar Áreas de Proficiencia y Determinar el Requisito Principal
    passed_exercises = StudentProgress.query.filter_by(student_id=student_id, status='completed').all()
    
    area_success_counts = defaultdict(int)
    area_attempt_counts = defaultdict(int)

    for progress in passed_exercises:
        exercise = Exercises.query.get(progress.exercise_id)

        if exercise and exercise.requirements:
            for area in exercise.requirements.split(', '):
                area_attempt_counts[area] += 1
                if progress.status == 'completed':
                    area_success_counts[area] += 1

    most_successful_area = None
    max_successes = 0

    for area, successes in area_success_counts.items():
        attempts = area_attempt_counts.get(area, 0)
        
        if successes >= min_successes and (successes / max(attempts, 1)) >= min_success_rate:
            proficiency_areas.add(area)
            
            if successes > max_successes:
                most_successful_area = area
                max_successes = successes

    primary_requirement = most_successful_area

    print("proficiency: ", proficiency_areas)
    print("primary requirement: ", primary_requirement)

    # Paso 2: Buscar Ejercicios Avanzados
    if primary_requirement:
        potential_advanced_exercises = (Exercises.query
            .join(GlobalOrder, Exercises.id == GlobalOrder.content_id)
            .filter(
                GlobalOrder.content_type == 'Exercises',
                Exercises.requirements.ilike(f"%{primary_requirement}%")
            )
            .order_by(GlobalOrder.global_order)
            .all())
    else:
        potential_advanced_exercises = []
        
    # Filtrar los ejercicios avanzados para incluir solo aquellos que el estudiante no ha intentado
    attempted_exercise_ids = {progress.exercise_id for progress in StudentProgress.query.filter_by(student_id=student_id).all()}
    advanced_exercises = [exercise for exercise in potential_advanced_exercises if exercise.id not in attempted_exercise_ids]

    # Paso 3: Recomendar Ejercicios
    # Usa determine_number_of_skipped_exercises para decidir cuántos ejercicios recomendar
    # Asumiendo que tienes una función determine_number_of_skipped_exercises definida en otro lugar
    num_skip_exercises = determine_number_of_skipped_exercises(student_id, primary_requirement)
    recommended_exercises = advanced_exercises[:num_skip_exercises]
    
    print ("num skip: ", num_skip_exercises)
    print ("recommended: ", recommended_exercises)

    return recommended_exercises
