from flask import Blueprint, redirect, url_for, flash, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models import Exercises, StudentProgress, StudentActivity, Theory, Requirement, UserRequirementsCompleted, ModuleRequirementOrder, ExtraExercises

from sqlalchemy import func
from datetime import datetime

from radon.complexity import cc_visit
from javalang.tree import *

import pylint.epylint as lint
import os, subprocess, json, time, re, tempfile, ast, random, lizard, threading, javalang, clang.cindex

libclang_path = "/usr/lib/llvm-10/lib"
os.environ['LIBCLANG_LIBRARY_PATH'] = libclang_path

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


# --- FUNCIÓN Y FUNCIONES AUXILIARES PARA CORRECT_EXERCISE

def gather_data():
    source_code = request.form.get('source_code')
    language = request.form.get('language')
    content_id = request.form.get('exercise_id')
    start_time = datetime.fromtimestamp(int(request.form.get('start_time')) / 1000.0)
    end_time = datetime.fromtimestamp(int(request.form.get('end_time')) / 1000.0)
    user_inputs = request.form.getlist('user_inputs[]')
    return source_code, language, content_id, start_time, end_time, user_inputs

def compile_and_correct(content_id, source_code, language, user_inputs):
    exercise = Exercises.query.get(content_id)
    
    if not exercise:
        return "error", False

    try:
        once_decoded = json.loads(exercise.test_verification)
        test_verification = json.loads(once_decoded)
    except ValueError:
        return "error", False

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

    return status

def update_student_progress_and_activity(content_id, source_code, start_time, end_time, time_spent, status):
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

def check_module_completion(exercise):
    module_id = exercise.module_id
    key_exercises = Exercises.query.filter_by(module_id=module_id, is_key_exercise=True).all()
    for key_exercise in key_exercises:
        student_progress = StudentProgress.query.filter_by(student_id=current_user.id, exercise_id=key_exercise.id, status='completed').first()
        if not student_progress:
            return False
    return True

# ---- ESTILO DEL CÓDIGO ----

def evaluate_code_style(source_code):
    # Crear un archivo temporal
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp:
        temp_name = temp.name
        temp.write(source_code.encode())

    try:
        (pylint_stdout, _) = lint.py_run(f"{temp_name} --disable=missing-final-newline,missing-module-docstring", return_std=True)
        feedback = pylint_stdout.getvalue()
    finally:
        os.remove(temp_name)

    return feedback

