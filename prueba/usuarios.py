import zmq
import time
import random
import threading

# Diccionario para almacenar el estado de los usuarios (si siguen activos o no)
usuarios_activos = {}
ip_central='10.43.100.106'

# Función para manejar la solicitud de taxi
def solicitar_taxi(req_socket, id_usuario, x, y):
    # Enviar solicitud de taxi
    req_socket.send_string(f"Usuario {id_usuario} en posición ({x},{y}) solicita un taxi")
    print(f"Usuario {id_usuario} ha solicitado un taxi.")
    
    # Medir el tiempo de respuesta
    inicio_respuesta = time.time()

    try:
        # Esperar respuesta del servidor con timeout de 15 segundos
        req_socket.setsockopt(zmq.RCVTIMEO, 15000)
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
        return False  # Indicar que no se recibió respuesta

    return True  # Indicar que se recibió respuesta correctamente


def usuario(id_usuario, x, y, tiempo_espera):
    context = zmq.Context()

    # Intentar primero con el servidor central, luego la réplica
    servidores = [(f"tcp://{ip_central}:5556", "Servidor Central"), (f"tcp://{ip_central}:5557", "Servidor Réplica")]
    
    # Simular tiempo hasta necesitar un taxi
    print(f"Usuario {id_usuario} en posición ({x},{y}) esperando {tiempo_espera} segundos para solicitar un taxi.")
    time.sleep(tiempo_espera)

    # Marcamos al usuario como activo (esperando por un taxi)
    usuarios_activos[id_usuario] = True

    # Probar con ambos servidores (central y réplica)
    for direccion_servidor, nombre_servidor in servidores:
        req_socket = context.socket(zmq.REQ)
        req_socket.connect(direccion_servidor)  # Conectar al servidor

        print(f"Usuario {id_usuario} intentando conectarse a {nombre_servidor} ({direccion_servidor})...")
        
        if solicitar_taxi(req_socket, id_usuario, x, y):
            # Si la solicitud fue exitosa, cerrar socket y salir
            req_socket.close()
            return
        else:
            print(f"Fallo en {nombre_servidor}, intentando con otro servidor...")
            req_socket.close()  # Cerrar socket después de fallo

    print(f"Usuario {id_usuario} no pudo conectarse a ningún servidor.")


# Genera múltiples usuarios con atributos aleatorios
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
    num_usuarios = 3  # Número de usuarios a simular
    grid_size = (10, 10)  # Tamaño de la cuadrícula NxM
    generador_usuarios(num_usuarios, grid_size)
