from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user, login_required

from app import db, bcrypt
from app.models import Users, Exercises, Module, Theory, GlobalOrder, Requirement, ExerciseRequirement

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
    
    exercises = exercises_query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()

    edit_mode = request.args.get('editMode') == 'true'

    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, theory=theory, requirements=requirements, edit_mode=edit_mode, global_orders=global_orders)



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

    # Variables comunes para el renderizado
    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()

    # Comprobar si el ejercicio ya existe
    existing_exercise = Exercises.query.filter_by(name=title, module_id=module_id).first()
    if existing_exercise:
        error_msg = 'Ya existe un ejercicio con ese nombre en el módulo seleccionado.'
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, theory=theory, global_orders=global_orders, error=error_msg)

    test_vf = request.form['test_verification']

    # Por si el ID del modulo no está
    module = Module.query.get(module_id)
    if not module:
        error_msg = 'El ID del módulo introducido no es correcto.'
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, theory=theory, global_orders=global_orders, error=error_msg)

    # Intenta decodificar el JSON
    if not is_valid_json(test_vf):
        error_msg = 'El campo SOLUTION no contiene un JSON válido.'
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, theory=theory, global_orders=global_orders, error=error_msg)

    # Dividir la cadena de requisitos en una lista y añadirlos a la tabla ExerciseRequirement
    # Aquí asociamos los requisitos seleccionados con la teoría
    requirements = request.form.getlist('requirements')
    for req_id in requirements:
        req = Requirement.query.get(req_id)
        if req:
            exercise.requirements.append(req)

    # Crear el nuevo ejercicio sin el campo de requisitos por ahora
    exercise = Exercises(
        name=title,
        content=request.form['content'],
        solution=request.form['solution'],
        module_id=module_id,
        test_verification=test_vf,
        language=language,
        requirements=requirements, 
        is_key_exercise=is_evaluation
    )

    db.session.add(exercise)
    db.session.flush()  # Esto es necesario para que el ejercicio obtenga su ID después de ser agregado a la sesión

    db.session.commit()

    exercises = Exercises.query.all()
    requirements = Requirement.query.all()

    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders)

@admin_blueprint.route('/admin/add_module', methods=['POST'])
@login_required
def add_module():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    module_name = request.form['module_name']

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()


    existing_module = Module.query.filter_by(name=module_name).first()
    if existing_module:
        error_msg = 'Ya existe un módulo con ese nombre.'
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, theory=theory, global_orders=global_orders, error=error_msg)

    module = Module(
        name=module_name,
        description=request.form['module_description'],
    )
    db.session.add(module)
    db.session.commit()

    modules = Module.query.all()
    requirements = Requirement.query.all()

    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders)


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

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()


    # Verificar si el correo ya existe
    existing_user = Users.query.filter_by(email=email).first()
    if existing_user:
        error_msg = 'Ese correo ya está registrado'
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, theory=theory, global_orders=global_orders, error=error_msg)

    # Verificar si el ID del profesor ya existe
    existing_teacher_id = Users.query.get(teacher_id)
    if existing_teacher_id:
        error_msg = 'El ID introducido ya está registrado'
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, theory=theory, global_orders=global_orders, error=error_msg)

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

    teachers = Users.query.filter_by(type_user="X").all()
    requirements = Requirement.query.all()

    flash('Profesor añadido con éxito', 'success')
    return  render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders)


@admin_blueprint.route('/admin/add_theory', methods=['POST'])
@login_required
def add_theory():
    # Recopilar datos desde el formulario
    module_id = request.form.get('module_id')
    content = request.form.get('content')

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()

    #Por si el ID del modulo no esta
    module = Module.query.get(module_id)
    if not module:
        error_msg = 'El ID del módulo introducido no es correcto.'
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders, error=error_msg)

    # Validar datos (puedes añadir más validaciones según lo necesites)
    if not module_id or not content:
        error_msg = 'Todos los campos son obligatorios.'
        return  render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders, error=error_msg)

    image = request.files.get('image')

    if image and image.filename:  # Verifica que el archivo tiene un nombre
        # Asegúrate de que el archivo es una imagen
        if not allowed_file(image.filename):
            error_msg = 'Tipo de archivo no permitido. Asegúrate de subir una imagen.'
            return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders, error=error_msg)

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

    theory = Theory.query.all()
    requirements = Requirement.query.all()

    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders)



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

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()


    return  render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders)


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

    db.session.commit()

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()

    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, requirements=requirements, teachers=teachers, theory=theory, global_orders=global_orders)

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

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()


    return  render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders)


