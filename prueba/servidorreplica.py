import zmq
import time
import random
import threading
import json
import argparse

solicitudes_resueltas = []

def cargar_datos_archivo(json_file):
    try:
        with open(json_file, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = {"taxis": [], "servicios": [], "estadisticas": {"servicios_satisfactorios": 0, "servicios_negados": 0}}
    return data

def guardar_datos_archivo(json_file, data):
    with open(json_file, 'w') as file:
        json.dump(data, file, indent=4)

def user_is_still_waiting(solicitud, solicitudes_timeout):
    user_id = solicitud.split()[1]  # Extraer el ID del usuario de la solicitud
    current_time = time.time()

    if user_id in solicitudes_timeout and current_time > solicitudes_timeout[user_id]:
        return False  # El usuario ya no está esperando
    return True  # El usuario sigue esperando

def registrar_servicio(data, taxi_id, usuario_posicion, taxi_posicion, servicio_satisfactorio=True):
    data["servicios"].append({
        "hora_asignacion": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "taxi_id": taxi_id,
        "usuario_posicion": usuario_posicion,
        "taxi_posicion": taxi_posicion
    })
    if servicio_satisfactorio:
        data["estadisticas"]["servicios_satisfactorios"] += 1
    else:
        data["estadisticas"]["servicios_negados"] += 1




def listen_for_activation():
    """Escucha señales de activación remota mediante un ping."""
    context = zmq.Context()
    activation_socket = context.socket(zmq.REP)
    activation_socket.bind("tcp://*:5561")  # Puerto para recibir el ping de activación

    while True:
        mensaje = activation_socket.recv_string()
        if mensaje == "ping":
            print("Recibido ping de activación, tomando control...")
            # Enviar respuesta de confirmación
            activation_socket.send_string("OK_ACTIVATED")
            # Activar la réplica como servidor principal
            activar_replica()

def activar_replica():
    # Implementa la lógica para activar la réplica (cambiar puertos, etc.)
    print("Activando réplica ahora...")
    # Cerrar y reabrir sockets para tomar el control como servidor principal
    servidor(is_primary=True)



def servidor(is_primary=False):
    context = zmq.Context()

    # Configurar los puertos según si es primario o réplica (standby)
    if is_primary:
        sub_port = 5555
        user_rep_port = 5556
        print("Iniciando como servidor central (primario)")
    else:
        # Usar puertos "standby" para evitar conflicto con el primario
        sub_port = 5571
        user_rep_port = 5572
        print("Iniciando como servidor réplica en standby")

    # SUB para recibir posiciones de taxis
    sub_socket = context.socket(zmq.SUB)
    try:
        sub_socket.bind(f"tcp://*:{sub_port}")
    except zmq.ZMQError as e:
        print(f"Error al hacer bind al puerto {sub_port}: {e}")
        return

    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    # REP para recibir solicitudes de usuarios
    user_rep_socket = context.socket(zmq.REP)
    try:
        user_rep_socket.bind(f"tcp://*:{user_rep_port}")
    except zmq.ZMQError as e:
        print(f"Error al hacer bind al puerto {user_rep_port}: {e}")
        return

    # REQ para enviar servicios a los taxis
    taxi_req_socket = context.socket(zmq.REQ)

    # REP para el ping/pong health-check
    ping_rep_socket = context.socket(zmq.REP)
    ping_rep_socket.bind(f"tcp://*:5559")

    taxis = {}
    solicitudes = []
    taxis_activos = {}  # Diccionario para gestionar el estado de taxis (si están activos)
    solicitudes_timeout = {}  # Diccionario para registrar el timeout de cada solicitud
    taxi_ip = '10.43.101.211'

    # Cargar datos del archivo JSON
    json_file = 'datos_taxis.json'
    data = cargar_datos_archivo(json_file)


    while True:
        # Recibir posiciones de taxis
        if sub_socket.poll(1000):  # Tiempo de espera para recibir posiciones
            mensaje = sub_socket.recv_string()
            print(f"Recibido mensaje: {mensaje}")
            partes = mensaje.split(maxsplit=2)
            if len(partes) == 3:
                id_taxi = int(partes[1])
                posicion = partes[2]
                try:
                    taxi_posicion = json.loads(posicion)  # Convertir la cadena JSON a diccionario
                    taxis[id_taxi] = taxi_posicion
                    taxis_activos[id_taxi] = True 

                    # Actualizar la posición del taxi en el archivo JSON con el formato establecido
                    taxi_data = next((t for t in data["taxis"] if t["id"] == id_taxi), None)
                    if taxi_data:
                        taxi_data["posiciones"].append({
                            "hora": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "x": taxi_posicion["x"],
                            "y": taxi_posicion["y"]
                        })
                    else:
                        data["taxis"].append({
                            "id": id_taxi,
                            "posiciones": [{
                                "hora": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "x": taxi_posicion["x"],
                                "y": taxi_posicion["y"]
                            }],
                            "servicios_realizados": 0
                        })
                    guardar_datos_archivo(json_file, data)
                except json.JSONDecodeError as e:
                    print(f"Error al decodificar JSON: {e}")
            else:
                print("Mensaje recibido no está en el formato esperado.")

        # Recibir solicitudes de usuarios
        if user_rep_socket.poll(1000):  # Tiempo de espera para solicitudes de usuario
            solicitud = user_rep_socket.recv_string()
            print(f"Solicitud recibida: {solicitud}")
            solicitudes.append(solicitud) 

            # Registrar el tiempo en que expira el timeout para esta solicitud
            user_id = solicitud.split()[1]
            solicitudes_timeout[user_id] = time.time() + 15  # Timeout de 15 segundos para cada solicitud, establecido

            # Verificar si hay health_checktaxis disponibles
            if len(taxis) > 0:
                if user_is_still_waiting(solicitud, solicitudes_timeout):
                    # La selección se maneja al azar de momento
                    taxi_seleccionado = seleccionar_taxi(taxis)
                    print(f"Asignando servicio al taxi {taxi_seleccionado}")

                      # Conectar al taxi seleccionado
                    taxi_req_socket.connect(f"tcp://{taxi_ip}:556{taxi_seleccionado}")
        
                    taxi_req_socket.send_string("Servicio asignado")
                    respuesta = taxi_req_socket.recv_string()
                    print(f"Respuesta del taxi {taxi_seleccionado}: {respuesta}")
                    taxi_req_socket.disconnect(f"tcp://{taxi_ip}:556{taxi_seleccionado}")  # Desconectar después del uso

                    # Eliminar la solicitud después de asignarla
                    solicitudes.remove(solicitud)
                    solicitudes_resueltas.append(solicitud)  # Marcar la solicitud como resuelta

                    # Registrar el servicio en el archivo JSON
                    taxi_posicion = taxis[taxi_seleccionado]
                    usuario_posicion = solicitud.split(maxsplit=2)[2:]  # Obtener la posición del usuario de la solicitud
                    registrar_servicio(data, taxi_seleccionado, usuario_posicion, taxi_posicion, servicio_satisfactorio=True)
                    guardar_datos_archivo(json_file, data)
                    user_rep_socket.send_string(f"Taxi {taxi_seleccionado} asignado")

                else:
                    # Eliminar la solicitud después del timeout
                    print(f"Usuario ya no está esperando, eliminando la solicitud.")
                    solicitudes.remove(solicitud)
                    taxi_posicion = taxis.get(taxi_seleccionado, {"x": None, "y": None})
                    usuario_posicion = solicitud.split(maxsplit=2)[2:]  # Obtener la posición del usuario de la solicitud
                    registrar_servicio(data, taxi_seleccionado, usuario_posicion, taxi_posicion, servicio_satisfactorio=False)
                    guardar_datos_archivo(json_file, data)
                    user_rep_socket.send_string("Usuario ya no está esperando.")
            else:
                print("No hay taxis disponibles")
                user_rep_socket.send_string("No hay taxis disponibles, intente más tarde")

        # Manejar el health-check (mediante verificación constante con ping-pong)
        if ping_rep_socket.poll(1000):  
            ping_message = ping_rep_socket.recv_string()
            if ping_message == "ping":
                print("Recibido ping, respondiendo con pong")
                ping_rep_socket.send_string("pong") # Enviando pong, confirmando estado activo

        time.sleep(1)

def seleccionar_taxi(taxis):
    return random.choice(list(taxis.keys()))

if __name__ == "__main__":
    # Argumentos de línea de comando para saber si es réplica o primario
    parser = argparse.ArgumentParser(description="Servidor Central o Réplica")
    parser.add_argument("--replica", action="store_true", help="Iniciar como réplica")
    args = parser.parse_args()

servidor(is_primary=False)

if __name__ == "__main__":
    # Socket para recibir el estado desde el servidor principal
    context = zmq.Context()
    replica_socket = context.socket(zmq.PULL)
    replica_socket.bind("tcp://*:5559")  # Puerto en el que la réplica recibe el estado

    # Lanzar el proceso para recibir el estado
    threading.Thread(target=recibir_estado, args=(replica_socket,)).start()

    # Lanzar la escucha de activación en un hilo separado
    threading.Thread(target=listen_for_activation).start()

    print("Réplica lista para activación remota.")

