from flask import Blueprint

from collections import defaultdict

from app.models import StudentProgress, Exercises, GlobalOrder, StudentActivity, TheoryRequirement, Theory, ExerciseRequirement, Requirement,  UserRequirementsCompleted, ModuleRequirementOrder

from app import db

from sqlalchemy import and_, asc

import random

module_blueprint = Blueprint('module', __name__)



# --------- AÑADIR EJERCICIOS ---------


# Número de ejercicios extra basándose en el rendimiento del estudiante.
def determine_number_of_extra_exercises(student_id, requirement, recent_num=5, max_extra_exercises=6, failure_rate_threshold=0.2):
    requirement_obj = Requirement.query.filter_by(name=requirement).first()
    
    if not requirement_obj:
        return 0

    # Identificar el primer ejercicio que NO está en la StudentActivity para este estudiante.
    next_exercise = (
        Exercises.query
        .join(ExerciseRequirement, Exercises.id == ExerciseRequirement.exercise_id)
        .join(GlobalOrder, Exercises.id == GlobalOrder.content_id)
        .outerjoin(
            StudentActivity, 
            and_(
                StudentActivity.content_id == Exercises.id, 
                StudentActivity.student_id == student_id
            )
        )
        .filter(
            GlobalOrder.content_type == 'Exercises',
            ExerciseRequirement.requirement_id == requirement_obj.id_requisito,
            StudentActivity.id == None  # No existe un registro correspondiente en StudentActivity.
        )
        .order_by(asc(GlobalOrder.global_order))  # Ordenar para obtener el próximo ejercicio.
        .first()
    )

    # Asegurarse de que se encontró un ejercicio.
    if next_exercise:
        current_module_id = next_exercise.module_id
    else:
        current_module_id = None

    # Asegurarse de que tenemos un `module_id` antes de realizar la consulta.
    if current_module_id:
        recent_exercises = (
            StudentProgress.query
            .join(Exercises, StudentProgress.exercise_id == Exercises.id)
            .join(ExerciseRequirement, Exercises.id == ExerciseRequirement.exercise_id)
            .filter(and_(
                StudentProgress.student_id == student_id,
                ExerciseRequirement.requirement_id == requirement_obj.id_requisito,
                Exercises.module_id == current_module_id  # Añadir este filtro
            ))
            .order_by(StudentProgress.completion_date.desc())
            .limit(recent_num)
            .all()
        )
    else:
        recent_exercises = []

    # Hasta que el estudiante no haya realizado el recent_num no se puede establecer si avanzar o añadir ejercicios
    if len(recent_exercises) < recent_num:
        return 0
    
    failed_exercises = sum(1 for exercise in recent_exercises if exercise.status == "failed")
    failure_rate = failed_exercises / recent_num

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
    
    weighted_sum = (weight_failure_rate * failure_rate + weight_time * normalized_time)
    
    recommended_exercises = max(0, round(weighted_sum * max_extra_exercises))  

    return recommended_exercises



# Obtención de ejercicios adicionales en base a los ejercicios fallados por el estudiante, y que tengan requerimientos similares no identicos.
def get_extra_exercises(student_id):
    difficulty_areas_counts = {}

    # Paso 1: Identificar Áreas de Dificultad y contar ocurrencias
    failed_exercises = StudentProgress.query.filter_by(student_id=student_id, status='failed').all()

    for progress in failed_exercises:
        exercise_requirements = ExerciseRequirement.query.filter_by(exercise_id=progress.exercise_id).all()

        for ex_req in exercise_requirements:
            requirement = Requirement.query.get(ex_req.requirement_id)
            if requirement:
                difficulty_areas_counts[requirement.name] = difficulty_areas_counts.get(requirement.name, 0) + 1

    # Seleccionar el requirement que ha sido fallado más veces
    primary_requirement = max(difficulty_areas_counts, key=difficulty_areas_counts.get, default=None)

    if not primary_requirement:
        return []

    # Paso 2: Buscar Ejercicios Adicionales
    primary_requirement_obj = Requirement.query.filter_by(name=primary_requirement).first()

    if not primary_requirement_obj:
        return []

    potential_extra_exercises = (
        Exercises.query
        .join(ExerciseRequirement, Exercises.id == ExerciseRequirement.exercise_id)
        .filter(ExerciseRequirement.requirement_id == primary_requirement_obj.id_requisito)
        .all()
    )

    attempted_exercise_ids = {progress.exercise_id for progress in StudentProgress.query.filter_by(student_id=student_id).all()}
    extra_exercises = [exercise for exercise in potential_extra_exercises if exercise.id not in attempted_exercise_ids]

    num_extra_exercises = determine_number_of_extra_exercises(student_id, primary_requirement)

    # Paso 3: Recomendar Ejercicios
    recommended_exercises = extra_exercises[:num_extra_exercises]

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


