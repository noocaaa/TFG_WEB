from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import current_user, login_required

from app import db, bcrypt
from app.models import Users, Exercises, Module, Theory, Requirement, ExerciseRequirement, ModuleRequirementOrder

from werkzeug.utils import secure_filename

from datetime import datetime

import json, os, uuid

admin_blueprint = Blueprint('admin', __name__)

ALLOWED_EXTENSIONS_img = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS_img

def is_valid_json(data):
    try:
        json.loads(data)
        return True
    except ValueError:
        return False

def obtener_datos():
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    requirements = Requirement.query.all()
    modules = Module.query.all()
    modulesRequirement = ModuleRequirementOrder.query.all()

    return modules, exercises, teachers, theory, requirements, modulesRequirement

@admin_blueprint.route('/admin_dashboard')
@login_required
def admin_dashboard():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    modules = Module.query.all()
    
    # Filtrar ejercicios basado en los criterios para la edición
    edit_filter_id = request.args.get('edit_filter_id')
    edit_filter_language = request.args.get('edit_filter_language')
    edit_filter_name = request.args.get('edit_filter_name')
    edit_mode = request.args.get('editMode') == 'true'
    
    exercises_query = Exercises.query

    if edit_filter_id:
        exercises_query = exercises_query.filter(Exercises.id == edit_filter_id)
    if edit_filter_language:
        exercises_query = exercises_query.filter(Exercises.language == edit_filter_language)
    if edit_filter_name:
        exercises_query = exercises_query.filter(Exercises.name.contains(edit_filter_name))

    filtered_exercises = exercises_query.all()

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    # Aquí sobreescribes "exercises" con "filtered_exercises"
    exercises = filtered_exercises

    edit_mode = request.args.get('editMode') == 'true'

    return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, edit_mode=edit_mode)



# ---------- ADD ----------


@admin_blueprint.route('/admin/add_exercise', methods=['POST'])
@login_required
def add_exercise():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:
        return redirect(url_for('control.login'))

    title = request.form['title']
    module_id = request.form['module_id']
    language = request.form['language']
    requirements = request.form['requirements']
    is_evaluation = 'evaluationExercise' in request.form  # Esto devolverá True si el checkbox está marcado, de lo contrario, False.
    reference_solution = request.form['reference_solution']

    # Variables comunes para el renderizado
    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    # Comprobar si el ejercicio ya existe
    existing_exercise = Exercises.query.filter_by(name=title, module_id=module_id).first()
    if existing_exercise:
        error_msg = 'Ya existe un ejercicio con ese nombre en el módulo seleccionado.'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, error=error_msg)

    test_vf = request.form['test_verification']

    # Por si el ID del modulo no está
    module = Module.query.get(module_id)
    if not module:
        error_msg = 'El ID del módulo introducido no es correcto.'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, error=error_msg)

    # Intenta decodificar el JSON
    if not is_valid_json(test_vf):
        error_msg = 'El campo SOLUTION no contiene un JSON válido.'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, error=error_msg)

    # Crear el nuevo ejercicio sin el campo de requisitos por ahora
    exercise = Exercises(
        name=title,
        content=request.form['content'],
        solution=request.form['solution'],
        module_id=module_id,
        test_verification=test_vf,
        language=language,
        is_key_exercise=is_evaluation,
        reference_solution=reference_solution
    )

    # Dividir la cadena de requisitos en una lista y añadirlos a la tabla ExerciseRequirement
    # Aquí asociamos los requisitos seleccionados con la teoría
    requirements = request.form.getlist('requirements')
    for req_id in requirements:
        req = Requirement.query.get(req_id)
        if req:
            exercise.requirements.append(req)

    db.session.add(exercise)
    db.session.flush()  # Esto es necesario para que el ejercicio obtenga su ID después de ser agregado a la sesión

    db.session.commit()
    
    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory)

@admin_blueprint.route('/admin/add_module', methods=['POST'])
@login_required
def add_module():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    module_name = request.form['module_name']

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    existing_module = Module.query.filter_by(name=module_name).first()
    if existing_module:
        error_msg = 'Ya existe un módulo con ese nombre.'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, error=error_msg)

    module = Module(
        name=module_name,
        description=request.form['module_description'],
    )
    db.session.add(module)
    db.session.commit()

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory)


