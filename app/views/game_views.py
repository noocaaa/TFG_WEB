from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required

from app.models import Payment, ModuleRequirementOrder, UserRequirementsCompleted, Module, Users, Game

from app import db

from datetime import datetime

game_blueprint = Blueprint('game', __name__)

def has_paid(user_id, game_id):
    # Verificar si existe un pago para el juego y el usuario
    payment = Payment.query.filter_by(user_id=user_id, game_id=game_id).first()
    return payment is not None

def has_completed_requirements(user_id, module_id):
    # Obtener los requisitos del módulo
    module_requirements = ModuleRequirementOrder.query.filter_by(module_id=module_id).count()
    unique_requirements_count = UserRequirementsCompleted.query.with_entities(UserRequirementsCompleted.requirement_id).filter_by(user_id=user_id, module_id=module_id).distinct().count()

    if (module_requirements != unique_requirements_count):
        return False
    else:
        return True

def get_first_module_id():
    first_module = Module.query.order_by(Module.id).first()
    return first_module.id if first_module else None

def get_module_by_order(order):
    # Asegúrate de que la orden sea un número y que no sea menor que 1
    if not isinstance(order, int) or order < 1:
        raise ValueError("Order must be an integer greater than 0")

    # Restar 1 porque la cuenta empieza en 0
    module = Module.query.order_by(Module.id).offset(order - 1).first()
    return module.id if module else None

def get_game_price(game_id):
    # Buscar el juego por ID y obtener su precio
    game = Game.query.get(game_id)

    if game:
        return game.price
    else:
        return None  # O manejar como se prefiera si el juego no existe

def get_student_score(user_id):
    # Buscar al usuario por ID y obtener su puntuación
    user = Users.query.get(user_id)
    if user:
        return user.score
    else:
        return None  # O manejar como se prefiera si el usuario no existe


@game_blueprint.route('/procesar_pago', methods=['POST'])
@login_required
def procesar_pago():
    # Asegúrate de tener un manejo de errores adecuado aquí
    data = request.get_json()

    game_price =  data.get('game_price')
    student_score = data.get('student_score')
    user_id = current_user.id

    game_id = Game.query.filter_by(price=game_price).first().id

    print(game_id)

    if student_score is not None and game_price is not None and student_score >= game_price:
        # Procesar el pago
        # Deduce el precio del juego de la puntuación del estudiante
        user = Users.query.get(user_id)
        user.score -= game_price

        payment = Payment(
            user_id=user_id,
            game_id=game_id,
            amount=game_price,
            payment_date=datetime.utcnow()
        )

        db.session.add(payment)

        db.session.commit()


        # Asumiendo que tienes una función que te devuelve la URL del juego
        game_url = url_for('game.games')

        return jsonify({'payment_successful': True, 'redirect_url': game_url})

    return jsonify({'payment_successful': False})


@game_blueprint.route('/juegos')
@login_required
def games():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    requirement_completed=True

    return render_template('juegos.html', user=current_user, student_score=0, game_price=0, requirements_completed=requirement_completed, show_payment_modal=False, show_not_money_modal=False)

@game_blueprint.route('/juegos/ajedrez')
@login_required
def chess():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    module_id_for_chess = get_first_module_id()
    game_id = Game.query.filter_by(name='Ajedrez').first().id

    requirement_completed = has_completed_requirements(current_user.id, module_id_for_chess)

    if requirement_completed:
        # Aquí puedes verificar si el usuario ya ha pagado
        if has_paid(current_user.id, game_id):
            # Renderizar la plantilla directamente si ya pagó
            return render_template('chess.html', user=current_user, requirements_completed=requirement_completed)
        else:

            # Obtén el precio del juego de la base de datos
            game_price = int(get_game_price(game_id))

            # Obtén el score del estudiante
            student_score = get_student_score(current_user.id)

            # Determina si se muestra el modal de pago
            show_payment_modal = student_score >= game_price

            if not show_payment_modal:
                show_not_money_modal = True
            else:
                show_not_money_modal = False
                
            # Pasa la información al frontend
            return render_template('juegos.html', user=current_user, requirements_completed=requirement_completed, game_price=game_price, show_payment_modal=show_payment_modal, student_score=student_score, show_not_money_modal=show_not_money_modal)
        
    return render_template('juegos.html', user=current_user, student_score=0, game_price=0, requirements_completed=requirement_completed, show_payment_modal=False, show_not_money_modal=False)


