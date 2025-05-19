from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
import os
from dotenv import load_dotenv
from functools import wraps
from datetime import datetime, timezone # Añadido timezone para el parseo de fechas

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "una_clave_secreta_muy_fuerte_y_aleatoria_para_flask_tfg2")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

@app.context_processor
def inject_now():
    user_id_from_session = None
    if 'token' in session: 
        user_id_from_session = session.get('current_user_id_from_me_endpoint') 
    return {'now': datetime.utcnow(), 'current_user_id_from_session': user_id_from_session}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'token' not in session:
            flash("Por favor, inicia sesión para acceder a esta página.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def make_api_request(endpoint, method="GET", data=None, files=None, token=None, params=None):
    if not token:
        token = session.get('token')

    public_endpoints_prefixes = ["/login", "/usuarios/", "/coches/"]
    is_chat_initiate_request = endpoint.startswith("/chat/conversations/initiate")
    is_chat_me_request = endpoint.startswith("/chat/conversations/me")
    
    requires_token = True
    if any(endpoint.startswith(prefix) for prefix in public_endpoints_prefixes):
        requires_token = False 
    elif is_chat_initiate_request: 
        requires_token = True
    elif is_chat_me_request: 
        requires_token = True
    
    if requires_token and not token:
        print(f"FRONTEND (make_api_request): Acceso denegado a {endpoint}. Token de autenticación no encontrado/requerido.")
        error_msg = "Token de autenticación no encontrado en sesión."
        if endpoint.startswith("/chat/"):
            error_msg = "Se requiere autenticación para acceder a esta función de chat."
        return None, error_msg, 401

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if method.upper() in ["POST", "PUT"] and not files:
        headers["Content-Type"] = "application/json"

    url = f"{BACKEND_API_URL}{endpoint}"
    
    print(f"FRONTEND (make_api_request): Llamando a {method} {url} con params={params}, data={'present' if data else 'absent'}, files={'present' if files else 'absent'}")

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, files=files, headers=headers, params=params if method.upper() == "POST" and params else None)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            return None, "Método HTTP no soportado por la función auxiliar.", 0

        status_code = response.status_code
        print(f"FRONTEND (make_api_request): Respuesta de {url}: Status {status_code}, Content: {response.text[:200]}...")

        if status_code == 204:
            return True, None, status_code
        
        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError:
            response_data = None
            if status_code >= 400:
                 error_message = response.text or f"Error del servidor (Código: {status_code}, sin detalle JSON)"
                 print(f"FRONTEND (make_api_request): Error (no JSON) - {error_message}")
                 return None, error_message, status_code
        
        if status_code < 400 :
            return response_data, None, status_code
        else: 
            error_detail = "Error desconocido del servidor."
            if response_data and isinstance(response_data, dict):
                error_detail = response_data.get("detail", error_detail)
            elif response.text:
                error_detail = response.text 
            
            if status_code == 401 and token:
                print(f"FRONTEND (make_api_request): Error 401 con token para {url}. Limpiando sesión.")
                session.pop('token', None)
                session.pop('user_alias', None)
                session.pop('current_user_id_from_me_endpoint', None) 
                error_detail = error_detail or "Sesión inválida o expirada. Por favor, inicia sesión de nuevo."

            print(f"FRONTEND (make_api_request): Error {status_code} - {error_detail}")
            return None, error_detail, status_code

    except requests.exceptions.ConnectionError as e:
        print(f"FRONTEND (make_api_request): Error de conexión llamando a API {endpoint}: {e}")
        return None, f"Error de conexión con el servidor: {e}", 0
    except Exception as e:
        print(f"FRONTEND (make_api_request): Error inesperado llamando a API {endpoint}: {e}")
        return None, f"Error inesperado: {e}", 0


@app.route('/')
def index():
    if 'token' in session:
        return redirect(url_for('main_page'))
    return redirect(url_for('login'))

