import subprocess
import threading
import tempfile
import os

def run_java_program(source_code):
    class_name = 'Main'  
    timeout_seconds = 3
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

# Código Java como una cadena
java_code = '''
public class Main {
    public static void main(String[] args) {
        while(true) {} // Bucle infinito para propósitos de prueba
    }
}
'''

# Ejecutar y comprobar si hay un bucle infinito
class_name = 'Main'  # Asegúrate de que esto coincida con el nombre de la clase en el código Java
has_infinite_loop = run_java_program(java_code, 5, class_name)  # 5 segundos de tiempo límite
print("Bucle infinito detectado:" if has_infinite_loop else "No se detectó bucle infinito.")