def evaluate_code_style_JAVA(source_code):
    with tempfile.NamedTemporaryFile(suffix=".java", delete=False) as temp:
        temp_name = temp.name
        temp.write(source_code.encode())
        temp.flush()

    try:
        result = subprocess.run(
            ["checkstyle", "-c", "./app/static/google_checks.xml", temp_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        feedback = result.stdout
        error_output = result.stderr
        exit_code = result.returncode
    except subprocess.CalledProcessError as e:
        feedback = e.output
    finally:
        os.remove(temp_name)

    return feedback, error_output, exit_code


def evaluate_code_style_CPP(source_code):
    # Crear un archivo temporal con la extensión adecuada para C++
    with tempfile.NamedTemporaryFile(suffix=".cpp", delete=False) as temp:
        temp_name = temp.name
        temp.write(source_code.encode())
        temp.flush()  # Asegúrate de que se escribe todo el contenido al archivo

    try:
        # Ejecutar cpplint en el archivo temporal, ignorando los errores de copyright
        result = subprocess.run(["cpplint", "--filter=-legal/copyright", temp_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        feedback = result.stdout.decode() + result.stderr.decode()
    finally:
        # Borrar el archivo temporal
        os.remove(temp_name)

    return feedback

def count_tmp_lines(feedback):
    # Dividir el feedback por líneas
    lines = feedback.split('\n')
    # Contar las líneas de errores que contienen '/tmp' y excluir líneas que empiecen con "Done processing"
    count = sum('/tmp' in line and not line.startswith('Done processing') for line in lines)
    return count

# ---- COMPLEJIDAD CICLOMATICA ----

def calculate_cyclomatic_complexity(source_code):
    blocks = cc_visit(source_code)
    total_complexity = sum(block.complexity for block in blocks)
    return total_complexity

def calculate_cyclomatic_complexity_JAVA(source_code):
    # Analiza el código fuente con Lizard
    analysis_result = lizard.analyze_file.analyze_source_code('temp.java', source_code)
    # Suma la complejidad ciclomática de todas las funciones
    total_complexity = sum(func.cyclomatic_complexity for func in analysis_result.function_list)
    return total_complexity

def calculate_cyclomatic_complexity_CPP(source_code):
    # Analiza el código fuente con Lizard
    analysis_result = lizard.analyze_file.analyze_source_code('temp.cpp', source_code)
    # Suma la complejidad ciclomática de todas las funciones
    total_complexity = sum(func.cyclomatic_complexity for func in analysis_result.function_list)
    return total_complexity

# ---- BUCLES INFINITOS ----

def run_program_CPP(source_code, timeout_seconds = 3):
    with tempfile.NamedTemporaryFile(suffix='.cpp', mode='w+', delete=False) as src_file:
        src_file.write(source_code)
        src_file.flush()  # Asegurarse de que se escribe en el disco
        executable_name = src_file.name + '.out'

    # Compilar el código fuente
    compile_process = subprocess.run(['g++', src_file.name, '-o', executable_name],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Verificar si hay errores de compilación
    if compile_process.returncode != 0:
        print("Error en la compilación:")
        print(compile_process.stderr.decode())
        return False

    try:
        # Ejecutar el programa compilado
        process = subprocess.Popen([executable_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Iniciar un temporizador y esperar que termine el proceso
        process_thread = threading.Thread(target=process.communicate)
        process_thread.start()
        process_thread.join(timeout_seconds)
        if process_thread.is_alive():
            # Terminar el proceso si sigue activo (bucle infinito potencial)
            process.terminate()
            process_thread.join()
            print(f"El proceso ha sido terminado después de {timeout_seconds} segundos, posible bucle infinito.")
            return True
        else:
            print("El proceso ha terminado correctamente.")
            return False
    finally:
        # Eliminar los archivos temporales
        subprocess.run(['rm', src_file.name])
        subprocess.run(['rm', executable_name])

def run_program(source_code, timeout_seconds = 3):
    # Añadir la declaración de codificación utf-8 si tu código fuente contiene caracteres no ASCII
    
    with tempfile.NamedTemporaryFile(suffix='.py', mode='w+', delete=False) as src_file:
        src_file.write(source_code)
        src_file.flush()
        src_file_name = src_file.name

    # Definir una variable para almacenar el resultado del hilo
    thread_result = {"timeout": False}

    def target():
        try:
            subprocess.run(['python3', src_file_name], timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            thread_result["timeout"] = True
            print(f"El proceso ha sido terminado después de {timeout_seconds} segundos, posible bucle infinito.")

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout_seconds)

    # Limpiar
    subprocess.run(['rm', src_file_name])

    if thread.is_alive():
        # Si el hilo está vivo después del tiempo límite, se asume que hay un bucle infinito.
        thread.join()
        return True
    elif thread_result["timeout"]:
        # Si el hilo no está vivo pero se ha alcanzado el tiempo límite, también es un bucle infinito.
        return True
    else:
        # Si el hilo ha terminado antes del tiempo límite, no hay bucle infinito.
        return False

def run_program_JAVA(source_code, timeout_seconds = 3, class_name = 'Main'):
    # Creamos un directorio temporal para almacenar el archivo .java y el .class
    with tempfile.TemporaryDirectory() as temp_dir:
        src_file_path = os.path.join(temp_dir, f"{class_name}.java")
        with open(src_file_path, 'w') as src_file:
            src_file.write(source_code)

        # Compilar el código fuente
        compile_process = subprocess.run(['javac', src_file_path],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=temp_dir)

        # Verificar si hay errores de compilación
        if compile_process.returncode != 0:
            print("Error en la compilación:")
            print(compile_process.stderr.decode())
            return False

        try:
            # Ejecutar el programa compilado
            cmd = ['java', '-cp', temp_dir, class_name]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Iniciar un temporizador y esperar que termine el proceso
            process_thread = threading.Thread(target=process.communicate)
            process_thread.start()
            process_thread.join(timeout_seconds)
            if process_thread.is_alive():
                # Terminar el proceso si sigue activo (bucle infinito potencial)
                process.terminate()
                process_thread.join()
                print(f"El proceso ha sido terminado después de {timeout_seconds} segundos, posible bucle infinito.")
                return True
            else:
                print("El proceso ha terminado correctamente.")
                return False
        finally:
            # Los archivos temporales se eliminarán automáticamente al salir del bloque with
            pass


# --- PUNTUACION --- 

def calculate_score(style_feedback, complexity, loops_detected):
    # Puntuación inicial
    score = 100
    
    # Deducción por problemas de estilo (por cada problema detectado, se restan 10 puntos)
    style_issues = count_tmp_lines(style_feedback)
    score -= 5 * style_issues
    
    # Deducción por complejidad ciclomática
    if complexity > 10:
        score -= 20

    # Deducción por detección de bucles
    if loops_detected:
        score -= 15

    # Asegurarte de que la puntuación no caiga por debajo de 0
    return max(0, score)

def all_checkings(source_code, language):
    
    if language == 'PYTHON':

        # Evaluamos el estilo del código
        style_feedback = evaluate_code_style(source_code)

        # Calculamos la complejidad ciclomática
        complexity = calculate_cyclomatic_complexity(source_code)

        # Detectamos bucles en el código
        loops_detected = run_program(source_code)

    elif language == 'JAVA':

        style_feedback = evaluate_code_style_JAVA(source_code)

        # Calculamos la complejidad ciclomática
        complexity = calculate_cyclomatic_complexity_JAVA(source_code)

        # Detectamos bucles en el código
        loops_detected = run_program_JAVA(source_code)

    elif language == 'CPP':

        style_feedback = evaluate_code_style_CPP(source_code)

        # Calculamos la complejidad ciclomática
        complexity = calculate_cyclomatic_complexity_CPP(source_code)

        # Detectamos bucles en el código
        loops_detected = run_program_CPP(source_code)

    return style_feedback, complexity, loops_detected

def update_score_user(user, score):
    if user.score is None:
        user.score = 0
    user.score += score
    db.session.commit()

# ---- COMPROBACIÓN DE REQUISITOS ----

class RequirementVisitor(ast.NodeVisitor):
    def __init__(self):
        self.requirements_found = {
            'Intro': False, 
            'Basic-Operators': False,
            'Logical-Operators': False,
            'If-Else': False,
            'Switch': False, 
            'While': False,
            'For': False,
            'Functions-Basics': False,
            'Functions-Advanced': False, 
            'Classes': False,
            'Inheritance': False,
            'Styles': False,
            'Interactivity': False,
            'DOM-Basics': False,
            'DOM-Advanced': False,
            'Lists': False,
            'Dictionaries': False
        }

    def visit_BinOp(self, node):
        # Comprobar operadores básicos
        if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            self.requirements_found['Basic-Operators'] = True
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # Comprobar operadores lógicos
        self.requirements_found['Logical-Operators'] = True
        self.generic_visit(node)

    def visit_If(self, node):
        # Comprobar If-Else
        self.requirements_found['If-Else'] = True
        self.generic_visit(node)

    def visit_While(self, node):
        # Comprobar While
        self.requirements_found['While'] = True
        self.generic_visit(node)

    def visit_For(self, node):
        # Comprobar For
        self.requirements_found['For'] = True
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Comprobar definición básica de funciones
        self.requirements_found['Functions-Basics'] = True
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        # Comprobar clases
        self.requirements_found['Classes'] = True
        # Comprobar herencia
        if node.bases:
            self.requirements_found['Inheritance'] = True
        self.generic_visit(node)

    def visit_List(self, node):
        # Comprobar listas
        self.requirements_found['Lists'] = True
        self.generic_visit(node)

    def visit_Dict(self, node):
        # Comprobar diccionarios
        self.requirements_found['Dictionaries'] = True
        self.generic_visit(node)


class RequirementVisitor_JAVA:

    def __init__(self):
        self.requirements_found = {
            'Intro': False,
            'Basic-Operators': False,
            'Logical-Operators': False,
            'If-Else': False,
            'Switch': False,
            'While': False,
            'For': False,
            'Methods-Basics': False,
            'Methods-Advanced': False,
            'Classes': False,
            'Inheritance': False,
            'Arrays': False
        }

    def visit(self, node):
        if isinstance(node, BinaryOperation):
            self.requirements_found['Basic-Operators'] = True
        elif isinstance(node, IfStatement) or isinstance(node, TernaryExpression):
            self.requirements_found['If-Else'] = True
        elif isinstance(node, WhileStatement):
            self.requirements_found['While'] = True
        elif isinstance(node, ForStatement):
            self.requirements_found['For'] = True
        elif isinstance(node, MethodDeclaration):
            self.requirements_found['Methods-Basics'] = True
            if node.parameters or node.throws or node.type_parameters:
                self.requirements_found['Methods-Advanced'] = True
        elif isinstance(node, ClassDeclaration):
            self.requirements_found['Classes'] = True
            if node.extends or node.implements:
                self.requirements_found['Inheritance'] = True
        elif isinstance(node, ArrayInitializer):
            self.requirements_found['Arrays'] = True

        # Recursivamente visita los hijos del nodo actual si los tiene
        if hasattr(node, 'children'):
            for child in node.children:
                if isinstance(child, (list, set)):
                    for item in child:
                        if isinstance(item, javalang.ast.Node):
                            self.visit(item)
                elif isinstance(child, javalang.ast.Node):
                    self.visit(child)


class RequirementVisitor_CPP:
    def __init__(self):
        self.requirements_found = {
            'Basic-Operators': False,
            'Logical-Operators': False,
            'If-Else': False,
            'Switch': False,
            'While': False,
            'For': False,
            'Functions-Basics': False,
            'Functions-Advanced': False,
            'Classes': False,
            'Inheritance': False,
            'Templates': False,
        }

    def visit(self, node):
        # Esta función necesita ser llamada recursivamente para cada hijo del nodo.
        if node.kind == clang.cindex.CursorKind.BINARY_OPERATOR:
            self.requirements_found['Basic-Operators'] = True
        elif node.kind == clang.cindex.CursorKind.IF_STMT:
            self.requirements_found['If-Else'] = True
        elif node.kind == clang.cindex.CursorKind.WHILE_STMT:
            self.requirements_found['While'] = True
        elif node.kind == clang.cindex.CursorKind.FOR_STMT:
            self.requirements_found['For'] = True
        elif node.kind in [clang.cindex.CursorKind.FUNCTION_DECL, clang.cindex.CursorKind.CXX_METHOD]:
            self.requirements_found['Functions-Basics'] = True
        elif node.kind == clang.cindex.CursorKind.CLASS_DECL:
            self.requirements_found['Classes'] = True
        elif node.kind == clang.cindex.CursorKind.CLASS_TEMPLATE:
            self.requirements_found['Templates'] = True

        for child in node.get_children():
            self.visit(child)


def check_requirements(code, language):
    if language == "PYTHON":
        tree = ast.parse(code)
        visitor = RequirementVisitor()
        visitor.visit(tree)
        return visitor.requirements_found
    elif language == "JAVA":
        tree = javalang.parse.parse(code)
        visitor = RequirementVisitor_JAVA()
        for path, node in tree:
            visitor.visit(node)
        return visitor.requirements_found
    elif language == "CPP":
        index = clang.cindex.Index.create()
        tu = index.parse('tmp.cpp', args=['-std=c++11'],  # Asegúrate de que el estándar de C++ sea el correcto
                        unsaved_files=[('tmp.cpp', code)], options=0)
        visitor = RequirementVisitor_CPP()
        visitor.visit(tu.cursor)
        return visitor.requirements_found

# ---- EJERCICIOS ----

# Obtener los ejercicios recientes completados por un estudiante para un requisito específico
def get_recent_completed_exercises(student_id, recent_num, related_exercises_ids):
    recent_exercises = (
        StudentProgress.query
        .filter(
            StudentProgress.student_id == student_id,
            StudentProgress.exercise_id.in_(related_exercises_ids),
            StudentProgress.status.in_(['completed', 'failed'])
        )
        .order_by(StudentProgress.completion_date.desc())
        .limit(recent_num)
        .all()
    )
    
    return recent_exercises

# Determina el numero de ejercicios extras que añadir al estudiante
def determine_number_of_extra_exercises(student_id, recent_num=4, max_extra_exercises=5, failure_rate_threshold=0.35):
    # 1. Buscar el último requirement completado por el estudiante
    last_completed_requirement = (
        UserRequirementsCompleted.query
        .filter_by(user_id=student_id)
        .order_by(UserRequirementsCompleted.completion_date.desc())
        .first()
    )
    
    if not last_completed_requirement:
        # Si el estudiante aún no ha completado ningún requisito, podemos seleccionar el primer requisito
        # del primer módulo como el "requirement" actual.
        next_requirement = (
            ModuleRequirementOrder.query
            .order_by(ModuleRequirementOrder.module_id, ModuleRequirementOrder.order_position)
            .first()
        )
    else:
        # Si el estudiante ha completado algún requisito, determina el siguiente
        current_position = (
            ModuleRequirementOrder.query
            .filter_by(module_id=last_completed_requirement.module_id, requirement_id=last_completed_requirement.requirement_id)
            .first()
        )
        
        next_requirement = (
            ModuleRequirementOrder.query
            .filter_by(module_id=current_position.module_id)
            .filter(ModuleRequirementOrder.order_position > current_position.order_position)
            .order_by(ModuleRequirementOrder.order_position)
            .first()
        )
    
    # Si no hay un próximo requisito, terminar
    if not next_requirement:
        return 0
    
    requirement_obj = Requirement.query.get(next_requirement.requirement_id)

    if not requirement_obj:
        return 0

    related_exercises_ids = [exercise.id for exercise in requirement_obj.exercises]
    
    recent_exercises = get_recent_completed_exercises(student_id, recent_num, related_exercises_ids)
    
    # Hasta que el estudiante no haya realizado el recent_num no se puede establecer si avanzar o añadir ejercicios
    if len(recent_exercises) < recent_num:
        return 0
    
    failed_exercises = sum(1 for exercise in recent_exercises if exercise.status == "failed")
    failure_rate = failed_exercises / len(recent_exercises)

    # Si la tasa de fallos es demasiado baja, no asignar ejercicios adicionales
    if failure_rate < failure_rate_threshold:
        return 0

    all_times = [e.time_spent for e in recent_exercises]
    min_time = min(all_times)
    max_time = max(all_times)
    
    if min_time == max_time:
        normalized_time_last_exercise = 1
    else:
        time_spent_last_exercise = recent_exercises[0].time_spent

        if time_spent_last_exercise == 0:
            time_spent_last_exercise = min_time
        
        normalized_time_last_exercise = (time_spent_last_exercise - min_time) / (max_time - min_time)
    
    weight_failure_rate = 0.7
    weight_time = 0.3

    normalized_time = abs(0.5 - normalized_time_last_exercise) * 2
    
    weighted_sum = (weight_failure_rate * failure_rate + weight_time * normalized_time)
    
    return max(0, round(weighted_sum * max_extra_exercises))


def assign_extra_exercises(user_id):
    # 1. Determinar cuántos ejercicios extra se necesitan
    num_extra = determine_number_of_extra_exercises(user_id)

    # 2. Identificar ejercicios disponibles como extras
    all_exercises = db.session.query(Exercises).all()

    # 2.1 Excluir ejercicios ya asignados como extras o intentados por el estudiante en la tabla de progreso regular
    assigned_extra_exercise_ids = db.session.query(ExtraExercises.exercise_id)\
                                            .filter(ExtraExercises.student_id == user_id)\
                                            .all()

    student_progress_records = db.session.query(StudentProgress)\
                                         .filter(StudentProgress.student_id == user_id)\
                                         .all()

    attempted_exercise_ids = [record.exercise_id for record in student_progress_records] + [record[0] for record in assigned_extra_exercise_ids]
    failed_exercise_ids = [record.exercise_id for record in student_progress_records if record.status == 'failed']

    not_attempted_exercises = [exercise for exercise in all_exercises if exercise.id not in attempted_exercise_ids]
    failed_exercises = [exercise for exercise in all_exercises if exercise.id in failed_exercise_ids]

    # 3. Asignar ejercicios al estudiante
    for i in range(num_extra):
        if not_attempted_exercises:
            extra_exercise = random.choice(not_attempted_exercises)
            not_attempted_exercises.remove(extra_exercise)
        elif failed_exercises:
            extra_exercise = random.choice(failed_exercises)
            failed_exercises.remove(extra_exercise)
        else:
            break  # No hay más ejercicios para asignar

        # Crear el registro que conecta al estudiante con el ejercicio extra en la tabla ExtraExercises.
        new_record = ExtraExercises(
            student_id=user_id, 
            exercise_id=extra_exercise.id, 
            assigned_date=datetime.utcnow(), 
            status='Assigned'
        )
        db.session.add(new_record)

    db.session.commit()



@exercise_blueprint.route('/correct_exercise', methods=['POST'])
@login_required
def correct_exercise():

    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    # Obtenemos los datos necesarios
    source_code, language, content_id, start_time, end_time, user_inputs = gather_data()

    exercise = Exercises.query.get(content_id)
    
    time_spent = (end_time - start_time).seconds  
    
    # Comprobamos que la solución es correcta
    status = compile_and_correct(content_id, source_code, language, user_inputs)

    if status == 'completed':
        style_feedback, complexity, loops_detected = all_checkings(source_code, language)
        
        student_score = calculate_score(style_feedback, complexity, loops_detected)

        requirements_status = check_requirements(source_code)
        
        met_requirements = sum(1 for _, is_met in requirements_status.items() if is_met)
        
        # Penalización por requisitos no cumplidos
        for req, is_met in requirements_status.items():
            if not is_met:
                student_score -= 10

        # Si no se cumple al menos el 60% de los requisitos, la solución es inválida.
        if met_requirements < 0.6 * len(requirements_status):
            student_score = 0
            status = "failed"
        
        # Obtener la puntuación de la solución de referencia
        if exercise.reference_solution:
            ref_sf, ref_c, ref_l = all_checkings(exercise.reference_solution, language)
            teacher_score = calculate_score(ref_sf, ref_c, ref_l)

            # Ajustar la puntuación del estudiante basado en la comparación con la solución de referencia
            fitness = max(0, 1 - abs(teacher_score - student_score) / 100.0)
            student_score *= fitness
        
        # Asignar ejercicios adicionales si la puntuación del estudiante es baja
        if student_score < 60:
            assign_extra_exercises(current_user.id)

        # Actualizar la puntuación del usuario
        update_score_user(current_user, student_score)

    assign_extra_exercises(current_user.id)

    #Almacenamos la información en la BBDD
    update_student_progress_and_activity(content_id, source_code, start_time, end_time, time_spent, status)

    #Comprobamos si el modulo se ha completado
    module_completed = check_module_completion(exercise)
    
    return jsonify({"status": status, "module_completed": module_completed})