@admin_blueprint.route('/admin/add_teacher', methods=['POST'])
@login_required
def add_teacher():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))


    teacher_id = request.form['teacher_id']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    birth_date = request.form['birth_date']
    city = request.form['city']
    gender = request.form['gender']
    email = request.form['email']
    password = request.form['password']

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    # Verificar si el correo ya existe
    existing_user = Users.query.filter_by(email=email).first()

    if existing_user:
        error_msg = 'Ese correo ya está registrado'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, error=error_msg)

    # Verificar si el ID del profesor ya existe
    existing_teacher_id = Users.query.get(teacher_id)

    if existing_teacher_id:
        error_msg = 'El ID introducido ya está registrado'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, error=error_msg)

    # Hash the password using Flask-Bcrypt
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    new_teacher = Users(
        id=teacher_id,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        city=city,
        gender=gender,
        email=email,
        password=hashed_password,
        type_user="X",
        avatar_id = None
    )

    db.session.add(new_teacher)
    db.session.commit()

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    return  render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory)


@admin_blueprint.route('/admin/add_theory', methods=['POST'])
@login_required
def add_theory():
    # Recopilar datos desde el formulario
    module_id = request.form.get('module_id')
    content = request.form.get('content')

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    #Por si el ID del modulo no esta
    module = Module.query.get(module_id)
    if not module:
        error_msg = 'El ID del módulo introducido no es correcto.'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, error=error_msg)

    # Validar datos (puedes añadir más validaciones según lo necesites)
    if not module_id or not content:
        error_msg = 'Todos los campos son obligatorios.'
        return  render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, error=error_msg)

    image = request.files.get('image')

    if image and image.filename:  # Verifica que el archivo tiene un nombre
        # Asegúrate de que el archivo es una imagen
        if not allowed_file(image.filename):
            error_msg = 'Tipo de archivo no permitido. Asegúrate de subir una imagen.'
            return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, error=error_msg)

        # Obtener la extensión del archivo
        file_ext = os.path.splitext(image.filename)[1]
        # Generar un nombre de archivo único
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}{file_ext}"
        filename = secure_filename(unique_filename)

        image_path = os.path.join("./app/static/asked_questions", filename)
        image.save(image_path)
        new_theory = Theory(module_id=module_id, content=content, image_path=image_path)
    else:
        new_theory = Theory(module_id=module_id, content=content)

    # Aquí asociamos los requisitos seleccionados con la teoría
    requirements = request.form.getlist('requirements')
    for req_id in requirements:
        req = Requirement.query.get(req_id)
        if req:
            new_theory.requirements.append(req)

    # Crear y guardar la nueva entrada de teoría en la base de datos
    db.session.add(new_theory)
    db.session.commit()

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    return render_template('admin_dashboard.html', modules=modules, modules_requirements = modulesRequirement, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory)


@admin_blueprint.route('/admin/add_requirement', methods=['POST'])
@login_required
def add_requirement():
    # Recopilar datos desde el formulario
    requirement_name = request.form.get('requirement_name')

    # Intentar obtener la teoría usando el ID
    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    # Validar datos
    if not requirement_name:
        error_msg = 'El nombre del requisito es obligatorio.'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, error=error_msg)

    # Verificar si el requisito ya existe
    existing_requirement = Requirement.query.filter_by(name=requirement_name).first()
    if existing_requirement:
        error_msg = 'El requisito ya existe.'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, error=error_msg)

    # Crear y guardar el nuevo requisito en la base de datos
    new_requirement = Requirement(name=requirement_name)
    db.session.add(new_requirement)
    db.session.commit()

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory)


# ---------- UPDATE ----------



@admin_blueprint.route('/admin/update_module', methods=['POST'])
@login_required
def update_module():
    if not current_user.is_authenticated:
        return redirect(url_for('control.login'))

    for key, value in request.form.items():
        if key.startswith("name_"):
            module_id = int(key.split("_")[1])
            module = Module.query.get(module_id)
            module.name = value
        elif key.startswith("description_"):
            module_id = int(key.split("_")[1])
            module = Module.query.get(module_id)
            module.description = value

    db.session.commit()

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()


    return  render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory)


@admin_blueprint.route('/admin/update_exercise', methods=['POST'])
@login_required
def update_exercise():
    if not current_user.is_authenticated:
        return redirect(url_for('control.login'))

    prefixes = ["name_", "content_", "solution_", "test_verification_", "requirements_", "language_"]

    for key, value in request.form.items():
        if any(prefix in key for prefix in prefixes):
            exercise_id = int(key.split("_")[-1])
            exercise = Exercises.query.get(exercise_id)

            if key.startswith("name_"):
                exercise.name = value
            elif key.startswith("content_"):
                exercise.content = value
            elif key.startswith("solution_"):
                exercise.solution = value
            elif key.startswith("test_verification_"):
                exercise.test_verification = value
            elif key.startswith("requirements_"):
                # Primero, borra todas las relaciones existentes de requisitos para este ejercicio
                ExerciseRequirement.query.filter_by(exercise_id=exercise_id).delete()

                requirement_ids = request.form.getlist(f'requirements_{exercise_id}') 
                requirement_ids = [rid for rid in requirement_ids if rid and rid.isdigit()]

                for req_id in requirement_ids:
                    # Asegura que req_id no esté vacío y sea un número
                    if req_id and req_id.isdigit():  
                        requirement_obj = Requirement.query.get(req_id)
                        # Añadir la relación entre el ejercicio y el requisito
                        if requirement_obj: 
                            exercise_requirement = ExerciseRequirement(exercise_id=exercise.id, requirement_id=requirement_obj.id_requisito)
                            db.session.add(exercise_requirement)
            elif key.startswith("language_"):
                exercise.language = value
            elif key.startswith("reference_solution_"):
                exercise.reference_solution = value

    db.session.commit()

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, requirements=requirements, teachers=teachers, theory=theory)

