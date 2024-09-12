import zmq
import time
import random
import threading

# Almacenar las solicitudes resueltas
solicitudes_resueltas = []

def sincronizar_estado(replica_socket, taxis, solicitudes, taxis_activos, solicitudes_resueltas):
    while True:
        estado = {
            'taxis': taxis,
            'solicitudes': solicitudes,
            'solicitudes_resueltas': solicitudes_resueltas,  # Sincroniza las solicitudes resueltas
            'taxis_activos': taxis_activos
        }
        replica_socket.send_pyobj(estado)  # Enviar el estado como objeto Python serializado
        time.sleep(3)  # Sincronizar cada 3 segundos


def user_is_still_waiting(solicitud, solicitudes_timeout):
    user_id = solicitud.split()[1]  # Extraer el ID del usuario de la solicitud
    current_time = time.time()

    if user_id in solicitudes_timeout and current_time > solicitudes_timeout[user_id]:
        return False  # El usuario ya no está esperando
    return True  # El usuario aún está esperando


def servidor():
    context = zmq.Context()

    # SUB para recibir posiciones de taxis
    sub_socket = context.socket(zmq.SUB)
    sub_socket.bind(f"tcp://*:5555")  # El servidor bindea al puerto
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    # REP para recibir solicitudes de usuarios
    user_rep_socket = context.socket(zmq.REP)
    user_rep_socket.bind(f"tcp://*:5556")  # El servidor bindea a este puerto para usuarios

    # REQ para enviar servicios a los taxis
    taxi_req_socket = context.socket(zmq.REQ)  # Socket de solicitud para taxis

    # REP para el ping/pong health-check
    ping_rep_socket = context.socket(zmq.REP)
    ping_rep_socket.bind(f"tcp://*:5558")  # El puerto donde el servidor responde pings

    # Socket para sincronizar el estado con la réplica
    replica_socket = context.socket(zmq.PUSH)
    replica_socket.connect("tcp://localhost:5559")  # La réplica escucha en este puerto

    taxis = {}
    solicitudes = []
    taxis_activos = {}  # Diccionario para gestionar el estado de taxis activos
    global solicitudes_timeout
    solicitudes_timeout = {}  # Diccionario para registrar el timeout de cada solicitud

    # Lanzar hilo de sincronización de estado con taxis_activos y solicitudes_resueltas
    threading.Thread(target=sincronizar_estado, args=(replica_socket, taxis, solicitudes, taxis_activos, solicitudes_resueltas)).start()

    while True:
        # Recibir posiciones de taxis
        if sub_socket.poll(1000):  # Tiempo de espera para recibir posiciones
            mensaje = sub_socket.recv_string()
            print(f"Recibido mensaje: {mensaje}")
            partes = mensaje.split()
            id_taxi = int(partes[1])
            posicion = partes[-1]
            taxis[id_taxi] = posicion
            taxis_activos[id_taxi] = True  # Marcar el taxi como activo

        # Recibir solicitudes de usuarios
        if user_rep_socket.poll(1000):  # Tiempo de espera para solicitudes de usuario
            solicitud = user_rep_socket.recv_string()
            print(f"Solicitud recibida: {solicitud}")
            solicitudes.append(solicitud)  # Añadir la solicitud a la lista

            # Registrar el tiempo en que expira el timeout para esta solicitud
            user_id = solicitud.split()[1]
            solicitudes_timeout[user_id] = time.time() + 15  # Timeout de 15 segundos para cada solicitud

            # Verificar si hay taxis disponibles
            if len(taxis) > 0:

                if user_is_still_waiting(solicitud, solicitudes_timeout):
                    # Seleccionar cualquier taxi disponible
                    taxi_seleccionado = seleccionar_taxi(taxis)
                    print(f"Asignando servicio al taxi {taxi_seleccionado}")

                    # Conectar al taxi seleccionado
                    taxi_req_socket.connect(f"tcp://localhost:556{taxi_seleccionado}")
                    taxi_req_socket.send_string("Servicio asignado")
                    respuesta = taxi_req_socket.recv_string()
                    print(f"Respuesta del taxi {taxi_seleccionado}: {respuesta}")
                    taxi_req_socket.disconnect(f"tcp://localhost:556{taxi_seleccionado}")  # Desconectar después del uso

                    # Eliminar la solicitud después de asignarla
                    solicitudes.remove(solicitud)
                    solicitudes_resueltas.append(solicitud)  # Marcar la solicitud como resuelta

                    # Enviar la confirmación al usuario
                    user_rep_socket.send_string(f"Taxi {taxi_seleccionado} asignado")
                else:
                    print(f"Usuario ya no está esperando, eliminando la solicitud.")
                    solicitudes.remove(solicitud)
                    user_rep_socket.send_string("Usuario ya no está esperando.")
            else:
                print("No hay taxis disponibles")
                user_rep_socket.send_string("No hay taxis disponibles, intente más tarde")

        # Manejar el health-check (ping/pong)
        if ping_rep_socket.poll(1000):  # Verifica si se recibe un ping
            ping_message = ping_rep_socket.recv_string()
            if ping_message == "ping":
                print("Recibido ping, respondiendo con pong")
                ping_rep_socket.send_string("pong")

        time.sleep(1)

def seleccionar_taxi(taxis):
    return random.choice(list(taxis.keys()))

if __name__ == "__main__":
    servidor()