# Devuelve el numero de ejercicios que se podrían saltar del estudiante, , basado en su historial reciente.
def determine_number_of_skipped_exercises(student_id, primary_requirement, recent_num=6, max_skip_exercises=3, pass_rate_threshold=0.6):
    # Identificar el primer ejercicio que NO está en la StudentActivity para este estudiante.
    next_exercise = (
        Exercises.query
        .join(GlobalOrder, Exercises.id == GlobalOrder.content_id)
        .outerjoin(
            StudentActivity, 
            and_(
                StudentActivity.content_id == Exercises.id, 
                StudentActivity.student_id == student_id
            )
        )
        .filter(
            GlobalOrder.content_type == 'Exercises',
            StudentActivity.id == None  # No existe un registro correspondiente en StudentActivity.
        )
        .order_by(asc(GlobalOrder.global_order))  # Ordenar para obtener el próximo ejercicio.
        .first()
    )

    # Asegurarse de que se encontró un ejercicio.
    if next_exercise:
        current_module_id = next_exercise.module_id
    else:
        current_module_id = None


    # Asegurarse de que tenemos un `module_id` antes de realizar la consulta.
    if current_module_id:
        recent_exercises = (
            StudentProgress.query
            .join(Exercises, StudentProgress.exercise_id == Exercises.id)
            .join(ExerciseRequirement, ExerciseRequirement.exercise_id == Exercises.id)  # Únete a la tabla de relación
            .join(Requirement, ExerciseRequirement.requirement_id == Requirement.id_requisito)  # Luego, únete a la tabla de requisitos
            .filter(and_(
                StudentProgress.student_id == student_id,
                Requirement.name == primary_requirement,  # Filtra por el nombre del requisito
                Exercises.module_id == current_module_id
            ))
            .order_by(StudentProgress.completion_date.desc())
            .limit(recent_num)
            .all()
        )
    else:
        recent_exercises = []

    # Verificar si hay suficientes ejercicios recientes para considerar
    if len(recent_exercises) < recent_num:
        return 0
    
    effective_pass_count = 0
    unique_exercise_ids = set()
    for exercise in recent_exercises:
        # ID del ejercicio único
        unique_exercise_ids.add(exercise.exercise_id)

        # Ajustamos solo para ejercicios completados
        if exercise.status == "completed":
            previous_fails = (StudentProgress.query
                              .filter_by(student_id=student_id, exercise_id=exercise.exercise_id, status="failed")
                              .count())
            # Hay que sumarle uno porque el completado tambien cuenta como intento
            adjuster = max(1, previous_fails + 1)
            effective_pass_count += 1/adjuster
    
    num_unique_exercises = len(unique_exercise_ids)  # Número de ejercicios únicos intentados

    # Calcular la tasa de éxito y verificar contra el umbral
    pass_rate = effective_pass_count / num_unique_exercises
    if pass_rate < pass_rate_threshold:
        return 0
    
    # Recoger los tiempos de todos los ejercicios para encontrar el mínimo y el máximo
    all_times = [e.time_spent for e in recent_exercises]
    min_time = min(all_times)
    max_time = max(all_times)
    
    # Normalizar el tiempo del último ejercicio con respecto al rango [min_time, max_time]
    time_spent_last_exercise = recent_exercises[0].time_spent
    
    # Proteger contra divisiones por cero
    if time_spent_last_exercise == 0:
        time_spent_last_exercise = min_time
    
    # Función para calcular el rendimiento en función del tiempo
    def time_score(time, min_t, max_t):
        return (max_t - time) / (max_t - min_t)

    time_performance = time_score(time_spent_last_exercise, min_time, max_time)
    
    # Ponderar y sumar métricas
    weight_pass_rate = 0.7
    weight_time = 0.3
    weighted_sum = (weight_pass_rate * pass_rate + weight_time * time_performance)
    
    # Calcular y devolver la cantidad recomendada de ejercicios para saltar
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

        if exercise:
            for requirement in exercise.requirements:
                area = requirement.name 
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

    # Paso 2: Buscar Ejercicios Avanzados
    if primary_requirement:
        potential_advanced_exercises = (Exercises.query
            .join(GlobalOrder, Exercises.id == GlobalOrder.content_id)
            .join(ExerciseRequirement, Exercises.id == ExerciseRequirement.exercise_id)  # Únete a la tabla de relación
            .join(Requirement, ExerciseRequirement.requirement_id == Requirement.id_requisito)  # Luego, únete a la tabla de requisitos
            .filter(
                GlobalOrder.content_type == 'Exercises',
                Requirement.name == primary_requirement  # Filtra por el nombre del requisito
            )
            .order_by(GlobalOrder.global_order)
            .all())
    else:
        potential_advanced_exercises = []

    # Filtrar los ejercicios avanzados para incluir solo aquellos que el estudiante no ha intentado
    attempted_exercise_ids = {activity.content_id for activity in StudentActivity.query.filter_by(student_id=student_id, done=True).all()}
    advanced_exercises = [exercise for exercise in potential_advanced_exercises if exercise.id not in attempted_exercise_ids]

    # Paso 3: Recomendar Ejercicios
    # Usa determine_number_of_skipped_exercises para decidir cuántos ejercicios recomendar
    # Asumiendo que tienes una función determine_number_of_skipped_exercises definida en otro lugar
    num_skip_exercises = determine_number_of_skipped_exercises(student_id, primary_requirement)

    recommended_exercises = advanced_exercises[:num_skip_exercises]

    
    return recommended_exercises