@admin_blueprint.route('/admin/update_teacher', methods=['POST'])
@login_required
def update_teacher():
    if not current_user.is_authenticated:
        return redirect(url_for('control.login'))

    # Prefixes que vamos a buscar en el formulario
    prefixes = ["first_name_", "last_name_", "birth_date_", "city_", "gender_", "email_"]

    for key, value in request.form.items():
        # Verificamos si el key actual contiene alguno de los prefixes definidos
        if any(prefix in key for prefix in prefixes):
            user_id = int(key.split("_")[-1])
            user = Users.query.get(user_id)

            if key.startswith("first_name_"):
                user.first_name = value
            elif key.startswith("last_name_"):
                user.last_name = value
            elif key.startswith("birth_date_"):
                user.birth_date = datetime.strptime(value, '%Y-%m-%d').date()
            elif key.startswith("city_"):
                user.city = value
            elif key.startswith("gender_"):
                user.gender = value
            elif key.startswith("email_"):
                user.email = value

    db.session.commit()

    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    return  render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory)


@admin_blueprint.route('/admin/update_theory/<int:theory_id>', methods=['POST'])
@login_required
def update_theory(theory_id):
    # Obtener todas las teorías, ejercicios y profesores para el template
    modules, exercises, teachers, theory_all, requirements, modulesRequirement = obtener_datos()

    # Obtener la teoría específica
    theory = Theory.query.get(theory_id)
    if not theory:
        error_msg = 'Teoría no encontrada.'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, requirements=requirements, exercises=exercises, teachers=teachers, theory=theory_all, error=error_msg)

    # Recopilar datos desde el formulario
    content = request.form.get(f'content_{theory_id}')

    # Validar datos
    if not content:
        error_msg = 'El contenido es obligatorio.'
        return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, requirements=requirements, exercises=exercises, teachers=teachers, theory=theory_all, error=error_msg)

    # Actualizar y guardar los cambios en la base de datos
    theory.content = content

    db.session.commit()

    return render_template('admin_dashboard.html', modules_requirements = modulesRequirement, modules=modules, requirements=requirements, exercises=exercises, teachers=teachers, theory=theory_all)


# ------------------- DELETE -------------------

@admin_blueprint.route('/admin/delete', methods=['POST'])
@login_required
def delete_element():
    # Comprobar si el usuario está loggeado y es administrador
    if not current_user.is_authenticated or current_user.type_user != 'T':
        return redirect(url_for('control.login'))
    
    element_type = request.form.get('element_type')
    element_id = request.form.get('element_id')
    requirement_id = request.form.get('requirement_id') if element_type == 'requirement' else None

    if element_type == 'module':
        # Lógica para eliminar módulo
        module_to_delete = Module.query.get(element_id)
        if module_to_delete:
            db.session.delete(module_to_delete)
            db.session.commit()
        else:
            error_msg = 'Módulo no encontrado.'
    
    elif element_type == 'exercise':
        # Lógica para eliminar ejercicio
        exercise_to_delete = Exercises.query.get(element_id)
        if exercise_to_delete:
            db.session.delete(exercise_to_delete)
            db.session.commit()
        else:
            error_msg = 'Ejercicio no encontrado.'
    
    elif element_type == 'teacher':
        # Lógica para eliminar profesor
        teacher_to_delete = Users.query.get(element_id)
        if teacher_to_delete:
            db.session.delete(teacher_to_delete)
            db.session.commit()
        else:
            error_msg = 'Profesor no encontrado.'
    
    elif element_type == 'theory':
        # Lógica para eliminar teoría
        theory_to_delete = Theory.query.get(element_id)
        if theory_to_delete:
            db.session.delete(theory_to_delete)
            db.session.commit()
        else:
            error_msg = 'Teoría no encontrada.'
    
    elif element_type == 'requirement' and requirement_id:
        # Lógica para eliminar requisito
        requirement_to_delete = Requirement.query.get(requirement_id)
        if requirement_to_delete:
            db.session.delete(requirement_to_delete)
            db.session.commit()
        else:
            error_msg ='Requisito no encontrado.'
    
    else:
        error_msg = 'Tipo de elemento no válido o ID faltante.'

    # Recargar los datos después de la eliminación para la plantilla
    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()
    return render_template('admin_dashboard.html',  modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, error=error_msg)

