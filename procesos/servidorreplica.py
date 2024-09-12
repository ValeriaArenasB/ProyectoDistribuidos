import zmq
import threading
import time
import random

# Almacenar el estado recibido desde el servidor principal
estado_recibido = {
    'taxis': {},
    'solicitudes': [],
    'solicitudes_usuarios': {},  # Diccionario vacío para tiempos de solicitudes
    'taxis_activos': {}
}

# Diccionario para almacenar los servicios completados por cada taxi
servicios_completados_por_taxi = {}

def recibir_estado(replica_socket):
    global estado_recibido
    while True:
        estado_recibido = replica_socket.recv_pyobj()  # Recibir el estado como objeto Python
        print("Estado sincronizado recibido:", estado_recibido)

# Función para verificar si el usuario sigue esperando
def user_is_still_waiting(id_usuario, tiempo_espera_maximo=15):
    tiempo_actual = time.time()
    
    # Verificar si 'solicitudes_usuarios' existe y si el usuario está en ella
    if id_usuario in estado_recibido.get('solicitudes_usuarios', {}):
        tiempo_solicitud = estado_recibido['solicitudes_usuarios'][id_usuario]
        if tiempo_actual - tiempo_solicitud > tiempo_espera_maximo:
            print(f"Tiempo de espera excedido para el usuario {id_usuario}.")
            return False
    return True

def asignar_servicios_a_solicitudes():
    solicitudes = estado_recibido['solicitudes']
    taxis = estado_recibido['taxis']
    taxis_activos = estado_recibido['taxis_activos']

    if len(solicitudes) > 0:
        solicitud_actual = solicitudes.pop(0)
        id_usuario = solicitud_actual.split()[1]  # Obtener ID del usuario
        if user_is_still_waiting(id_usuario):
            # Filtrar taxis disponibles (activos)
            taxis_disponibles = [taxi for taxi in taxis if taxis_activos.get(taxi, True)]
            if len(taxis_disponibles) > 0:
                taxi_seleccionado = seleccionar_taxi(taxis_disponibles)
                print(f"Asignando servicio al taxi {taxi_seleccionado} para el usuario {id_usuario}")
                asignar_servicio_taxi(taxi_seleccionado, id_usuario)

                # Registrar el servicio completado por el taxi
                servicios_completados_por_taxi[taxi_seleccionado] = servicios_completados_por_taxi.get(taxi_seleccionado, 0) + 1

                # Si el taxi ha completado 3 servicios, marcarlo como inactivo
                if servicios_completados_por_taxi[taxi_seleccionado] >= 3:
                    print(f"Taxi {taxi_seleccionado} ha completado 3 servicios, marcándolo como inactivo.")
                    taxis_activos[taxi_seleccionado] = False  # Desactivar el taxi
            else:
                print("No hay taxis activos disponibles. Reagendando solicitud.")
                solicitudes.append(solicitud_actual)
        else:
            print(f"El usuario {id_usuario} ya no está esperando. Eliminando la solicitud.")
            if id_usuario in estado_recibido['solicitudes_usuarios']:
                del estado_recibido['solicitudes_usuarios'][id_usuario]

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
        # Asegurarse de que 'solicitudes_usuarios' está inicializado en estado_recibido
        if 'solicitudes_usuarios' not in estado_recibido:
            estado_recibido['solicitudes_usuarios'] = {}

        # Recibir nuevas posiciones de taxis
        if sub_socket.poll(1000):
            mensaje = sub_socket.recv_string()
            print(f"Recibido mensaje: {mensaje}")
            partes = mensaje.split()
            id_taxi = int(partes[1])
            posicion = partes[-1]
            estado_recibido['taxis'][id_taxi] = posicion
            estado_recibido['taxis_activos'][id_taxi] = True

        # Recibir nuevas solicitudes de usuarios
        if user_rep_socket.poll(1000):
            solicitud = user_rep_socket.recv_string()
            print(f"Solicitud recibida en réplica: {solicitud}")
            estado_recibido['solicitudes'].append(solicitud)
            id_usuario = solicitud.split()[1]
            estado_recibido['solicitudes_usuarios'][id_usuario] = time.time()  # Ahora esto debería funcionar correctamente
            user_rep_socket.send_string("Solicitud recibida")

        # Asignar servicios a las solicitudes pendientes
        asignar_servicios_a_solicitudes()

        time.sleep(2)


def health_check(replica_socket, primary_socket_addr):
    context = zmq.Context()
    health_socket = context.socket(zmq.REQ)
    health_socket.connect(primary_socket_addr)
    
    # Incrementar el timeout a 5 segundos
    health_socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5 segundos de espera

    while True:
        try:
            health_socket.send_string("ping")
            respuesta = health_socket.recv_string()
            if respuesta == "pong":
                print("Servidor principal en funcionamiento")
        except zmq.error.Again:  # Si se agota el tiempo sin recibir respuesta
            print("Servidor principal no respondió, activando réplica")
            servidor_replica()  # Llamar al servidor réplica
            break  # Salir del loop una vez que la réplica asuma el control
        except zmq.ZMQError as e:
            print(f"Error de ZMQ: {e}")
            break

        time.sleep(1)  # Verificar cada 2 segundos

if __name__ == "__main__":
    context = zmq.Context()

    # Socket para recibir el estado desde el servidor principal
    replica_socket = context.socket(zmq.PULL)
    replica_socket.bind("tcp://*:5559")  # Puerto en el que la réplica recibe el estado

    # Lanzar el proceso para recibir el estado
    threading.Thread(target=recibir_estado, args=(replica_socket,)).start()

    primary_socket_addr = "tcp://localhost:5558"  # Puerto donde el servidor principal responde pings
    threading.Thread(target=health_check, args=(replica_socket, primary_socket_addr)).start()
