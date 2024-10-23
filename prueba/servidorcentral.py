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
    sub_socket2.setsockopt_string(zmq.SUBSCRIBE, "ubicacion_taxi")  # Suscribirse al tópico de posiciones

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

    while True:
        try:
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
                solicitudes.append(solicitud)

                user_id = solicitud.split()[1]
                solicitudes_timeout[user_id] = time.time() + 15  # Timeout de 15 segundos

                if len(taxis) > 0:
                    if user_is_still_waiting(solicitud, solicitudes_timeout):
                        taxi_seleccionado = seleccionar_taxi(taxis)
                        print(f"Asignando servicio al taxi {taxi_seleccionado}")

                        taxi_req_socket.connect(f"tcp://{taxi_ip}:556{taxi_seleccionado}")
                        taxi_req_socket.send_string("Servicio asignado")
                        respuesta = taxi_req_socket.recv_string()
                        print(f"Respuesta del taxi {taxi_seleccionado}: {respuesta}")
                        taxi_req_socket.disconnect(f"tcp://{taxi_ip}:556{taxi_seleccionado}")

                        solicitudes.remove(solicitud)
                        user_rep_socket.send_string(f"Taxi {taxi_seleccionado} asignado")
                    else:
                        print("No hay taxis disponibles")
                        user_rep_socket.send_string("No hay taxis disponibles")
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
            sub_socket.connect("tcp://localhost:5556")
            sub_socket2.connect("tcp://localhost:5756")

        time.sleep(1)


# Función para manejar los mensajes de los taxis
def manejar_mensaje(socket, taxis, taxis_activos, data, json_file):
    mensaje = socket.recv_string()
    print(f"Recibido mensaje: {mensaje}")
    partes = mensaje.split(maxsplit=2)
    if len(partes) == 3:
        id_taxi = int(partes[1])
        posicion = partes[2]
        try:
            taxi_posicion = json.loads(posicion)
            taxis[id_taxi] = taxi_posicion
            taxis_activos[id_taxi] = True
            guardar_datos_archivo(json_file, data)
        except json.JSONDecodeError as e:
            print(f"Error al decodificar JSON: {e}")



def seleccionar_taxi(taxis):
    return random.choice(list(taxis.keys()))

if __name__ == "__main__":
    # Argumentos de línea de comando para saber si es réplica o primario
    parser = argparse.ArgumentParser(description="Servidor Central o Réplica")
    parser.add_argument("--replica", action="store_true", help="Iniciar como réplica")
    args = parser.parse_args()

    # Iniciar servidor como primario o réplica
    servidor(is_primary=not args.replica)