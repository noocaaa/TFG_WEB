from flask import Blueprint, redirect, url_for, flash, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models import Exercises, StudentProgress, StudentActivity, Theory

from sqlalchemy import func

from datetime import datetime

import os, subprocess, json, time, re

exercise_blueprint = Blueprint('exercise', __name__)

def extract_classname(source_code):
    match = re.search(r'\bclass\s+(\w+)', source_code)
    if match:
        return match.group(1)
    return None

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
        if all(len(ui) == 1 for ui in user_inputs):
            input_data = '"' + ''.join(user_inputs) + '"'
        else:
            input_data = '\n'.join(['"' + ui + '"' for ui in user_inputs])

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


@exercise_blueprint.route('/compile', methods=['POST'])
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

@exercise_blueprint.route('/mark_theory_as_read/<int:content_id>', methods=['POST'])
@login_required
def mark_theory_as_read(content_id):
    student_id = current_user.id
    
    # Crear un nuevo registro en studentactivity
    activity = StudentActivity(
        student_id=student_id,
        content_id=content_id,
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

@exercise_blueprint.route('/time_out', methods=['POST'])
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

@exercise_blueprint.route('/correct_exercise', methods=['POST'])
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
    
    exercise = Exercises.query.get(content_id)
    if not exercise:
        return jsonify({"status": "error", "message": "El ejercicio no existe."})

    time_spent = (end_time - start_time).seconds  

    user_inputs = request.form.getlist('user_inputs[]')

    try:
        once_decoded = json.loads(exercise.test_verification)
        test_verification = json.loads(once_decoded)
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid test_verification format"})
    
    if language != "html": 

        if list(test_verification.keys()) == ["A"] and test_verification["A"] == "B":
            result = some_compile_function(source_code, language, user_inputs)
            is_correct = (result.strip() == str(exercise.solution).strip())
        else:
            first_key = list(test_verification.keys())[0]
            result = some_compile_function(source_code, language, first_key)
            is_correct = (str(test_verification[first_key]).strip() == result.strip())

        status = "completed" if is_correct else "failed"

    else:        
        status = "under_review"


    #Borramos la entrada de in progress, para que el proximo ejercicio se pueda almacenar bien
    in_progress_entry = StudentProgress.query.filter_by(student_id=current_user.id, exercise_id=content_id, status='in progress').first()
    if in_progress_entry:
        db.session.delete(in_progress_entry)

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

    student_activity = StudentActivity.query.filter_by(student_id=current_user.id, content_id=content_id).first()
    if not student_activity:
        new_activity = StudentActivity(student_id=current_user.id, content_id=content_id, done=True, content_type="Exercise")
        db.session.add(new_activity)
    else:
        student_activity.done = True
    
    db.session.commit()

    # Verificar si todos los ejercicios clave han sido completados correctamente por el estudiante
    module_id = exercise.module_id
    key_exercises = Exercises.query.filter_by(module_id=module_id, is_key_exercise=True).all()

    module_completed = True
    for key_exercise in key_exercises:
        student_progress = StudentProgress.query.filter_by(student_id=current_user.id, exercise_id=key_exercise.id, status='completed').first()
        if not student_progress:
            module_completed = False
            break


    response_data = {"status": status, "module_completed": module_completed}

    return jsonify(response_data)