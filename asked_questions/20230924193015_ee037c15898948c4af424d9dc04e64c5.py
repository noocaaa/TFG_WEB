from app import db
from flask_login import UserMixin
from datetime import datetime

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

    @property
    def is_active(self):
        return True

    def check_password(self, password, bcrypt):
        return bcrypt.check_password_hash(self.password, password)

    def set_avatar(self, avatar_id):
        self.avatar_id = avatar_id
        db.session.commit()

class Exercises(db.Model):    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    solution = db.Column(db.Text, nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    test_verification = db.Column(db.JSON)

class Module(db.Model):
    __tablename__ = 'modules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    exercises = db.relationship('Exercises', backref='module', lazy=True) # Clase Ejercicios ya definida

class StudentProgress(db.Model):
    __tablename__ = 'student_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False, server_default='pending', info={'valid_values': ['pending', 'completed', 'in progress']})
    completion_date = db.Column(db.DateTime, nullable=True)
    grade = db.Column(db.Float, nullable=True) # Se podría forzar a un valor entre 0 y 10.
    time_spent = db.Column(db.Integer, default=0)  # Yiempo en segundos
    start_date = db.Column(db.DateTime, nullable=True)

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
