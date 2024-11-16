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

def sincronizar_estado(replica_socket, taxis, solicitudes, taxis_activos, solicitudes_resueltas):
    while True:
        estado = {
            'taxis': taxis,
            'solicitudes': solicitudes,
            'solicitudes_resueltas': solicitudes_resueltas,
            'taxis_activos': taxis_activos
        }
        replica_socket.send_pyobj(estado)  # Enviar el estado como objeto Python serializado
        time.sleep(3)  # Sincronizar cada 3 segundos, cambiar si necesario

def user_is_still_waiting(solicitud, solicitudes_timeout):
    user_id = solicitud.split()[1]  # Extraer el ID del usuario de la solicitud
    current_time = time.time()

    if user_id in solicitudes_timeout and current_time > solicitudes_timeout[user_id]:
        return False  
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


def servidor(is_primary=True):
    context = zmq.Context()

    # Configurar los puertos según si es primario o réplica
    user_rep_port = 5551 if is_primary else 5552

    # Conectar a ambos brokers (Broker 1 y Broker 2)
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect("tcp://localhost:5556")  # Conectar al Broker 1
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "ubicacion_taxi")  # Suscribirse al tópico de posiciones

    sub_socket2 = context.socket(zmq.SUB)
    sub_socket2.connect("tcp://localhost:5756")  # Conectar al Broker 2
    sub_socket2.setsockopt_string(zmq.SUBSCRIBE, "estado_taxi")  # Suscribirse al tópico de posiciones

    # REP para recibir solicitudes de usuarios
    user_rep_socket = context.socket(zmq.REP)
    user_rep_socket.bind(f"tcp://*:{user_rep_port}")

    # REQ para enviar servicios a los taxis
    taxi_req_socket = context.socket(zmq.REQ)

    # REP para el health-check
    ping_rep_socket = context.socket(zmq.REP)
    ping_rep_socket.bind(f"tcp://*:5558")

    taxis = {}
    solicitudes = []
    taxis_activos = {}
    solicitudes_timeout = {}
    taxi_ip = 'localhost'

    json_file = 'datos_taxis.json'
    data = cargar_datos_archivo(json_file)

    print("Servidor iniciado como", "Primario" if is_primary else "Réplica")

    # Configuración de poller para manejar múltiples sockets sin bloquear
    poller = zmq.Poller()
    poller.register(sub_socket, zmq.POLLIN)  # Registrar el socket SUB del Broker 1
    poller.register(sub_socket2, zmq.POLLIN)  # Registrar el socket SUB del Broker 2
    poller.register(user_rep_socket, zmq.POLLIN)  # Registrar el socket REP para usuarios
    poller.register(ping_rep_socket, zmq.POLLIN)  # Registrar el socket REP para health-check

    ultimo_tiempo_limpieza = time.time()
    while True:
        try:
            #Limpiar taxis inactivvos cada 5 segundos
            tiempo_actual = time.time()
            if tiempo_actual - ultimo_tiempo_limpieza > 5:
                limpiar_taxis_inactivos(taxis, taxis_activos)
                ultimo_tiempo_limpieza = tiempo_actual
            # Polling para revisar mensajes de los brokers y solicitudes de los usuarios
            sockets_activados = dict(poller.poll(1000))  # Polling con timeout de 1 segundo

            # Manejar mensajes de los taxis desde el Broker 1
            if sub_socket in sockets_activados:
                manejar_mensaje(sub_socket, taxis, taxis_activos, data, json_file)

            # Manejar mensajes de los taxis desde el Broker 2
            if sub_socket2 in sockets_activados:
                manejar_mensaje(sub_socket2, taxis, taxis_activos, data, json_file)

            # Manejo de solicitudes de los usuarios (REQ/REP)
            if user_rep_socket in sockets_activados:
                solicitud = user_rep_socket.recv_string()
                print(f"Solicitud recibida: {solicitud}")
                print(f"Taxis disponibles: {list(taxis.keys())}")  # Debug: mostrar taxis disponibles
                solicitudes.append(solicitud)

                user_id = solicitud.split()[1]
                solicitudes_timeout[user_id] = time.time() + 15  # Timeout de 15 segundos

                if taxis:
                    if user_is_still_waiting(solicitud, solicitudes_timeout):
                        posicion_usuario = extraer_posicion_usuario(solicitud)
                        if posicion_usuario:
                            taxi_seleccionado = seleccionar_taxi(taxis, posicion_usuario)
                            if taxi_seleccionado is not None:
                                try:
                                    print(f"Asignando servicio al taxi {taxi_seleccionado} (mas cercano)")
                                    taxi_req_socket.connect(f"tcp://{taxi_ip}:556{taxi_seleccionado}")
                                    taxi_req_socket.setsockopt(zmq.RCVTIMEO, 5000)  # Timeout de 5 segundos
                                    taxi_req_socket.send_string("Servicio asignado")
                                    respuesta = taxi_req_socket.recv_string()
                                    #print(f"Respuesta del taxi {taxi_seleccionado}: {respuesta}")
                                    taxi_req_socket.disconnect(f"tcp://{taxi_ip}:556{taxi_seleccionado}")

                                    #solicitudes.remove(solicitud)
                                    distancia = calcular_distancia(taxis[taxi_seleccionado], posicion_usuario)
                                    user_rep_socket.send_string(f"Taxi {taxi_seleccionado} asignado (distancia: {distancia} unidades)")
                                    registrar_servicio(
                                        data,
                                        taxi_seleccionado,
                                        posicion_usuario,
                                        taxis[taxi_seleccionado],
                                        True
                                    )
                                    
                                    solicitudes.remove(solicitud)
                                    print(f"Servicio asignado exitosamente al taxi {taxi_seleccionado}")
                                except zmq.ZMQError as e:
                                    print(f"Error al comunicarse con el taxi {taxi_seleccionado}: {e}")
                                    user_rep_socket.send_string("Error al asignar taxi, intentando con otro...")
                            
                            else:
                                print("Error al seleccionar taxi")
                                user_rep_socket.send_string("No hay taxis disponibles en este momento")
                        else:
                            print("Error al extraer posición del usuario")
                            user_rep_socket.send_string("Error en el formato de la solicitud")
                    else:
                        print("Timeout de la solicitud")
                        user_rep_socket.send_string("Tiempo de espera agotado")
                else:
                    print("No hay taxis disponibles")
                    user_rep_socket.send_string("No hay taxis disponibles, intente más tarde")

            # Health-check
            if ping_rep_socket in sockets_activados:
                ping_message = ping_rep_socket.recv_string()
                if ping_message == "ping":
                    print("Recibido ping, respondiendo con pong")
                    ping_rep_socket.send_string("pong")

        except zmq.ZMQError as e:
            print(f"Error en la conexión: {e}")
            time.sleep(1)  # Pausa antes de intentar reconectar
            # Intentar reconectar a ambos brokers
            try:
                sub_socket.connect("tcp://localhost:5556")
                sub_socket2.connect("tcp://localhost:5756")
            except zmq.ZMQError:
                print("Error al reconectar a los brokers")

        time.sleep(1)


