import zmq
import threading
import time

# Almacenar el estado recibido desde el servidor principal
estado_recibido = {
    'taxis': {},
    'solicitudes': []
}

def recibir_estado(replica_socket):
    global estado_recibido
    while True:
        estado_recibido = replica_socket.recv_pyobj()  # Recibir el estado como objeto Python
        print("Estado sincronizado recibido:", estado_recibido)

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

        time.sleep(2)  # Verificar cada 2 segundos


def servidor_replica():
    global estado_recibido  # Asegurar que usamos la variable global
    print("Servidor réplica ha tomado el control")
    taxis = estado_recibido['taxis']
    solicitudes = estado_recibido['solicitudes']
    
    # Continuar el procesamiento de solicitudes y taxis desde el estado sincronizado
    while True:
        if len(solicitudes) > 0:
            solicitud = solicitudes.pop(0)
            print(f"Procesando solicitud: {solicitud}")
            # Aquí puedes procesar la solicitud y asignar taxis con los datos sincronizados.
        
        time.sleep(1)

if __name__ == "__main__":
    context = zmq.Context()

    # Socket para recibir el estado desde el servidor principal
    replica_socket = context.socket(zmq.PULL)
    replica_socket.bind("tcp://*:5559")  # Puerto en el que la réplica recibe el estado

    # Lanzar el proceso para recibir el estado
    threading.Thread(target=recibir_estado, args=(replica_socket,)).start()

    primary_socket_addr = "tcp://localhost:5558"  # Puerto donde el servidor principal responde pings
    threading.Thread(target=health_check, args=(servidor_replica, primary_socket_addr)).start()