# --- CAMBIO DE ESTRUCTURA ---

def get_current_module_and_next_requirement_for_user(user_id):
    # Primero, obtenemos el último requisito completado para este usuario.
    last_completed = db.session.query(UserRequirementsCompleted)\
                               .filter_by(user_id=user_id)\
                               .order_by(UserRequirementsCompleted.completion_date.desc())\
                               .first()

    # Si el usuario no ha completado ningún requisito, retorna el primer módulo y su primer requisito.
    if not last_completed:
        first_module = db.session.query(ModuleRequirementOrder.module_id).order_by(ModuleRequirementOrder.module_id).first()
        if not first_module:
            return None  # No se encontraron módulos.

        first_requirement = db.session.query(ModuleRequirementOrder)\
                                    .filter_by(module_id=first_module[0])\
                                    .order_by(ModuleRequirementOrder.order_position)\
                                    .first()
        return first_module[0], first_requirement

    current_module_id = last_completed.module_id
    last_order_position = db.session.query(ModuleRequirementOrder.order_position)\
                                    .filter_by(module_id=current_module_id, requirement_id=last_completed.requirement_id)\
                                    .first()
    
    if not last_order_position:
        return None  # No se encontró la posición de orden para el último requisito completado.

    next_requirement = db.session.query(ModuleRequirementOrder)\
                                .filter_by(module_id=current_module_id)\
                                .filter(ModuleRequirementOrder.order_position > last_order_position[0])\
                                .order_by(ModuleRequirementOrder.order_position)\
                                .first()

    # Si no hay un siguiente requisito en el módulo actual, movemos al usuario al siguiente módulo.
    if not next_requirement:
        next_module = db.session.query(ModuleRequirementOrder.module_id)\
                                .filter(ModuleRequirementOrder.module_id > current_module_id)\
                                .order_by(ModuleRequirementOrder.module_id)\
                                .first()

        # Si no hay un siguiente módulo, significa que el estudiante ha completado todos los módulos y requisitos.
        if not next_module:
            return None  # Todo completado.

        # Buscamos el primer requisito del nuevo módulo.
        first_requirement_in_next_module = db.session.query(ModuleRequirementOrder)\
                                                .filter_by(module_id=next_module[0])\
                                                .order_by(ModuleRequirementOrder.order_position)\
                                                .first()
        return next_module[0], first_requirement_in_next_module

    # Retorna el módulo actual y el próximo requisito en ese módulo.
    return current_module_id, next_requirement