# Función para manejar los mensajes de los taxis
def manejar_mensaje(socket, taxis, taxis_activos, data, json_file):
    mensaje = socket.recv_string()
    print(f"Recibido mensaje: {mensaje}")
    partes = mensaje.split(maxsplit=2)
    if len(partes) == 3:
        _, id_taxi, posicion = partes  # Usando _ para el tópico que no necesitamos
        id_taxi = int(id_taxi)
        try:
            taxi_posicion = json.loads(posicion)
            taxis[id_taxi] = taxi_posicion
            taxis_activos[id_taxi] = time.time()
            print(f"Taxi {id_taxi} actualizado en posición: {taxi_posicion}")
            guardar_datos_archivo(json_file, data)
        except json.JSONDecodeError as e:
            print(f"Error al decodificar JSON: {e}")

def limpiar_taxis_inactivos(taxis, taxis_activos, timeout=10):
    """
    Elimina los taxis que no han enviado actualización en los últimos 'timeout' segundos
    """
    tiempo_actual = time.time()
    taxis_a_eliminar = []
    
    for taxi_id, ultimo_tiempo in taxis_activos.items():
        if tiempo_actual - ultimo_tiempo > timeout:
            taxis_a_eliminar.append(taxi_id)
    
    for taxi_id in taxis_a_eliminar:
        taxis.pop(taxi_id, None)
        taxis_activos.pop(taxi_id, None)
        print(f"Taxi {taxi_id} eliminado por inactividad")

def calcular_distancia(pos1, pos2):
    """
    Calcula la distancia Manhattan entre dos posiciones
    """
    return abs(pos1['x'] - pos2['x']) + abs(pos1['y'] - pos2['y'])

def extraer_posicion_usuario(solicitud):
    """
    Extrae la posición del usuario de la cadena de solicitud
    Formato esperado: "Usuario {id} en posición ({x},{y}) solicita un taxi"
    """
    try:
        partes = solicitud.split("posición (")[1].split(")")[0].split(",")
        return {
            'x': int(partes[0]),
            'y': int(partes[1])
        }
    except (IndexError, ValueError) as e:
        print(f"Error al extraer posición del usuario: {e}")
        return None

def seleccionar_taxi(taxis, posicion_usuario):
    """
    Selecciona el taxi más cercano a la posición del usuario
    """
    if not taxis:
        return None
        
    distancias = {
        taxi_id: calcular_distancia(posicion, posicion_usuario)
        for taxi_id, posicion in taxis.items()
    }
    
    return min(distancias.items(), key=lambda x: x[1])[0]

if __name__ == "__main__":
    # Argumentos de línea de comando para saber si es réplica o primario
    parser = argparse.ArgumentParser(description="Servidor Central o Réplica")
    parser.add_argument("--replica", action="store_true", help="Iniciar como réplica")
    args = parser.parse_args()

    # Iniciar servidor como primario o réplica
    servidor(is_primary=not args.replica)