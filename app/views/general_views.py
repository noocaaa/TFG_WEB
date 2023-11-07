from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required

general_blueprint = Blueprint('general', __name__)

@general_blueprint.route('/logo_guide')
@login_required
def logo_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('logo_guide.html', user=current_user)

@general_blueprint.route('/cpp_guide')
@login_required
def cpp_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    return render_template('cpp_guide.html', user=current_user)

@general_blueprint.route('/python_guide')
@login_required
def python_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('python_guide.html', user=current_user)

@general_blueprint.route('/java_guide')
@login_required
def java_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    return render_template('java_guide.html', user=current_user)

@general_blueprint.route('/web_guide')
@login_required
def web_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    user=current_user

    return render_template('web_guide.html')

@general_blueprint.route('/web_guide/html')
@login_required
def html_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('html_guide.html', user=current_user)

@general_blueprint.route('/web_guide/css')
@login_required
def css_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('css_guide.html', user=current_user)

@general_blueprint.route('/web_guide/javascript')
@login_required
def javascript_guide():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))
    
    return render_template('javascript_guide.html', user=current_user)

@general_blueprint.route('/biblioteca')
@login_required
def biblioteca():
    # Comprobar si el usuario está loggeado
    if not current_user.is_authenticated:  
        return redirect(url_for('control.login'))

    return render_template('biblioteca.html', user=current_user)    
