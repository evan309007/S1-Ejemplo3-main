from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import bcrypt
from models import db, Usuario, Producto, CarritoItem, Orden, OrdenItem


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


@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.es_admin:
        flash('Acceso denegado', 'error')
        return redirect(url_for('perfil'))
    
    usuarios = Usuario.query.all()  # ← Cambiar a usuarios
    return render_template('dashboard.html', usuarios=usuarios)  # ← Cambiar a usuarios


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

# Página para agregar producto
@app.route('/producto/nuevo')
@login_required
def nuevo_producto():
    if not current_user.es_admin:
        flash('Acceso denegado', 'error')
        return redirect(url_for('tienda'))
    
    return render_template('agregar_productos.html')

# API para crear producto (recibe los datos del formulario)
@app.route('/api/productos', methods=['POST'])
@login_required
def crear_producto():
    if not current_user.es_admin:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    data = request.json
    
    # Validar campos requeridos
    if not data.get('nombre') or not data.get('precio'):
        return jsonify({'error': 'Nombre y precio son requeridos'}), 400
    
    # Crear el producto
    nuevo_producto = Producto(
        nombre=data['nombre'],
        descripcion=data.get('descripcion', ''),
        precio=float(data['precio']),
        stock=int(data.get('stock', 0)),
        categoria=data.get('categoria', ''),
        imagen_url=data.get('imagen_url', '')
    )
    
    db.session.add(nuevo_producto)
    db.session.commit()
    
    return jsonify({
        'mensaje': 'Producto creado exitosamente',
        'producto_id': nuevo_producto.id
    }), 201
    
# Gestión completa de productos (CRUD)
@app.route('/gestionar/productos')
@login_required
def gestionar_productos():
    if not current_user.es_admin:
        flash('Acceso denegado', 'error')
        return redirect(url_for('tienda'))
    
    productos = Producto.query.all()
    return render_template('gestionar_productos.html', productos=productos)    
    
# API para editar producto
@app.route('/api/productos/<int:producto_id>', methods=['PUT'])
@login_required
def actualizar_producto(producto_id):
    if not current_user.es_admin:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    producto = Producto.query.get_or_404(producto_id)
    data = request.json
    
    # Actualizar campos
    if 'nombre' in data:
        producto.nombre = data['nombre']
    if 'descripcion' in data:
        producto.descripcion = data['descripcion']
    if 'precio' in data:
        producto.precio = float(data['precio'])
    if 'stock' in data:
        producto.stock = int(data['stock'])
    if 'categoria' in data:
        producto.categoria = data['categoria']
    
    db.session.commit()
    
    return jsonify({'mensaje': 'Producto actualizado exitosamente'})


# API para eliminar producto
@app.route('/api/productos/<int:producto_id>', methods=['DELETE'])
@login_required
def eliminar_producto(producto_id):
    if not current_user.es_admin:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    producto = Producto.query.get_or_404(producto_id)
    
    # Verificar que no esté en ningún carrito
    en_carrito = CarritoItem.query.filter_by(producto_id=producto_id).first()
    if en_carrito:
        return jsonify({'error': 'No se puede eliminar: producto está en un carrito'}), 400
    
    db.session.delete(producto)
    db.session.commit()
    
    return jsonify({'mensaje': 'Producto eliminado exitosamente'})

# API para obtener un producto específico
@app.route('/api/productos/<int:producto_id>', methods=['GET'])
@login_required
def obtener_producto(producto_id):
    if not current_user.es_admin:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    producto = Producto.query.get_or_404(producto_id)
    
    return jsonify({
        'id': producto.id,
        'nombre': producto.nombre,
        'descripcion': producto.descripcion,
        'precio': producto.precio,
        'stock': producto.stock,
        'categoria': producto.categoria
    })
    
@app.route('/api/productos/buscar')
@login_required
def buscar_productos():
    query = request.args.get('q', '')
    if query:
        productos = Producto.query.filter(Producto.nombre.contains(query)).all()
    else:
        productos = Producto.query.all()
    
    return jsonify([{
        'id': p.id,
        'nombre': p.nombre,
        'descripcion': p.descripcion,
        'precio': p.precio,
        'stock': p.stock,
        'categoria': p.categoria,
        'imagen_url': p.imagen_url
    } for p in productos])    

# Obtener cantidad de items en el carrito
@app.route('/api/carrito/count')
@login_required
def carrito_count():
    count = CarritoItem.query.filter_by(usuario_id=current_user.id).count()
    return jsonify({'count': count})

