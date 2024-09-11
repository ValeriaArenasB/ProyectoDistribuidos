import zmq
import threading
import random
import time

def usuario(id_usuario, grid_size):
    context = zmq.Context()

    # REQ para solicitar un taxi
    req_socket = context.socket(zmq.REQ)
    req_socket.connect("tcp://localhost:5556")  # El servidor debe bindear en este puerto

    # Posición aleatoria del usuario
    x, y = random.randint(0, grid_size[0] - 1), random.randint(0, grid_size[1] - 1)
    
    # Simular tiempo hasta necesitar un taxi
    tiempo_espera = random.randint(1, 5)  # En segundos para la prueba
    print(f"Usuario {id_usuario} esperando {tiempo_espera} segundos para solicitar un taxi.")
    time.sleep(tiempo_espera)

    # Enviar solicitud de taxi
    req_socket.send_string(f"Usuario {id_usuario} en posición ({x},{y}) solicita un taxi")
    print(f"Usuario {id_usuario} ha solicitado un taxi.")

    # Esperar respuesta del servidor
    respuesta = req_socket.recv_string()
    print(f"Usuario {id_usuario} recibió respuesta: {respuesta}")

    req_socket.close()

def generador_usuarios(num_usuarios, grid_size):
    threads = []
    for i in range(num_usuarios):
        hilo_usuario = threading.Thread(target=usuario, args=(i, grid_size))
        threads.append(hilo_usuario)
        hilo_usuario.start()
    
    # Esperar a que todos los hilos terminen
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    num_usuarios = 5  # Número de usuarios a simular
    grid_size = (10, 10)  # Tamaño de la cuadrícula NxM
    generador_usuarios(num_usuarios, grid_size)