def select_exercise_for_user(user_id, requirement_id):
    # 2.2.1: Obtener la lista de ejercicios para el requisito actual
    available_exercises = db.session.query(Exercises)\
                                    .join(Exercises.requirements)\
                                    .filter(Requirement.id_requisito == requirement_id)\
                                    .all()

    # 2.2.2: Obtener todos los registros de progreso del estudiante para los ejercicios relacionados con el requirement_id
    student_progress_records = db.session.query(StudentProgress.exercise_id, StudentProgress.status)\
                                        .filter_by(student_id=user_id)\
                                        .all()

    completed_exercise_ids = [record[0] for record in student_progress_records if record[1] == 'completed']
    failed_exercise_ids = [record[0] for record in student_progress_records if record[1] == 'failed']

    # Eliminar de la lista de ejercicios fallados aquellos ejercicios que el estudiante ha completado posteriormente
    failed_exercise_ids = [exercise_id for exercise_id in failed_exercise_ids if exercise_id not in completed_exercise_ids]


    # Filtramos la lista de ejercicios disponibles para excluir los completados y los fallados
    valid_exercises = [exercise for exercise in available_exercises if exercise.id not in completed_exercise_ids and exercise.id not in failed_exercise_ids]

    if not (valid_exercises):
        return random.choice(failed_exercise_ids)

    # 2.2.3: Identificar si hay algún ejercicio clave pendiente
    key_exercises = [exercise for exercise in valid_exercises if exercise.is_key_exercise]

    # 2.2.4: Si hay ejercicios clave pendientes y el estudiante ha completado al menos 4-5 ejercicios
    completed_exercises_count = len(completed_exercise_ids)

    if key_exercises and completed_exercises_count >= 4:
        failed_key_exercises = db.session.query(StudentProgress.exercise_id)\
                                         .filter_by(user_id=user_id, status='failed', is_key_exercise=True)\
                                         .all()
        if failed_key_exercises:
            # Obtener la lista de ejercicios asignados después de fallar el ejercicio clave
            assigned_exercises_after_fail = db.session.query(StudentProgress)\
                                                      .filter_by(user_id=user_id)\
                                                      .filter(StudentProgress.assigned_date > failed_key_exercises[0].assigned_date)\
                                                      .all()

            completed_after_fail = [exercise for exercise in assigned_exercises_after_fail if exercise.status == 'completed']

            # Si el estudiante ha completado 3 ejercicios después de fallar, reintroduce el ejercicio clave
            if len(completed_after_fail) >= 3:
                return random.choice(key_exercises)
            else:
                # Si no ha completado 3 ejercicios, proporciona ejercicios adicionales
                non_key_exercises = [exercise for exercise in valid_exercises if not exercise.is_key_exercise]
                if non_key_exercises:
                    return random.choice(non_key_exercises)
        else:
            # Si no ha fallado, seleccionar un ejercicio clave
            return random.choice(key_exercises)

    # 2.2.5: Seleccionar un ejercicio adecuado
    # Si no hay ejercicios válidos disponibles, devuelve None
    if not valid_exercises:
        return None

    # En otros casos, simplemente seleccionar un ejercicio al azar
    return random.choice(valid_exercises)


def assign_exercise_to_student(user_id, exercise):
    if not exercise:
        # No hay ejercicio válido para asignar, por lo que no hacemos nada
        return None

    # Siempre creamos una nueva entrada para este estudiante y ejercicio
    new_progress = StudentProgress(
        student_id=user_id,
        exercise_id=exercise.id,
        status='in progress'
    )
    db.session.add(new_progress)

    # Finalmente, hacemos commit de los cambios en la base de datos
    db.session.commit()

    # Retorna el ejercicio asignado (por si lo necesitas para algo más)
    return exercise