# Agregar producto al carrito (API)
@app.route('/api/carrito/agregar', methods=['POST'])
@login_required
def agregar_carrito():
    try:
        data = request.json
        producto_id = data.get('producto_id')
        cantidad = data.get('cantidad', 1)
        
        # Validar que el producto existe
        producto = Producto.query.get(producto_id)
        if not producto:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        # Validar stock
        if producto.stock < cantidad:
            return jsonify({'error': f'Stock insuficiente. Solo hay {producto.stock} unidades'}), 400
        
        # Buscar si el producto ya está en el carrito del usuario
        carrito_item = CarritoItem.query.filter_by(
            usuario_id=current_user.id,
            producto_id=producto_id
        ).first()
        
        if carrito_item:
            # Si ya existe, actualizar cantidad
            nueva_cantidad = carrito_item.cantidad + cantidad
            if producto.stock < nueva_cantidad:
                return jsonify({'error': f'Stock insuficiente. Stock disponible: {producto.stock}'}), 400
            carrito_item.cantidad = nueva_cantidad
        else:
            # Si no existe, crear nuevo item
            carrito_item = CarritoItem(
                usuario_id=current_user.id,
                producto_id=producto_id,
                cantidad=cantidad
            )
            db.session.add(carrito_item)
        
        db.session.commit()
        
        return jsonify({
            'mensaje': f'✅ {cantidad}x {producto.nombre} agregado al carrito'
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Ver el carrito de compras
@app.route('/carrito')
@login_required
def ver_carrito():
    # Obtener todos los items del carrito del usuario actual
    items = CarritoItem.query.filter_by(usuario_id=current_user.id).all()
    
    # Calcular el total
    total = 0
    for item in items:
        total += item.producto.precio * item.cantidad
    
    return render_template('carrito.html', items=items, total=total)    

@app.route('/tienda')
@login_required
def tienda():
    # Obtener todos los productos de la base de datos
    productos = Producto.query.all()
    
    # Renderizar la plantilla pasando los productos
    return render_template('productos.html', productos=productos)

@app.route('/producto/<int:producto_id>')
@login_required
def ver_producto(producto_id):
    # Buscar el producto por su ID
    producto = Producto.query.get_or_404(producto_id)
    
    return render_template('producto_detalle.html', producto=producto)

@app.route('/api/carrito/eliminar/<int:item_id>', methods=['DELETE'])
@login_required
def eliminar_carrito_item(item_id):
    item = CarritoItem.query.get_or_404(item_id)
    
    # Verificar que el item pertenece al usuario actual
    if item.usuario_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'mensaje': 'Producto eliminado del carrito'})

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada exitosamente', 'success')
    return redirect(url_for('login'))


# Procesar checkout (crear orden)
@app.route('/api/checkout', methods=['POST'])
@login_required
def procesar_checkout():
    try:
        # Obtener items del carrito
        items = CarritoItem.query.filter_by(usuario_id=current_user.id).all()
        
        if not items:
            return jsonify({'error': 'El carrito está vacío'}), 400
        
        # Calcular total
        total = 0
        for item in items:
            total += item.producto.precio * item.cantidad
        
        # Crear la orden
        orden = Orden(
            usuario_id=current_user.id,
            total=total,
            estado='pendiente'
        )
        db.session.add(orden)
        db.session.flush()  # Para obtener el ID de la orden
        
        # Crear items de la orden y actualizar stock
        for item in items:
            orden_item = OrdenItem(
                orden_id=orden.id,
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio_unitario=item.producto.precio
            )
            db.session.add(orden_item)
            
            # Actualizar stock del producto
            item.producto.stock -= item.cantidad
        
        # Vaciar el carrito
        for item in items:
            db.session.delete(item)
        
        db.session.commit()
        
        return jsonify({
            'mensaje': '✅ Compra realizada con éxito',
            'orden_id': orden.id,
            'total': total
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
    # Ver histórico de órdenes del usuario
@app.route('/mis-ordenes')
@login_required
def mis_ordenes():
    ordenes = Orden.query.filter_by(usuario_id=current_user.id).order_by(Orden.fecha.desc()).all()
    return render_template('mis_ordenes.html', ordenes=ordenes)

# Ver detalle de una orden específica
@app.route('/orden/<int:orden_id>')
@login_required
def ver_orden(orden_id):
    orden = Orden.query.get_or_404(orden_id)
    
    # Verificar que la orden pertenece al usuario actual o es admin
    if orden.usuario_id != current_user.id and not current_user.es_admin:
        flash('Acceso denegado', 'error')
        return redirect(url_for('tienda'))
    
    return render_template('orden_detalle.html', orden=orden)

if __name__ == '__main__':
    app.run(debug=True)