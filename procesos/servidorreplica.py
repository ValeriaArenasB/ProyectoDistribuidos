import zmq
import threading
import time
import random
import json
import os

# Archivo JSON donde guardaremos los datos
ARCHIVO_DATOS = "datos_taxis.json"

# Función para cargar los datos actuales desde el archivo JSON
def cargar_datos():
    if os.path.exists(ARCHIVO_DATOS):
        with open(ARCHIVO_DATOS, 'r') as archivo:
            return json.load(archivo)
    else:
        return {"taxis": {}, "servicios_exitosos": 0, "servicios_fallidos": 0}

# Función para guardar los datos en el archivo JSON
def guardar_datos(datos):
    with open(ARCHIVO_DATOS, 'w') as archivo:
        json.dump(datos, archivo, indent=4)

# Función para registrar el estado de un taxi
def registrar_taxi(taxi_id, posicion):
    datos = cargar_datos()
    if taxi_id not in datos['taxis']:
        datos['taxis'][taxi_id] = {
            "posiciones": [],
            "servicios_realizados": 0
        }
    datos['taxis'][taxi_id]["posiciones"].append(posicion)
    guardar_datos(datos)

# Función para registrar un servicio exitoso
def registrar_servicio_exitoso(taxi_id, posicion_usuario):
    datos = cargar_datos()
    datos['taxis'][taxi_id]["servicios_realizados"] += 1
    datos['servicios_exitosos'] += 1
    guardar_datos(datos)

# Función para registrar un servicio fallido
def registrar_servicio_fallido():
    datos = cargar_datos()
    datos['servicios_fallidos'] += 1
    guardar_datos(datos)

# Almacenar el estado recibido desde el servidor principal
estado_recibido = {
    'taxis': {},
    'solicitudes': [],
    'solicitudes_resueltas': [],  # Diccionario para solicitudes ya resueltas
    'taxis_activos': {}
}

def recibir_estado(replica_socket):
    global estado_recibido
    while True:
        estado_recibido = replica_socket.recv_pyobj()  # Recibir el estado como objeto Python
        print("Estado sincronizado recibido:", estado_recibido)

# Función para verificar si el usuario sigue esperando
def user_is_still_waiting(id_usuario, tiempo_espera_maximo=15):
    tiempo_actual = time.time()

    if id_usuario in estado_recibido.get('solicitudes_usuarios', {}):
        tiempo_solicitud = estado_recibido['solicitudes_usuarios'][id_usuario]
        if tiempo_actual - tiempo_solicitud > tiempo_espera_maximo:
            print(f"Tiempo de espera excedido para el usuario {id_usuario}.")
            return False
    return True

def servidor_replica():
    global estado_recibido
    print("Servidor réplica ha tomado el control")

    context = zmq.Context()
    user_rep_socket = context.socket(zmq.REP)
    user_rep_socket.bind(f"tcp://*:5556")  # Escuchar nuevas solicitudes de usuarios

    sub_socket = context.socket(zmq.SUB)
    sub_socket.bind(f"tcp://*:5555")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Escuchar posiciones de taxis

    while True:
        taxis = estado_recibido['taxis']
        solicitudes = estado_recibido['solicitudes']
        solicitudes_resueltas = estado_recibido['solicitudes_resueltas']
        taxis_activos = estado_recibido['taxis_activos']

        # Procesar solicitudes existentes
        for solicitud in solicitudes[:]:
            if solicitud not in solicitudes_resueltas:  # Solo procesar si no está resuelta
                id_usuario = solicitud.split()[1]

                if user_is_still_waiting(id_usuario):
                    taxis_disponibles = [taxi for taxi in taxis if taxis_activos.get(taxi, True)]
                    if len(taxis_disponibles) > 0:
                        taxi_seleccionado = seleccionar_taxi(taxis_disponibles)
                        print(f"Asignando servicio al taxi {taxi_seleccionado} para el usuario {id_usuario}")
                        asignar_servicio_taxi(taxi_seleccionado, id_usuario)
                        solicitudes_resueltas.append(solicitud)  # Marcar como resuelta

                        # Registrar el servicio en el archivo JSON
                        registrar_servicio_exitoso(taxi_seleccionado, solicitud)
                    else:
                        print(f"No hay taxis activos disponibles. Reagendando solicitud.")
                else:
                    print(f"Usuario {id_usuario} ya no está esperando, eliminando la solicitud.")
                    solicitudes.remove(solicitud)

        # Recibir nuevas posiciones de taxis
        if sub_socket.poll(1000):
            mensaje = sub_socket.recv_string()
            print(f"Recibido mensaje: {mensaje}")
            partes = mensaje.split()
            id_taxi = int(partes[1])
            posicion = partes[-1]
            taxis[id_taxi] = posicion
            taxis_activos[id_taxi] = True

            # Registrar la posición del taxi en el archivo JSON
            registrar_taxi(id_taxi, posicion)

        # Recibir nuevas solicitudes de usuarios
        if user_rep_socket.poll(1000):
            solicitud = user_rep_socket.recv_string()
            print(f"Solicitud recibida en réplica: {solicitud}")
            solicitudes.append(solicitud)
            user_rep_socket.send_string("Solicitud recibida")  # Confirmar recepción de solicitud

        time.sleep(2)

def seleccionar_taxi(taxis_disponibles):
    return random.choice(taxis_disponibles)

def asignar_servicio_taxi(taxi_id, usuario_id):
    """Función para manejar la conexión con el taxi y asignarle el servicio"""
    context = zmq.Context()
    taxi_req_socket = context.socket(zmq.REQ)

    try:
        taxi_req_socket.connect(f"tcp://localhost:556{taxi_id}")
        taxi_req_socket.send_string(f"Servicio asignado al usuario {usuario_id}")
        respuesta = taxi_req_socket.recv_string()
        print(f"Respuesta del taxi {taxi_id}: {respuesta}")
    finally:
        taxi_req_socket.disconnect(f"tcp://localhost:556{taxi_id}")
        taxi_req_socket.close()

def health_check(replica_socket, primary_socket_addr):
    context = zmq.Context()
    health_socket = context.socket(zmq.REQ)
    health_socket.connect(primary_socket_addr)

    health_socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5 segundos de espera

    while True:
        try:
            health_socket.send_string("ping")
            respuesta = health_socket.recv_string()
            if respuesta == "pong":
                print("Servidor principal en funcionamiento")
        except zmq.error.Again:
            print("Servidor principal no respondió, activando réplica")
            servidor_replica()
            break
        except zmq.ZMQError as e:
            print(f"Error de ZMQ: {e}")
            break

        time.sleep(1)

if __name__ == "__main__":
    context = zmq.Context()

    # Socket para recibir el estado desde el servidor principal
    replica_socket = context.socket(zmq.PULL)
    replica_socket.bind("tcp://*:5559")  # Puerto en el que la réplica recibe el estado

    # Lanzar el proceso para recibir el estado
    threading.Thread(target=recibir_estado, args=(replica_socket,)).start()

    primary_socket_addr = "tcp://localhost:5558"  # Puerto donde el servidor principal responde pings
    threading.Thread(target=health_check, args=(replica_socket, primary_socket_addr)).start()
