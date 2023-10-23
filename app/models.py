from app import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import Enum

class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    birth_date = db.Column(db.Date)
    city = db.Column(db.String(100))
    gender = db.Column(db.String(10))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128))
    type_user = db.Column(db.String(1))
    avatar_id = db.Column(db.Integer)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    current_module_id = db.Column(db.Integer)
    score = db.Column(db.Integer)

    @property
    def is_active(self):
        return True

    def check_password(self, password, bcrypt):
        return bcrypt.check_password_hash(self.password, password)

    def set_avatar(self, avatar_id):
        self.avatar_id = avatar_id
        db.session.commit()

    extra_exercises = db.relationship('ExtraExercises', back_populates='student')

class StudentProgress(db.Model):
    __tablename__ = 'student_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False, server_default='pending', info={'valid_values': ['pending', 'completed', 'in progress']})
    completion_date = db.Column(db.DateTime, nullable=True)
    grade = db.Column(db.Float, nullable=True) # Se podría forzar a un valor entre 0 y 10.
    time_spent = db.Column(db.Integer, default=0)  # Tiempo en segundos
    start_date = db.Column(db.DateTime, nullable=True)
    solution_code = db.Column(db.Text, nullable=True)
    comments = db.Column(db.Text, nullable=True)

    # Relationships 
    student = db.relationship('Users', backref='progresses', lazy=True) # Clase Usuario ya definida
    exercise = db.relationship('Exercises', backref='student_progresses', lazy=True) # Clase Ejercicios ya definida


class Question(db.Model):

    __tablename__ = 'questions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    parent_question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=True)
    question_text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text)
    asked_date = db.Column(db.DateTime, default=datetime.utcnow)
    answered_date = db.Column(db.DateTime)
    attachment_name = db.Column(db.String(255), nullable=True)

    # Esta relación permite que cuando cargues una pregunta, automáticamente puedas cargar 
    # todas las preguntas relacionadas (preguntas de seguimiento) si las hay.
    follow_ups = db.relationship('Question', backref=db.backref('parent', remote_side=[id]), primaryjoin=(id == parent_question_id))
    student = db.relationship('Users', backref='questions', lazy=True)


class StudentModules(db.Model):
    __tablename__ = 'student_modules'


    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    module_id = db.Column(db.Integer, nullable=False)
    current_exercise_id = db.Column(db.Integer, nullable=True)
    completed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<StudentModule {self.id}>'


class StudentActivity(db.Model):
    __tablename__ = 'studentactivity'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content_id = db.Column(db.Integer, nullable=False)  # Añadido content_id sin ForeignKey
    done = db.Column(db.Boolean, default=False)
    content_type = db.Column(Enum('Theory', 'Exercise', name='content_types'), nullable=False)
    skipped = db.Column(db.Boolean, default=False)
    
    # Relación con el estudiante
    student = db.relationship('Users', backref='activities', lazy=True)

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship('Users', backref='notifications', lazy=True)


class ExtraExercises(db.Model):
    __tablename__ = 'extraexercises'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    assigned_date = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    completed_date = db.Column(db.DateTime)
    status = db.Column(db.String(255), nullable=False, default='Assigned')
    
    student = db.relationship('Users', back_populates='extra_exercises')
    exercise = db.relationship('Exercises', back_populates='assigned_exercises')


class Requirement(db.Model):
    __tablename__ = 'requisitos'

    id_requisito = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)

    theories = db.relationship(
        'Theory',
        secondary='theoryrequirements',
        back_populates='requirements'
    )
    exercises = db.relationship(
        'Exercises',
        secondary='exerciserequirements',
        back_populates='requirements'
    )

class TheoryRequirement(db.Model):
    __tablename__ = 'theoryrequirements'

    id_theory = db.Column(db.Integer, db.ForeignKey('theory.id'), primary_key=True)
    id_requirement = db.Column(db.Integer, db.ForeignKey('requisitos.id_requisito'), primary_key=True)

    requirement = db.relationship('Requirement', overlaps="theories")
    theory = db.relationship('Theory', overlaps="requirements")

class Theory(db.Model):
    __tablename__ = 'theory'

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String, nullable=True)

    module = db.relationship('Module', backref='theories', lazy=True)

    requirements = db.relationship(
        'Requirement',
        secondary='theoryrequirements',
        back_populates='theories',
        overlaps="theoryrequirements"
    )

class ExerciseRequirement(db.Model):
    __tablename__ = 'exerciserequirements'

    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), primary_key=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey('requisitos.id_requisito'), primary_key=True)

    requirement = db.relationship('Requirement', overlaps="exercises")
    exercise = db.relationship('Exercises', overlaps="requirements")

class Exercises(db.Model):    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    solution = db.Column(db.Text, nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    test_verification = db.Column(db.JSON)
    language = db.Column(db.Enum('LOGO', 'PYTHON', 'C++', 'JAVA', 'WEB'))
    requires_manual_review = db.Column(db.Boolean, default=False)
    is_key_exercise = db.Column(db.Boolean, default=False)

    requirements = db.relationship(
        'Requirement',
        secondary='exerciserequirements',
        back_populates='exercises',
        overlaps="exerciserequirements"
    )

    assigned_exercises = db.relationship('ExtraExercises', back_populates='exercise')


class Module(db.Model):
    __tablename__ = 'modules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    exercises = db.relationship('Exercises', backref='module', lazy=True) # Clase Ejercicios ya definida

class ModuleRequirementOrder(db.Model):
    __tablename__ = 'module_requirements_order'

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, nullable=False)
    requirement_id = db.Column(db.Integer, db.ForeignKey('requisitos.id_requisito'), nullable=False)
    order_position = db.Column(db.Integer, nullable=False)

    requirement = db.relationship("Requirement", backref="module_orders")

class UserRequirementsCompleted(db.Model):
    __tablename__ = 'userrequirementscompleted'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    requirement_id = db.Column(db.Integer, db.ForeignKey('requisitos.id_requisito'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    completion_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    # Si deseas relaciones para acceder a la información relacionada, puedes agregarlas así:
    user = db.relationship('Users', backref=db.backref('completed_requirements', lazy=True))
    requirement = db.relationship('Requirement', backref=db.backref('completed_users', lazy=True))
    module = db.relationship('Module', backref=db.backref('completed_users', lazy=True))