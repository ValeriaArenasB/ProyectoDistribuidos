import zmq
import time
import random
import json  

# IP del broker en lugar del servidor central
ip_broker = 'localhost'

def mover_taxi(id_taxi, grid_size, velocidad, max_servicios):
    context = zmq.Context()

    while True:
        try:
            # Publisher para enviar información al Broker
            pub_socket = context.socket(zmq.PUB)
            pub_socket.connect(f"tcp://{ip_broker}:5555")  # Conectar al Broker

            pub_socket2 = context.socket(zmq.PUB)
            pub_socket2.connect(f"tcp://{ip_broker}:5755")  # Conectar al Broker 2 (tolerancia a fallos)

            # Socket REP para recibir servicios
            rep_socket = context.socket(zmq.REP)
            rep_socket.bind(f"tcp://*:556{id_taxi}")  # Cada taxi tiene su propio puerto

            x, y = random.randint(0, grid_size[0] - 1), random.randint(0, grid_size[1] - 1)
            servicios_realizados = 0

            while servicios_realizados < max_servicios:
                # Enviar la posición actual en formato JSON en el tópico `ubicacion_taxi`
                taxi_posicion = {"x": x, "y": y}
                mensaje = json.dumps(taxi_posicion)
                pub_socket.send_string(f"ubicacion_taxi {id_taxi} {mensaje}")
                pub_socket2.send_string(f"ubicacion_taxi {id_taxi} {mensaje}")

                print(f"Enviado a ubicacion_taxi: {id_taxi} {mensaje}")
                
                # Enviar el estado del taxi en el tópico `estado_taxi`
                estado_taxi = {"estado": "disponible"}
                mensaje_estado = json.dumps(estado_taxi)
                pub_socket.send_string(f"estado_taxi {id_taxi} {mensaje_estado}")
                pub_socket2.send_string(f"estado_taxi {id_taxi} {mensaje_estado}")

                print(f"Enviado a estado_taxi: {id_taxi} {mensaje_estado}")

                # Poll para recibir servicios
                poller = zmq.Poller()
                poller.register(rep_socket, zmq.POLLIN)
                socks = dict(poller.poll(1000))  # Esperar hasta 1 segundo

                if socks.get(rep_socket) == zmq.POLLIN:
                    servicio = rep_socket.recv_string()
                    print(f"Recibido servicio: {servicio}")
                    rep_socket.send_string(f"Taxi {id_taxi} aceptando servicio")
                    servicios_realizados += 1
                else:
                    print("No se ha recibido ningún servicio en este ciclo.")

                # Simular movimiento en la grilla
                x, y = mover_taxi_en_grilla(x, y, grid_size, velocidad)
                time.sleep(2)
                
        finally:
            pub_socket.close()
            pub_socket2.close()

            rep_socket.close()
            context.term()

def mover_taxi_en_grilla(x, y, grid_size, velocidad):
    movimiento = random.choice(['vertical', 'horizontal'])
    if movimiento == 'vertical':
        x = max(0, min(x + velocidad, grid_size[0] - 1))
    else:
        y = max(0, min(y + velocidad, grid_size[1] - 1))
    return x, y

if __name__ == "__main__":
    id_taxi = 1  # Identificador del taxi
    grid_size = (10, 10)  # Tamaño de la cuadrícula NxM
    velocidad = 2  # Velocidad del taxi (en km/h)
    max_servicios = 3  # Número máximo de servicios
    mover_taxi(id_taxi, grid_size, velocidad, max_servicios)