@admin_blueprint.route('/admin/update_theory/<int:theory_id>', methods=['POST'])
@login_required
def update_theory(theory_id):
    # Obtener todas las teorías, ejercicios y profesores para el template
    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory_all = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()


    # Obtener la teoría específica
    theory = Theory.query.get(theory_id)
    if not theory:
        error_msg = 'Teoría no encontrada.'
        return render_template('admin_dashboard.html', modules=modules, requirements=requirements, exercises=exercises, teachers=teachers, theory=theory_all, global_orders=global_orders, error=error_msg)

    # Recopilar datos desde el formulario
    content = request.form.get(f'content_{theory_id}')

    # Validar datos
    if not content:
        error_msg = 'El contenido es obligatorio.'
        return render_template('admin_dashboard.html', modules=modules, requirements=requirements, exercises=exercises, teachers=teachers, theory=theory_all, global_orders=global_orders, error=error_msg)

    # Actualizar y guardar los cambios en la base de datos
    theory.content = content
    db.session.commit()

    return render_template('admin_dashboard.html', modules=modules, requirements=requirements, exercises=exercises, teachers=teachers, theory=theory_all, global_orders=global_orders,)


# ------------------- DELETE -------------------



@admin_blueprint.route('/admin/delete_module', methods=['POST'])
@login_required
def delete_module():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()

    module_id = request.form.get('module_id')
    if module_id:
        # Obtiene el módulo por ID
        module_to_delete = Module.query.get(module_id)
        
        # Si el módulo existe, lo elimina
        if module_to_delete:
            db.session.delete(module_to_delete)
            db.session.commit()
        else:
            error_msg = 'Módulo no encontrado'
            return  render_template('admin_dashboard.html', modules=modules, requirements=requirements, exercises=exercises, teachers=teachers, theory=theory, global_orders=global_orders, error=error_msg)

    else:
        error_msg = 'Error al eliminar el módulo'
        return  render_template('admin_dashboard.html', modules=modules, requirements=requirements, exercises=exercises, teachers=teachers, theory=theory, global_orders=global_orders, error=error_msg)

    return  render_template('admin_dashboard.html', modules=modules, exercises=exercises, requirements=requirements, teachers=teachers, theory=theory, global_orders=global_orders,)


@admin_blueprint.route('/admin/delete_exercise', methods=['POST'])
@login_required
def delete_exercise():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    exercise_id = request.form.get('exercise_id')

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()

    if exercise_id:
        # Obtiene el ejercicio por ID
        exercise_to_delete = Exercises.query.get(exercise_id)
        
        # Si el ejercicio existe, lo elimina
        if exercise_to_delete:
            db.session.delete(exercise_to_delete)
            db.session.commit()
        else:
            error_msg = 'Ejercicio no encontrado'
            return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders, error=error_msg)
    else:
        error_msg = 'Error al eliminar el ejercicio'
        return  render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders, error=error_msg)

    exercises = Exercises.query.all()

    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders,)


@admin_blueprint.route('/admin/delete_teacher', methods=['POST'])
@login_required
def delete_teacher():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    # Comprobar si el usuario es un administrador
    if current_user.type_user != 'T': 
        flash('No tienes permisos para realizar esta acción.', 'error')
        return redirect(url_for('student.principal'))

    teacher_id = request.form.get('teacher_id')
    teacher = Users.query.get(teacher_id)

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()

    if not teacher:
        error_msg = 'Profesor no encontrado'
        return  render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory, global_orders=global_orders, error=error_msg)

    db.session.delete(teacher)
    db.session.commit()

    teachers = Users.query.filter_by(type_user="X").all()

    return  render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, global_orders=global_orders, theory=theory)


@admin_blueprint.route('/admin/delete_theory', methods=['POST'])
@login_required
def delete_theory():
    theory_id = request.form.get('exercise_id')  # Obtener el ID de la teoría desde el formulario

    # Intentar obtener la teoría usando el ID
    theory = Theory.query.get(theory_id)

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    all_theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()

    if not theory:
        error_msg = 'Teoría no encontrada.'

        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=all_theory, global_orders=global_orders, error=error_msg)

    # Eliminar la teoría y guardar los cambios en la base de datos
    db.session.delete(theory)
    db.session.commit()

    # Recargar la página con las teorías actualizadas
    all_theory = Theory.query.all()

    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=all_theory, global_orders=global_orders,)

