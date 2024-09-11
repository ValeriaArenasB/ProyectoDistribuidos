import zmq
import time
import random

def servidor():
    context = zmq.Context()

    # SUB para recibir posiciones de taxis
    sub_socket = context.socket(zmq.SUB)
    sub_socket.bind(f"tcp://*:5555")  # El servidor bindea al puerto
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

    taxis = {}

    while True:
        # Recibir la posición del taxi
        mensaje = sub_socket.recv_string()
        print(f"Recibido mensaje: {mensaje}")
        partes = mensaje.split()
        id_taxi = int(partes[1])
        posicion = partes[-1]
        taxis[id_taxi] = posicion

        if len(taxis) > 0:
            # Seleccionar un taxi para asignar servicio
            taxi_seleccionado = seleccionar_taxi(taxis)
            print(f"Asignando servicio al taxi {taxi_seleccionado}")

            # Enviar el servicio al taxi
            req_socket = context.socket(zmq.REQ)
            try:
                req_socket.connect(f"tcp://localhost:556{taxi_seleccionado}")
                req_socket.send_string("Servicio asignado")
                respuesta = req_socket.recv_string()
                print(f"Respuesta del taxi {taxi_seleccionado}: {respuesta}")
            except zmq.error.ZMQError as e:
                print(f"Error en la comunicación con el taxi {taxi_seleccionado}: {e}")
            finally:
                req_socket.close()

        time.sleep(1)

def seleccionar_taxi(taxis):
    return random.choice(list(taxis.keys()))

if __name__ == "__main__":
    servidor()
