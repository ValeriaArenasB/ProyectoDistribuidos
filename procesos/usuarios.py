import zmq
import time
import random
import threading

# Diccionario para almacenar el estado de los usuarios (si siguen activos o no)
usuarios_activos = {}

def usuario(id_usuario, x, y, tiempo_espera):
    context = zmq.Context()

    # REQ para solicitar un taxi
    req_socket = context.socket(zmq.REQ)
    req_socket.connect("tcp://localhost:5556")  # El servidor debe bindear en este puerto

    # Simular tiempo hasta necesitar un taxi
    print(f"Usuario {id_usuario} en posición ({x},{y}) esperando {tiempo_espera} segundos para solicitar un taxi.")
    time.sleep(tiempo_espera)

    # Enviar solicitud de taxi
    req_socket.send_string(f"Usuario {id_usuario} en posición ({x},{y}) solicita un taxi")
    print(f"Usuario {id_usuario} ha solicitado un taxi.")
    
    # Marcamos al usuario como activo (esperando por un taxi)
    usuarios_activos[id_usuario] = True

    # Medir el tiempo de respuesta
    inicio_respuesta = time.time()

    try:
        # Esperar respuesta del servidor con timeout de 10 segundos
        req_socket.setsockopt(zmq.RCVTIMEO, 15000)  # 15 segundos de timeout
        respuesta = req_socket.recv_string()
        fin_respuesta = time.time()

        tiempo_respuesta = fin_respuesta - inicio_respuesta
        print(f"Usuario {id_usuario} recibió respuesta: {respuesta} en {tiempo_respuesta:.2f} segundos")

        # Eliminar al usuario de los activos (ha sido atendido)
        usuarios_activos[id_usuario] = False

    except zmq.error.Again:
        # Si no se recibe respuesta a tiempo, el usuario se va a otro proveedor
        print(f"Usuario {id_usuario} no recibió respuesta, se va a otro proveedor")
        usuarios_activos[id_usuario] = False  # Marca al usuario como inactivo (timeout)

    req_socket.close()


# esto genera 5 usuarios con atributos al azar. no se si toque especificar cuales usuarios mas adelante
def generador_usuarios(num_usuarios, grid_size):
    threads = []
    for i in range(num_usuarios):
        # Generar posiciones aleatorias para los usuarios
        x, y = random.randint(0, grid_size[0] - 1), random.randint(0, grid_size[1] - 1)
        tiempo_espera = random.randint(1, 5)  # Tiempo en segundos para simular minutos
        hilo_usuario = threading.Thread(target=usuario, args=(i, x, y, tiempo_espera))
        threads.append(hilo_usuario)
        hilo_usuario.start()

    # Esperar a que todos los hilos terminen
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    num_usuarios = 5  # Número de usuarios a simular
    grid_size = (10, 10)  # Tamaño de la cuadrícula NxM
    generador_usuarios(num_usuarios, grid_size)


