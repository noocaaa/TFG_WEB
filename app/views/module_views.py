from flask import Blueprint

from app.models import StudentProgress, StudentActivity

from datetime import datetime, timedelta


module_blueprint = Blueprint('module', __name__)

# Verifica si el estudiante ha fallado repetidamente un ejercicio.
def has_failed_recently(student_id, threshold=3):
    recent_failures = (
        StudentProgress.query
        .filter_by(student_id=student_id, status="failed")
        .order_by(StudentProgress.completion_date.desc())
        .limit(threshold)
        .all()
    )
    return len(recent_failures) == threshold

# Comprueba si el estudiante ha estado inactivo durante cierto número de días.
def is_inactive(student_id, days=7):
    last_activity = (
        StudentActivity.query
        .filter_by(student_id=student_id)
        .order_by(StudentActivity.timestamp.desc())
        .first()
    )
    if not last_activity:
        return False
    return datetime.now() - last_activity.timestamp > timedelta(days=days)