@app.route('/main_page')
@login_required
def main_page():
    token = session.get('token')
    user_alias_session = session.get('user_alias')
    current_user_id_flask = session.get('current_user_id_from_me_endpoint') 

    if not current_user_id_flask: 
        user_profile_data, profile_error, profile_status_code = make_api_request("/usuarios/me", token=token)
        if not profile_error and user_profile_data:
            current_user_id_flask = user_profile_data.get('id')
            session['current_user_id_from_me_endpoint'] = current_user_id_flask 
            print(f"ID del usuario actual obtenido y guardado en sesión: {current_user_id_flask}")
        elif profile_status_code == 401:
            flash(profile_error or "Tu sesión ha expirado. Por favor, inicia sesión de nuevo.", "error")
            return redirect(url_for('login', next=request.url))
        else:
            flash(f"No se pudo obtener la información del usuario actual: {profile_error or 'Error desconocido'}", "warning")
            print(f"Error obteniendo /usuarios/me: Código {profile_status_code}, Error: {profile_error}")
    else:
        print(f"ID del usuario actual recuperado de sesión: {current_user_id_flask}")

    todos_los_coches_flask = [] 
    response_data_coches, coches_error, coches_status_code = make_api_request(f"/coches/?limit=100") 

    if not coches_error and response_data_coches:
        if isinstance(response_data_coches, list):
            todos_los_coches_flask = response_data_coches
        else:
            flash("Error al cargar la lista de coches (formato inesperado).", "warning")
    elif coches_status_code == 401:
        flash(coches_error or "Tu sesión ha expirado o no es válida para cargar coches. Por favor, inicia sesión de nuevo.", "error")
        return redirect(url_for('login', next=request.url))
    elif coches_error:
        flash(f"Error al cargar la lista de coches: {coches_error}", "danger")
        
    return render_template('app/main_page.html', 
                           user_alias=user_alias_session,
                           token_sesion=token,
                           todos_los_coches=todos_los_coches_flask,
                           current_user_id=current_user_id_flask) 

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'token' in session:
        return redirect(url_for('main_page'))
    if request.method == 'POST':
        alias = request.form.get('alias')
        contrasena = request.form.get('contrasena')
        if not alias or not contrasena:
            flash("Alias y contraseña son requeridos.", "danger")
            return redirect(url_for('login'))
        
        data, error, status_code = make_api_request(
            "/login", 
            method="POST", 
            data={"alias": alias, "contrasena": contrasena} 
        )
        
        if not error and status_code == 200 and data and data.get('access_token'):
            session['token'] = data.get('access_token')
            user_profile_data, profile_error, _ = make_api_request("/usuarios/me", token=session['token'])
            if not profile_error and user_profile_data:
                session['user_alias'] = user_profile_data.get('alias', alias)
                session['current_user_id_from_me_endpoint'] = user_profile_data.get('id') 
            else: 
                session.pop('token', None)
                flash(profile_error or "No se pudo verificar tu perfil después del login.", "error")
                return redirect(url_for('login'))
            
            flash("¡Login Exitoso!", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main_page'))
        else:
            flash(error or "Error de autenticación. Verifica tus credenciales.", "danger")
        return redirect(url_for('login'))
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'token' in session:
        return redirect(url_for('main_page'))
    form_data = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        payload = {
            "alias": form_data.get('alias'),
            "nombre": form_data.get('nombre'),
            "apellido": form_data.get('apellido'),
            "contrasena": form_data.get('contrasena')
        }
        if not all(val for val in [payload["alias"], payload["nombre"], payload["apellido"], payload["contrasena"]]):
            flash("Todos los campos son requeridos.", "danger")
            return render_template('auth/register.html', form_data=form_data)
        if len(payload["contrasena"]) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", "danger")
            return render_template('auth/register.html', form_data=form_data)

        data, error, status_code = make_api_request("/usuarios/", method="POST", data=payload)
        if not error and status_code == 201 and data:
            flash(f"¡Usuario '{data.get('alias')}' registrado! Ahora puedes iniciar sesión.", "success")
            return redirect(url_for('login'))
        else:
            flash(f"Error al registrar: {error or 'Inténtalo de nuevo.'}", "danger")
        return render_template('auth/register.html', form_data=form_data)
    return render_template('auth/register.html', form_data={})

@app.route('/logout')
def logout():
    session.pop('token', None)
    session.pop('user_alias', None)
    session.pop('current_user_id_from_me_endpoint', None) 
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_page():
    user_info_display = None 
    token = session.get('token')
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == "update_profile":
            payload = {"nombre": request.form.get('nombre'), "apellido": request.form.get('apellido')}
            if not payload["nombre"] or not payload["apellido"]:
                flash("Nombre y apellido son requeridos.", "danger")
            else:
                updated_data, error, status_code_api = make_api_request("/usuarios/me", method="PUT", data=payload, token=token)
                if not error and status_code_api == 200:
                    flash("Perfil actualizado exitosamente.", "success")
                    if updated_data:
                        session['user_alias'] = updated_data.get('alias', session.get('user_alias'))
                        session['current_user_id_from_me_endpoint'] = updated_data.get('id', session.get('current_user_id_from_me_endpoint'))
                elif status_code_api == 401: 
                    flash(error or "Sesión inválida. Por favor, inicia sesión.", "error")
                    return redirect(url_for('login', next=request.url))
                else:
                    flash(f"Error al actualizar perfil: {error or 'Inténtalo de nuevo.'}", "danger")
            return redirect(url_for('profile_page'))
        
        elif action == "delete_account":
            _, error, status_code_api = make_api_request("/usuarios/me", method="DELETE", token=token)
            if not error and status_code_api == 204:
                flash("Tu cuenta ha sido eliminada.", "success")
                session.pop('token', None); session.pop('user_alias', None)
                session.pop('current_user_id_from_me_endpoint', None)
                return redirect(url_for('login'))
            elif status_code_api == 401:
                flash(error or "Sesión inválida. Por favor, inicia sesión.", "error")
                return redirect(url_for('login', next=request.url))
            else:
                flash(f"Error al eliminar cuenta: {error or 'Inténtalo de nuevo.'}", "danger")
            return redirect(url_for('profile_page')) 
    
    user_info_display, error, status_code_api = make_api_request("/usuarios/me", token=token)
    if error:
        if status_code_api == 401: 
            flash(error or "Sesión inválida. Por favor, inicia sesión.", "error")
            return redirect(url_for('login', next=request.url))
        flash(f"Error al cargar perfil: {error or 'Inténtalo de nuevo.'}", "danger")
        user_info_display = None
    elif user_info_display: 
        session['current_user_id_from_me_endpoint'] = user_info_display.get('id')
        
    return render_template('app/profile.html', user_info=user_info_display)

@app.route('/my-cars')
@login_required
def my_cars_page():
    coches_del_usuario, error, status_code_api = make_api_request("/usuarios/me/coches/")
    if error:
        if status_code_api == 401:
            flash(error or "Sesión inválida. Por favor, inicia sesión.", "error")
            return redirect(url_for('login', next=request.url))
        flash(f"Error al cargar tus coches: {error or 'Inténtalo de nuevo'}", "danger")
        coches_del_usuario = [] 
    return render_template('app/mycars.html', coches_del_usuario=coches_del_usuario if coches_del_usuario else [])

@app.route('/publish-car', methods=['GET', 'POST'])
@login_required
def publish_car_page():
    form_data_display = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        token = session.get('token')
        form_fields = {
            "marca": request.form.get('marca'), "modelo": request.form.get('modelo'),
            "ano_str": request.form.get('ano'), "cv_str": request.form.get('cv'),
            "color": request.form.get('color'), "combustible": request.form.get('combustible'),
            "km_str": request.form.get('km'), "etiqueta": request.form.get('etiqueta'),
            "localidad": request.form.get('localidad'), "descripcion": request.form.get('descripcion')
        }
        uploaded_files = request.files.getlist("car_images")
        required_text_fields = ["marca", "modelo", "ano_str", "cv_str", "color", "combustible", "km_str"]
        
        if not all(form_fields.get(f) for f in required_text_fields):
            flash("Por favor, completa todos los campos obligatorios del coche.", "danger")
            return render_template('app/publish_car.html', form_data=form_data_display)
        try:
            ano = int(form_fields["ano_str"]); cv = int(form_fields["cv_str"]); km = int(form_fields["km_str"])
        except ValueError:
            flash("Año, CV y Kilómetros deben ser números.", "danger")
            return render_template('app/publish_car.html', form_data=form_data_display)

        image_urls = []
        valid_files = [f for f in uploaded_files if f and f.filename]
        if len(valid_files) > 6:
            flash("Puedes subir un máximo de 6 imágenes.", "danger")
            return render_template('app/publish_car.html', form_data=form_data_display)

        for file_storage in valid_files:
            files_payload = {'file': (file_storage.filename, file_storage.stream, file_storage.content_type)}
            img_data, error, status_code_api = make_api_request("/upload-image/", method="POST", files=files_payload, token=token)
            if error or status_code_api != 200:
                flash(f"Error al subir imagen '{file_storage.filename}': {error or 'Error desconocido'}", "danger")
                if status_code_api == 401: 
                    return redirect(url_for('login', next=request.url))
                return render_template('app/publish_car.html', form_data=form_data_display)
            image_urls.append(img_data.get("image_url"))
        
        car_payload = {
            "marca": form_fields["marca"], "modelo": form_fields["modelo"], "ano": ano, "cv": cv,
            "color": form_fields["color"], "combustible": form_fields["combustible"], "km": km,
            "etiqueta": form_fields["etiqueta"] or None, "localidad": form_fields["localidad"] or None,
            "descripcion": form_fields["descripcion"] or None, "imagen_urls": image_urls
        }
        
        _, error, status_code_api = make_api_request("/coches/", method="POST", data=car_payload, token=token)
        if not error and status_code_api == 201:
            flash("¡Coche publicado exitosamente!", "success")
            return redirect(url_for('my_cars_page'))
        else:
            if status_code_api == 401:
                flash(error or "Sesión inválida al publicar coche. Por favor, inicia sesión.", "error")
                return redirect(url_for('login', next=request.url))
            flash(f"Error al publicar coche: {error or 'Inténtalo de nuevo.'}", "danger")
        return render_template('app/publish_car.html', form_data=form_data_display)
    return render_template('app/publish_car.html', form_data={})

@app.route('/edit-car/<car_id>', methods=['GET', 'POST'])
@login_required
def edit_car_page(car_id):
    token = session.get('token')
    coche_actual_para_template = None

    if request.method == 'POST':
        form_data = request.form.to_dict()
        nuevas_imagenes_files = request.files.getlist("car_images_new")
        try:
            ano = int(form_data["ano"]) if form_data.get("ano") else None
            cv = int(form_data["cv"]) if form_data.get("cv") else None
            km = int(form_data["km"]) if form_data.get("km") else None
        except ValueError:
            flash("Año, CV y Kilómetros deben ser números válidos.", "danger")
            coche_actual_para_template, _, _ = make_api_request(f"/coches/{car_id}", token=token)
            return render_template('app/edit_car.html', coche=coche_actual_para_template or {'id': car_id})

        update_payload = {
            "marca": form_data.get("marca"), "modelo": form_data.get("modelo"),
            "ano": ano, "cv": cv, "color": form_data.get("color"),
            "combustible": form_data.get("combustible"), "km": km,
            "etiqueta": form_data.get("etiqueta") or None,
            "localidad": form_data.get("localidad") or None,
            "descripcion": form_data.get("descripcion") or None
        }

        nuevas_image_urls = []
        valid_new_files = [f for f in nuevas_imagenes_files if f and f.filename]
        if valid_new_files:
            if len(valid_new_files) > 6:
                flash("Puedes subir un máximo de 6 imágenes nuevas.", "danger")
                coche_actual_para_template, _, _ = make_api_request(f"/coches/{car_id}", token=token)
                return render_template('app/edit_car.html', coche=coche_actual_para_template or {'id': car_id})

            for file_storage in valid_new_files:
                files_payload = {'file': (file_storage.filename, file_storage.stream, file_storage.content_type)}
                img_data, error, status_code_api = make_api_request("/upload-image/", method="POST", files=files_payload, token=token)
                if error or status_code_api != 200:
                    flash(f"Error al subir nueva imagen '{file_storage.filename}': {error}", "danger")
                    if status_code_api == 401: return redirect(url_for('login', next=request.url))
                    coche_actual_para_template, _, _ = make_api_request(f"/coches/{car_id}", token=token)
                    return render_template('app/edit_car.html', coche=coche_actual_para_template or {'id': car_id})
                nuevas_image_urls.append(img_data["image_url"])
            update_payload["imagen_urls"] = nuevas_image_urls

        _, error, status_code_api = make_api_request(f"/coches/{car_id}", method="PUT", data=update_payload, token=token)
        if not error and status_code_api == 200:
            flash("Coche actualizado exitosamente.", "success")
            return redirect(url_for('my_cars_page'))
        else:
            if status_code_api == 401: 
                flash(error or "Sesión inválida. Por favor, inicia sesión.", "error")
                return redirect(url_for('login', next=request.url))
            flash(f"Error al actualizar coche: {error or 'Inténtalo de nuevo'}", "danger")
            coche_actual_para_template, _, _ = make_api_request(f"/coches/{car_id}", token=token)
            return render_template('app/edit_car.html', coche=coche_actual_para_template or {'id': car_id})

    coche_a_editar, error, status_code_api = make_api_request(f"/coches/{car_id}", token=token)
    if error:
        if status_code_api == 401: 
            flash(error or "Sesión inválida. Por favor, inicia sesión.", "error")
            return redirect(url_for('login', next=request.url))
        flash(f"Error al cargar el coche para editar: {error}", "danger")
        return redirect(url_for('my_cars_page'))
    if not coche_a_editar:
        flash("No se encontró el coche especificado para editar o no tienes permiso.", "warning")
        return redirect(url_for('my_cars_page'))
    
    if 'id' not in coche_a_editar:
        coche_a_editar['id'] = car_id

    return render_template('app/edit_car.html', coche=coche_a_editar)

@app.route('/delete-car/<car_id>', methods=['POST'])
@login_required
def delete_car_action(car_id):
    _, error, status_code_api = make_api_request(f"/coches/{car_id}", method="DELETE")
    if not error and status_code_api == 204:
        flash("Coche eliminado exitosamente.", "success")
    elif status_code_api == 401:
        flash(error or "Sesión inválida. Por favor, inicia sesión.", "error")
        return redirect(url_for('login', next=request.referrer or url_for('my_cars_page')))
    elif status_code_api == 403:
        flash("No tienes permiso para eliminar este coche.", "danger")
    elif status_code_api == 404:
        flash("El coche que intentas eliminar no fue encontrado.", "warning")
    else:
        flash(f"Error al eliminar coche: {error or 'Inténtalo de nuevo.'}", "danger")
    return redirect(request.referrer or url_for('my_cars_page'))

# --- RUTA PARA VER DETALLES DEL COCHE (view_car_page) ---
@app.route('/car/<car_id>', methods=['GET'])
def view_car_page(car_id):
    token = session.get('token')
    
    car_details, api_error, status_code = make_api_request(
        endpoint=f"/coches/{car_id}",
        method="GET",
        token=token 
    )

    if token and not session.get('current_user_id_from_me_endpoint'):
        user_profile_data, _, _ = make_api_request("/usuarios/me", token=token)
        if user_profile_data and user_profile_data.get('id'):
            session['current_user_id_from_me_endpoint'] = user_profile_data.get('id')


    if not api_error and car_details:
        if 'id' not in car_details: 
            car_details['id'] = car_id
        return render_template('app/view_car_details.html', coche=car_details, error_message=None)
    else:
        error_message_display = "No se pudo cargar la información del coche."
        if status_code == 404:
            error_message_display = "Coche no encontrado."
        elif status_code == 401 and token:
            flash(api_error or "Tu sesión ha expirado o no es válida. Inicia sesión para una mejor experiencia.", "warning")
            error_message_display = api_error or "Error de autenticación al intentar cargar detalles."
        elif api_error:
            error_message_display = api_error
        
        flash(error_message_display, "error")
        return render_template('app/view_car_details.html', coche=None, error_message=error_message_display)


# --- RUTAS DE CHAT ---

@app.route('/chats', methods=['GET'])
@login_required
def chats_list_page():
    token = session.get('token')
    user_alias = session.get('user_alias') 

    print(f"DEBUG FLASK (chats_list_page GET): Cargando chats para el usuario '{user_alias}'")

    conversations_data_raw, error, status_code = make_api_request(
        endpoint="/chat/conversations/me", 
        method="GET",
        token=token
    )

    conversations_processed = []
    if not error and conversations_data_raw:
        for convo_raw in conversations_data_raw:
            if convo_raw.get('ultimo_mensaje_en'):
                try:
                    dt_obj = datetime.fromisoformat(convo_raw['ultimo_mensaje_en'].replace('Z', '+00:00'))
                    convo_raw['ultimo_mensaje_en'] = dt_obj
                except (ValueError, TypeError) as e_date:
                    print(f"WARN FLASK (chats_list_page): No se pudo parsear la fecha 'ultimo_mensaje_en': {convo_raw['ultimo_mensaje_en']} - Error: {e_date}")
            
            if convo_raw.get('creado_en'):
                 try:
                    dt_obj_creado = datetime.fromisoformat(convo_raw['creado_en'].replace('Z', '+00:00'))
                    convo_raw['creado_en'] = dt_obj_creado
                 except (ValueError, TypeError) as e_date_creado:
                    print(f"WARN FLASK (chats_list_page): No se pudo parsear la fecha 'creado_en': {convo_raw['creado_en']} - Error: {e_date_creado}")

            conversations_processed.append(convo_raw)
    elif error:
        if status_code == 401:
            flash(error or "Tu sesión ha expirado. Por favor, inicia sesión de nuevo.", "error")
            return redirect(url_for('login', next=request.url))
        
        flash(f"No se pudieron cargar tus conversaciones: {error}", "danger")
        print(f"ERROR FLASK (chats_list_page): Error al obtener conversaciones - Código: {status_code}, Detalle: {error}")
        return render_template('app/chats_list.html', conversations=[], error_message=error, user_alias=user_alias)

    if not conversations_data_raw and not error:
        conversations_processed = []

    print(f"DEBUG FLASK (chats_list_page): {len(conversations_processed)} conversaciones procesadas para la plantilla.")
        
    return render_template('app/chats_list.html', 
                           conversations=conversations_processed, 
                           user_alias=user_alias,
                           error_message=error if error else None)

# NUEVA RUTA: Iniciar una conversación o ir a una existente
@app.route('/initiate-chat/<car_id>', methods=['GET'])
@login_required
def initiate_chat_with_owner(car_id):
    token = session.get('token')
    
    # El endpoint del backend es POST /chat/conversations/initiate?car_id=...
    # Así que pasamos car_id como un parámetro de query para la petición POST.
    conversation_details, error, status_code = make_api_request(
        endpoint=f"/chat/conversations/initiate",
        method="POST", # El backend espera POST para este endpoint
        params={"car_id": car_id}, # car_id como query parameter
        token=token
    )

    if error:
        if status_code == 401:
            flash(error or "Tu sesión ha expirado. Por favor, inicia sesión de nuevo.", "error")
            return redirect(url_for('login', next=request.url))
        flash(f"No se pudo iniciar o encontrar la conversación: {error}", "danger")
        # Redirigir de vuelta a la página del coche si falla
        return redirect(url_for('view_car_page', car_id=car_id))

    if conversation_details and conversation_details.get('id'):
        conversation_id = conversation_details.get('id')
        # Redirigir a la página de la conversación específica
        return redirect(url_for('chat_conversation_page', conversation_id=conversation_id))
    else:
        flash("Error inesperado al obtener los detalles de la conversación.", "danger")
        return redirect(url_for('view_car_page', car_id=car_id))

# NUEVA RUTA: Ver una conversación específica
@app.route('/chat/<conversation_id>', methods=['GET', 'POST'])
@login_required
def chat_conversation_page(conversation_id):
    token = session.get('token')
    current_user_id = session.get('current_user_id_from_me_endpoint') # Necesitamos el ID del usuario actual
    
    # --- MANEJO DE POST (Enviar un nuevo mensaje) ---
    if request.method == 'POST':
        contenido_mensaje = request.form.get('contenido')
        if not contenido_mensaje or not contenido_mensaje.strip():
            flash("El mensaje no puede estar vacío.", "warning")
        else:
            # Llamar al endpoint del backend para enviar el mensaje
            # POST /chat/conversations/{conversation_id}/messages
            # Body: {"contenido": "texto del mensaje"}
            message_payload = {"contenido": contenido_mensaje.strip()}
            sent_message_data, error, status_code = make_api_request(
                endpoint=f"/chat/conversations/{conversation_id}/messages",
                method="POST",
                data=message_payload,
                token=token
            )
            if error:
                if status_code == 401:
                    flash(error or "Tu sesión ha expirado. Por favor, inicia sesión de nuevo.", "error")
                    return redirect(url_for('login', next=request.url))
                flash(f"Error al enviar el mensaje: {error}", "danger")
            else:
                flash("Mensaje enviado.", "success")
        
        # Siempre redirigir después de un POST para evitar reenvíos del formulario
        return redirect(url_for('chat_conversation_page', conversation_id=conversation_id))

    # --- MANEJO DE GET (Mostrar la conversación) ---
    # 1. Obtener detalles de la conversación (para el encabezado, etc.)
    #    El backend ya devuelve esto en /chat/conversations/me,
    #    pero podríamos necesitar un endpoint específico /chat/conversations/{id}/details
    #    o simplemente filtrar de la lista que ya tenemos o volver a llamar.
    #    Por ahora, asumiremos que necesitamos obtener los detalles de la conversación de alguna forma.
    #    Lo más simple es obtener la lista completa y buscarla, o hacer una llamada específica si la tienes.
    #    Para este ejemplo, buscaremos en la lista de conversaciones del usuario si está disponible.
    
    all_my_convos_raw, error_convos, sc_convos = make_api_request("/chat/conversations/me", token=token)
    conversation_details_display = None
    if not error_convos and all_my_convos_raw:
        for convo in all_my_convos_raw:
            if convo.get('id') == conversation_id:
                # Preprocesar fechas para la plantilla
                if convo.get('ultimo_mensaje_en'):
                    try: convo['ultimo_mensaje_en'] = datetime.fromisoformat(convo['ultimo_mensaje_en'].replace('Z', '+00:00'))
                    except: pass
                if convo.get('creado_en'):
                    try: convo['creado_en'] = datetime.fromisoformat(convo['creado_en'].replace('Z', '+00:00'))
                    except: pass
                conversation_details_display = convo
                break
    
    if not conversation_details_display and not error_convos: # Si no se encontró o no hubo error al buscar
        flash("No se encontró la conversación o no tienes acceso a ella.", "warning")
        return redirect(url_for('chats_list_page'))
    elif error_convos and sc_convos == 401:
        flash(error_convos or "Tu sesión ha expirado.", "error")
        return redirect(url_for('login', next=request.url))
    elif error_convos:
        flash(f"Error al cargar detalles de la conversación: {error_convos}", "danger")
        return redirect(url_for('chats_list_page'))


    # 2. Obtener los mensajes de esta conversación
    messages_data_raw, error_msgs, sc_msgs = make_api_request(
        endpoint=f"/chat/conversations/{conversation_id}/messages",
        method="GET",
        token=token,
        params={"limit": 100} # Cargar hasta 100 mensajes, por ejemplo
    )

    messages_processed = []
    if not error_msgs and messages_data_raw:
        for msg_raw in messages_data_raw:
            if msg_raw.get('timestamp'):
                try:
                    msg_raw['timestamp'] = datetime.fromisoformat(msg_raw['timestamp'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass # Dejar como string si falla el parseo
            messages_processed.append(msg_raw)
    elif error_msgs:
        if sc_msgs == 401: # Error de autenticación al obtener mensajes
            # Ya manejado arriba si falló al obtener detalles de la convo.
            # Si solo falla aquí, es raro pero posible.
            flash(error_msgs or "Tu sesión ha expirado al cargar mensajes.", "error")
            return redirect(url_for('login', next=request.url))
        flash(f"Error al cargar los mensajes: {error_msgs}", "danger")
        # Se puede seguir renderizando la página con el error
    
    if not messages_data_raw and not error_msgs:
        messages_processed = [] # Lista vacía si no hay mensajes

    return render_template('app/chat_conversation.html',
                           conversation_details=conversation_details_display,
                           messages=messages_processed,
                           current_user_id=current_user_id,
                           conversation_id_param=conversation_id, # Para el action del form
                           error_message=error_msgs if error_msgs else None)

# --- FIN RUTAS DE CHAT ---


if __name__ == '__main__':
    app.run(debug=True, port=5001)