@game_blueprint.route('/juegos/2048')
@login_required
def g_2048():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    module_id_for_chess = get_first_module_id()
    game_id = Game.query.filter_by(name='2048').first().id

    requirement_completed = has_completed_requirements(current_user.id, module_id_for_chess)

    if requirement_completed:
        # Aquí puedes verificar si el usuario ya ha pagado
        if has_paid(current_user.id, game_id):
            # Renderizar la plantilla directamente si ya pagó
            return render_template('2048.html', user=current_user, requirements_completed=requirement_completed)
        else:

            # Obtén el precio del juego de la base de datos
            game_price = int(get_game_price(game_id))

            # Obtén el score del estudiante
            student_score = get_student_score(current_user.id)

            # Determina si se muestra el modal de pago
            show_payment_modal = student_score >= game_price

            if not show_payment_modal:
                show_not_money_modal = True
            else:
                show_not_money_modal = False
                
            # Pasa la información al frontend
            return render_template('juegos.html', user=current_user, requirements_completed=requirement_completed, game_price=game_price, show_payment_modal=show_payment_modal, student_score=student_score, show_not_money_modal=show_not_money_modal)
        
    return render_template('juegos.html', user=current_user, student_score=0, game_price=0, requirements_completed=requirement_completed, show_payment_modal=False, show_not_money_modal=False)


@game_blueprint.route('/juegos/hextris')
@login_required
def hextris():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    module_id_for_chess = get_first_module_id()
    game_id = Game.query.filter_by(name='Hextris').first().id

    requirement_completed = has_completed_requirements(current_user.id, module_id_for_chess)

    if requirement_completed:
        # Aquí puedes verificar si el usuario ya ha pagado
        if has_paid(current_user.id, game_id):
            # Renderizar la plantilla directamente si ya pagó
            return render_template('hextris.html', user=current_user, requirements_completed=requirement_completed)
        else:

            # Obtén el precio del juego de la base de datos
            game_price = int(get_game_price(game_id))

            # Obtén el score del estudiante
            student_score = get_student_score(current_user.id)

            # Determina si se muestra el modal de pago
            show_payment_modal = student_score >= game_price

            if not show_payment_modal:
                show_not_money_modal = True
            else:
                show_not_money_modal = False
                
            # Pasa la información al frontend
            return render_template('juegos.html', user=current_user, requirements_completed=requirement_completed, game_price=game_price, show_payment_modal=show_payment_modal, student_score=student_score, show_not_money_modal=show_not_money_modal)
        
    return render_template('juegos.html', user=current_user, student_score=0, game_price=0, requirements_completed=requirement_completed, show_payment_modal=False, show_not_money_modal=False)


@game_blueprint.route('/juegos/minesweeper')
@login_required
def minesweeper():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    module_id_for_chess = get_first_module_id()
    game_id = Game.query.filter_by(name='Buscaminas').first().id

    requirement_completed = has_completed_requirements(current_user.id, module_id_for_chess)

    if requirement_completed:
        # Aquí puedes verificar si el usuario ya ha pagado
        if has_paid(current_user.id, game_id):
            # Renderizar la plantilla directamente si ya pagó
            return render_template('minesweeper.html', user=current_user, requirements_completed=requirement_completed)
        else:

            # Obtén el precio del juego de la base de datos
            game_price = int(get_game_price(game_id))

            # Obtén el score del estudiante
            student_score = get_student_score(current_user.id)

            # Determina si se muestra el modal de pago
            show_payment_modal = student_score >= game_price

            if not show_payment_modal:
                show_not_money_modal = True
            else:
                show_not_money_modal = False
                
            # Pasa la información al frontend
            return render_template('juegos.html', user=current_user, requirements_completed=requirement_completed, game_price=game_price, show_payment_modal=show_payment_modal, student_score=student_score, show_not_money_modal=show_not_money_modal)
        
    return render_template('juegos.html', user=current_user, student_score=0, game_price=0, requirements_completed=requirement_completed, show_payment_modal=False, show_not_money_modal=False)
