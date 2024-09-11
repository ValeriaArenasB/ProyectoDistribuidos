# este es el publisher. cada taxi MANDA su posicion al servidor

import zmq
import time
import random

# Función que genera las posiciones de los taxis
def mover_taxi(id_taxi, grid_size, velocidad, max_servicios):
    # Iniciar ZeroMQ como publisher
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(f"tcp://*:555{id_taxi}")  # Asignar un puerto único a cada taxi

    # Posición inicial aleatoria dentro de la cuadrícula
    x, y = random.randint(0, grid_size[0]-1), random.randint(0, grid_size[1]-1)
    servicios_realizados = 0

    while servicios_realizados < max_servicios:
        # Enviar la posición del taxi
        mensaje = f"Taxi {id_taxi} en posición ({x},{y})"
        socket.send_string(mensaje)
        print(mensaje)

        # Simular el movimiento del taxi en la cuadrícula
        x, y = mover_taxi_en_grilla(x, y, grid_size, velocidad)

        # Simular tiempo entre movimientos (cada 30 minutos simulados)
        time.sleep(30)  # 30 segundos = 30 minutos simulados
        
        # ***** Aquí puedes agregar la lógica de los servicios (cuando el taxi recibe una asignación) *****

        servicios_realizados += 1

    # Desconectar ZeroMQ
    socket.close()
    context.term()



# Función para mover el taxi
def mover_taxi_en_grilla(x, y, grid_size, velocidad):
    movimiento = random.choice(['vertical', 'horizontal'])
    if movimiento == 'vertical':
        x = max(0, min(x + velocidad, grid_size[0]-1))
    else:
        y = max(0, min(y + velocidad, grid_size[1]-1))
    return x, y


if __name__ == "__main__":
    id_taxi = 1  # Identificador del taxi
    grid_size = (10, 10)  # Tamaño de la cuadrícula NxM
    velocidad = 2  # Velocidad del taxi (en km/h)
    max_servicios = 3  # Número máximo de servicios
    mover_taxi(id_taxi, grid_size, velocidad, max_servicios) # aqui mando solo un taxi con esas caracteristicas. esto se hace despues por cada cliente taxi