# ---- CONSULTA ----

@admin_blueprint.route('/filtrar_ejercicios', methods=['GET'])
@login_required
def filtrar_ejercicios():
    # Obtén los parámetros del formulario
    mod = request.args.get('language')
    selected_requirement = request.args.get('requirement_id')

    # Comienza con una consulta base de todos los ejercicios
    exercises_query = Exercises.query

    # Filtra por lenguaje si uno fue seleccionado
    if mod:
        exercises_query = exercises_query.filter(Exercises.module_id == mod)

    # Filtra por requisito si uno fue seleccionado
    if selected_requirement:
        exercises_query = exercises_query.join(ExerciseRequirement).filter(ExerciseRequirement.requirement_id == selected_requirement)

    # Obtén los resultados finales
    exercises = exercises_query.all()

    exercises_data = [{'id': ex.id, 'module_id': ex.module_id, 'name': ex.name, 'language': ex.language, 'requirements': [req.name for req in ex.requirements], 'is_key_exercise': ex.is_key_exercise} for ex in exercises]
    return jsonify(exercises=exercises_data)

# ---- GLOBAL ORDER ----

@admin_blueprint.route('/admin/update_global_order', methods=['POST'])
@login_required
def update_global_order():
    # Obtener el módulo y el requisito junto con la nueva posición desde el formulario
    module_id = int(request.form.get('module_id'))
    requirement_id = request.form['requirement_id']
    new_order_position = int(request.form.get('order_position'))

    # Verifica si ya existe un registro para el módulo y requisito dados
    existing_order = ModuleRequirementOrder.query.filter_by(
        module_id=module_id, 
        requirement_id=requirement_id
    ).first()

    # Si existe, actualiza su posición
    if existing_order:
        existing_order.order_position = new_order_position
    else:
        # Si no existe, crea uno nuevo
        new_order = ModuleRequirementOrder(
            module_id=module_id,
            requirement_id=requirement_id,
            order_position=new_order_position
        )
        db.session.add(new_order)

        # Encuentra el registro que queremos mover
        existing_order = ModuleRequirementOrder.query.filter_by(
            module_id=module_id, 
            requirement_id=requirement_id
        ).first()

        # Encuentra los registros cuyo orden debe incrementarse
        # Es decir, los que están en la posición de la nueva posición en adelante
        orders_to_update = ModuleRequirementOrder.query.filter(
            ModuleRequirementOrder.order_position >= new_order_position
        ).filter(
            ModuleRequirementOrder.id != existing_order.id  # Excluye el registro que estamos moviendo
        ).all()

        # Incrementa su posición para hacer espacio para el nuevo
        for order in orders_to_update:
            order.order_position += 1

        # Si el registro existe, actualiza su posición al nuevo valor
        if existing_order:
            existing_order.order_position = new_order_position
        else:
            # Si no existe, crea uno nuevo
            new_order = ModuleRequirementOrder(
                module_id=module_id,
                requirement_id=requirement_id,
                order_position=new_order_position
            )
            db.session.add(new_order)

    # Guarda los cambios en la base de datos
    db.session.commit()

    # Obtener datos actualizados para renderizar en el template
    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    # Renderiza el template con los datos actualizados
    return render_template('admin_dashboard.html',  modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory)


@admin_blueprint.route('/admin/delete_from_position', methods=['POST'])
@login_required
def delete_from_position():
    # Asumimos que recibimos la posición a eliminar desde el formulario
    position_to_delete = request.form.get('position_to_delete', type=int)

    # Obtener el registro a eliminar
    record_to_delete = ModuleRequirementOrder.query.filter_by(order_position=position_to_delete).first()

    if record_to_delete:
        # Eliminar el registro
        db.session.delete(record_to_delete)
        db.session.commit()

        # Seleccionar todos los registros con una posición mayor a la eliminada
        subsequent_records = ModuleRequirementOrder.query.filter(
            ModuleRequirementOrder.order_position > position_to_delete
        ).order_by(ModuleRequirementOrder.order_position.asc()).all()

        # Decrementar la posición de esos registros en 1
        for record in subsequent_records:
            record.order_position -= 1
            db.session.commit()  # Puedes hacer esto después del bucle si prefieres hacer un solo commit
    else:
        error_msg = 'No se encontró el registro en la posición indicada.'
    
    # Obtener datos actualizados para renderizar en el template
    modules, exercises, teachers, theory, requirements, modulesRequirement = obtener_datos()

    # Renderiza el template con los datos actualizados
    return render_template('admin_dashboard.html',  modules_requirements = modulesRequirement, modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, error=error_msg)


