import zmq
import time
import random
import threading

# Diccionario que almacena el estado de las solicitudes de usuarios: {usuario_id: tiempo_solicitud}
solicitudes_usuarios = {}

def sincronizar_estado(replica_socket, taxis, solicitudes):
    while True:
        estado = {
            'taxis': taxis,
            'solicitudes': solicitudes
        }
        replica_socket.send_pyobj(estado)  # Enviar el estado como objeto Python serializado
        time.sleep(5)  # Sincronizar cada 5 segundos

# Verificar si el usuario aún está esperando respuesta
def user_is_still_waiting(id_usuario, tiempo_espera_maximo=10):
    tiempo_actual = time.time()
    if id_usuario in solicitudes_usuarios:
        tiempo_solicitud = solicitudes_usuarios[id_usuario]
        if tiempo_actual - tiempo_solicitud > tiempo_espera_maximo:
            print(f"Tiempo de espera excedido para el usuario {id_usuario}.")
            return False
    return True

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

    # Lanzar hilo de sincronización de estado
    threading.Thread(target=sincronizar_estado, args=(replica_socket, taxis, solicitudes)).start()

    while True:
        # Recibir posiciones de taxis
        if sub_socket.poll(1000):  # Tiempo de espera para recibir posiciones
            mensaje = sub_socket.recv_string()
            print(f"Recibido mensaje: {mensaje}")
            partes = mensaje.split()
            id_taxi = int(partes[1])
            posicion = partes[-1]
            taxis[id_taxi] = posicion

        # Recibir solicitudes de usuarios
        if user_rep_socket.poll(1000):  # Tiempo de espera para solicitudes de usuario
            solicitud = user_rep_socket.recv_string()
            print(f"Solicitud recibida: {solicitud}")
            
            id_usuario = solicitud.split()[1]
            solicitudes_usuarios[id_usuario] = time.time()  # Almacenar el tiempo en que la solicitud se hizo
            
            # Verificar si hay taxis disponibles
            if len(taxis) > 0:
                if user_is_still_waiting(id_usuario):
                    taxi_seleccionado = seleccionar_taxi(taxis)
                    print(f"Asignando servicio al taxi {taxi_seleccionado}")

                    # Conectar al taxi seleccionado
                    taxi_req_socket.connect(f"tcp://localhost:556{taxi_seleccionado}")
                    taxi_req_socket.send_string("Servicio asignado")
                    respuesta = taxi_req_socket.recv_string()
                    print(f"Respuesta del taxi {taxi_seleccionado}: {respuesta}")
                    taxi_req_socket.disconnect(f"tcp://localhost:556{taxi_seleccionado}")  # Desconectar después del uso

                    # Enviar la confirmación al usuario
                    user_rep_socket.send_string(f"Taxi {taxi_seleccionado} asignado")
                else:
                    print(f"Usuario {id_usuario} ya no está esperando, eliminando la solicitud.")
                    if id_usuario in solicitudes_usuarios:
                        del solicitudes_usuarios[id_usuario]

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