@admin_blueprint.route('/admin/add_requirement', methods=['POST'])
@login_required
def add_requirement():
    # Recopilar datos desde el formulario
    requirement_name = request.form.get('requirement_name')

    # Intentar obtener la teoría usando el ID
    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    all_theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()

    # Validar datos
    if not requirement_name:
        flash('El nombre del requisito es obligatorio.', 'error')
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, theory=all_theory, requirements=requirements, global_orders=global_orders,)

    # Verificar si el requisito ya existe
    existing_requirement = Requirement.query.filter_by(name=requirement_name).first()
    if existing_requirement:
        flash('El requisito ya existe.', 'error')
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, theory=all_theory, requirements=requirements, global_orders=global_orders,)

    # Crear y guardar el nuevo requisito en la base de datos
    new_requirement = Requirement(name=requirement_name)
    db.session.add(new_requirement)
    db.session.commit()

    requirements = Requirement.query.all()

    flash('Requisito añadido exitosamente.', 'success')
    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=all_theory, global_orders=global_orders,)


@admin_blueprint.route('/admin/delete_requirement', methods=['POST'])
@login_required
def delete_requirement():
    # Recopilar ID del requisito desde el formulario
    requirement_id = request.form.get('requirement_id')

    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    all_theory = Theory.query.all()
    global_orders = GlobalOrder.query.order_by(GlobalOrder.global_order).all()
    requirements = Requirement.query.all()

    # Buscar el requisito en la base de datos
    requirement_to_delete = Requirement.query.get(requirement_id)
    
    if not requirement_to_delete:
        flash('Requisito no encontrado.', 'error')
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=all_theory, global_orders=global_orders)

    # Eliminar el requisito de la base de datos
    db.session.delete(requirement_to_delete)
    db.session.commit()

    requirements = Requirement.query.all()

    flash('Requisito eliminado exitosamente.', 'success')
    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=all_theory, global_orders=global_orders)


@admin_blueprint.route('/admin/update_global_order', methods=['POST'])
@login_required
def update_global_order():
    # Obtener todas las teorías, ejercicios y profesores para el template
    modules = Module.query.all()
    exercises = Exercises.query.all()
    teachers = Users.query.filter_by(type_user="X").all()
    theory_all = Theory.query.all()
    requirements = Requirement.query.all()

    # Recopilar datos desde el formulario
    content_type = request.form.get('content_type')
    content_id = int(request.form.get('content_id'))
    new_order = int(request.form.get('global_order'))

    # Verificar que el ID del contenido proporcionado exista
    if content_type == "Exercises":
        content_exists = Exercises.query.get(content_id)
    elif content_type == "Theory":
        content_exists = Theory.query.get(content_id)
    else:
        error_msg = 'Tipo de contenido no válido.'
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory_all, error=error_msg, global_orders=global_orders_updated)

    if not content_exists:
        error_msg = 'El ID para el tipo seleccionado no existe.'
        return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory_all, error=error_msg, global_orders=global_orders_updated)

    # Consulta el registro que actualmente tiene el global_order que deseas
    existing_order = GlobalOrder.query.filter_by(global_order=new_order).first()

    # Si ese registro existe, incrementa su valor y todos los valores subsiguientes
    if existing_order:
        # Obtén todos los registros que tienen un global_order mayor o igual al nuevo, en orden descendente
        subsequent_orders = GlobalOrder.query.filter(GlobalOrder.global_order >= new_order).order_by(GlobalOrder.global_order.desc()).all()
        for order in subsequent_orders:
            order.global_order += 1

    # Luego sigue la lógica para agregar o actualizar el registro
    existing_entry = GlobalOrder.query.filter_by(content_type=content_type, content_id=content_id).first()
    if existing_entry:
        existing_entry.global_order = new_order
    else:
        new_entry = GlobalOrder(content_type=content_type, content_id=content_id, global_order=new_order)
        db.session.add(new_entry)

    db.session.commit()


    # En la función update_global_order
    global_orders_updated = GlobalOrder.query.order_by(GlobalOrder.global_order).all()

    return render_template('admin_dashboard.html', modules=modules, exercises=exercises, teachers=teachers, requirements=requirements, theory=theory_all, global_orders=global_orders_updated)