def handle_all_exercises_completed_or_failed(user_id, requirement_id):
    # Primero, verifica si todos los ejercicios para este requisito han sido completados o fallados
    all_exercises_for_requirement = db.session.query(Exercises)\
                                               .join(Exercises.requirements)\
                                               .filter(Requirement.id_requisito == requirement_id)\
                                               .all()

    all_exercise_ids_for_requirement = [exercise.id for exercise in all_exercises_for_requirement]

    completed_and_failed_exercise_ids = db.session.query(StudentProgress.exercise_id)\
                                                  .filter_by(student_id=user_id)\
                                                  .filter(StudentProgress.exercise_id.in_(all_exercise_ids_for_requirement))\
                                                  .filter(or_(StudentProgress.status == 'completed', StudentProgress.status == 'failed'))\
                                                  .all()

    completed_and_failed_exercise_ids = [exercise[0] for exercise in completed_and_failed_exercise_ids]

    # Si todos los ejercicios para este requisito han sido completados o fallados
    # Considera reasignar un ejercicio que el estudiante haya fallado previamente
    if set(all_exercise_ids_for_requirement) == set(completed_and_failed_exercise_ids):
        failed_exercises = db.session.query(StudentProgress.exercise_id)\
                                    .filter_by(student_id=user_id, status='failed')\
                                    .all()
        if failed_exercises:
            return random.choice(failed_exercises)  # Devuelve un ejercicio fallado al azar para reintentarlo
        
        # O considera mover al estudiante al siguiente requisito
        next_module, next_requirement = get_current_module_and_next_requirement_for_user(user_id)
        if next_requirement:
            # Selecciona un ejercicio para el nuevo requisito
            return select_exercise_for_user(user_id, next_requirement.requirement_id)

    return None  # Retorna None si no se toma ninguna acción


def get_next_module_and_first_requirement_for_user(user_id):
    # Obtenemos los módulos completados por el usuario
    completed_modules = db.session.query(UserRequirementsCompleted.module_id
                                        ).filter(UserRequirementsCompleted.user_id == user_id
                                        ).distinct().all()
    
    completed_module_ids = [module[0] for module in completed_modules]

    # Obtenemos el primer módulo que no haya sido completado por el usuario
    next_module = db.session.query(ModuleRequirementOrder
                                ).filter(~ModuleRequirementOrder.module_id.in_(completed_module_ids)
                                ).order_by(ModuleRequirementOrder.module_id
                                ).first()

    if not next_module:
        # El usuario ha completado todos los módulos
        return None, None

    # Obtenemos el primer requisito del módulo siguiente
    first_requirement = db.session.query(ModuleRequirementOrder
                                        ).filter(ModuleRequirementOrder.module_id == next_module.module_id
                                        ).order_by(ModuleRequirementOrder.order_position
                                        ).first()


    return next_module.module_id, first_requirement.requirement


def get_exercise(exercise_id):
    return Exercises.query.filter_by(id=exercise_id).first()

def get_theory(theory_id):
    return Theory.query.filter_by(id=theory_id).first()

# Check if there's any unseen theory for the user and requirement
def get_next_theory_for_user(student_id, requirement_id):
    last_theory = db.session.query(StudentActivity)\
                            .filter_by(student_id=student_id, content_type='Theory')\
                            .order_by(StudentActivity.content_id.desc())\
                            .first()

    if last_theory:
        next_theory = db.session.query(TheoryRequirement)\
                                .filter_by(id_requirement=requirement_id)\
                                .filter(TheoryRequirement.id_theory > last_theory.content_id)\
                                .first()
        if next_theory:
            return next_theory.id_theory
    else:
        # If the student hasn't seen any theory for the requirement yet
        first_theory = db.session.query(TheoryRequirement)\
                                    .filter_by(id_requirement=requirement_id)\
                                    .first()
        if first_theory:
            return first_theory.id_theory
    return None