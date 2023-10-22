from flask import Blueprint

from app.models import StudentProgress, Exercises, StudentActivity, TheoryRequirement, Theory, Requirement,  UserRequirementsCompleted, ModuleRequirementOrder

from app import db

from sqlalchemy import and_, asc, or_

import random

module_blueprint = Blueprint('module', __name__)

# --- PARA MOSTRAR EL CAMINO DE FORMA ALEATORIA ---

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
                                        .join(Exercises, Exercises.id == StudentProgress.exercise_id)\
                                        .filter(StudentProgress.student_id==user_id, StudentProgress.status=='failed', Exercises.is_key_exercise==True)\
                                        .all()

        if failed_key_exercises:
            # Obtener la lista de ejercicios asignados después de fallar el ejercicio clave
            assigned_exercises_after_fail = db.session.query(StudentProgress)\
                                                      .filter_by(student_id=user_id)\
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



# --- PARA LA CORRECION AUTOMATICA DEL EJERCICIO ---