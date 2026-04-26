from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import bcrypt
from models import db, Usuario

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui_cambiala'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Función para hashear contraseña
def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# Función para verificar contraseña
def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

# Crear tablas y usuario admin por defecto
with app.app_context():
    db.create_all()
    # Crear usuario admin si no existe
    admin = Usuario.query.filter_by(usuario='admin').first()
    if not admin:
        admin_password = hash_password('admin123')
        admin = Usuario(
            nombre='Administrador',
            usuario='admin',
            celular='0000000000',
            email='admin@ejemplo.com',
            password_hash=admin_password,
            es_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuario admin creado: usuario='admin', contraseña='admin123'")

# Ruta principal
@app.route('/')
def index():
    return redirect(url_for('login'))

# Endpoint de registro
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        usuario = request.form.get('usuario')
        celular = request.form.get('celular')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Verificar si el usuario o email ya existe
        usuario_existente = Usuario.query.filter_by(usuario=usuario).first()
        email_existente = Usuario.query.filter_by(email=email).first()
        
        if usuario_existente:
            flash('El nombre de usuario ya está en uso', 'error')
            return redirect(url_for('registro'))
        
        if email_existente:
            flash('El correo electrónico ya está registrado', 'error')
            return redirect(url_for('registro'))
        
        # Hashear contraseña
        password_hash = hash_password(password)
        
        # Crear nuevo usuario (por defecto no es admin)
        nuevo_usuario = Usuario(
            nombre=nombre,
            usuario=usuario,
            celular=celular,
            email=email,
            password_hash=password_hash,
            es_admin=False
        )
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        flash('Registro exitoso. Por favor inicia sesión', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html')

# Endpoint de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')
        
        user = Usuario.query.filter_by(usuario=usuario).first()
        
        if user and verify_password(password, user.password_hash):
            login_user(user)
            flash(f'Bienvenido {user.nombre}!', 'success')
            
            # Redirigir según rol
            if user.es_admin:
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('perfil'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')

# Perfil de usuario normal
@app.route('/perfil')
@login_required
def perfil():
    return render_template('perfil.html', usuario=current_user)

# Dashboard de admin (CRUD de usuarios)
@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.es_admin:
        flash('Acceso denegado. Se requieren permisos de administrador', 'error')
        return redirect(url_for('perfil'))
    
    usuarios = Usuario.query.all()
    return render_template('dashboard.html', usuarios=usuarios)

# API Endpoint para crear usuario (desde dashboard)
@app.route('/api/usuarios', methods=['POST'])
@login_required
def crear_usuario_api():
    if not current_user.es_admin:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    data = request.json
    
    # Validar campos
    required_fields = ['nombre', 'usuario', 'celular', 'email', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo {field} requerido'}), 400
    
    # Verificar si existe
    if Usuario.query.filter_by(usuario=data['usuario']).first():
        return jsonify({'error': 'Usuario ya existe'}), 400
    
    if Usuario.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email ya existe'}), 400
    
    # Hashear contraseña
    password_hash = hash_password(data['password'])
    
    nuevo_usuario = Usuario(
        nombre=data['nombre'],
        usuario=data['usuario'],
        celular=data['celular'],
        email=data['email'],
        password_hash=password_hash,
        es_admin=data.get('es_admin', False)
    )
    
    db.session.add(nuevo_usuario)
    db.session.commit()
    
    return jsonify({
        'mensaje': 'Usuario creado exitosamente',
        'usuario': {
            'id': nuevo_usuario.id,
            'nombre': nuevo_usuario.nombre,
            'usuario': nuevo_usuario.usuario,
            'email': nuevo_usuario.email
        }
    }), 201

# Endpoint para actualizar usuario
@app.route('/api/usuarios/<int:usuario_id>', methods=['PUT'])
@login_required
def actualizar_usuario_api(usuario_id):
    if not current_user.es_admin:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    usuario = Usuario.query.get_or_404(usuario_id)
    data = request.json
    
    # Actualizar campos
    if 'nombre' in data:
        usuario.nombre = data['nombre']
    if 'usuario' in data:
        # Verificar que el nuevo usuario no exista
        if Usuario.query.filter_by(usuario=data['usuario']).first() and usuario.usuario != data['usuario']:
            return jsonify({'error': 'Nombre de usuario ya existe'}), 400
        usuario.usuario = data['usuario']
    if 'celular' in data:
        usuario.celular = data['celular']
    if 'email' in data:
        if Usuario.query.filter_by(email=data['email']).first() and usuario.email != data['email']:
            return jsonify({'error': 'Email ya existe'}), 400
        usuario.email = data['email']
    if 'password' in data and data['password']:
        usuario.password_hash = hash_password(data['password'])
    if 'es_admin' in data:
        # No permitir que se quite el admin al último administrador
        admin_count = Usuario.query.filter_by(es_admin=True).count()
        if not data['es_admin'] and admin_count == 1 and usuario.es_admin:
            return jsonify({'error': 'No puedes quitar permisos de admin al único administrador'}), 400
        usuario.es_admin = data['es_admin']
    
    db.session.commit()
    
    return jsonify({
        'mensaje': 'Usuario actualizado exitosamente',
        'usuario': {
            'id': usuario.id,
            'nombre': usuario.nombre,
            'usuario': usuario.usuario,
            'email': usuario.email,
            'es_admin': usuario.es_admin
        }
    })

# Endpoint para eliminar usuario
@app.route('/api/usuarios/<int:usuario_id>', methods=['DELETE'])
@login_required
def eliminar_usuario_api(usuario_id):
    if not current_user.es_admin:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    usuario = Usuario.query.get_or_404(usuario_id)
    
    # No permitir eliminar al propio admin
    if usuario.id == current_user.id:
        return jsonify({'error': 'No puedes eliminar tu propio usuario'}), 400
    
    # No permitir eliminar al último administrador
    if usuario.es_admin:
        admin_count = Usuario.query.filter_by(es_admin=True).count()
        if admin_count == 1:
            return jsonify({'error': 'No puedes eliminar al único administrador'}), 400
    
    db.session.delete(usuario)
    db.session.commit()
    
    return jsonify({'mensaje': 'Usuario eliminado exitosamente'})

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada exitosamente', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)