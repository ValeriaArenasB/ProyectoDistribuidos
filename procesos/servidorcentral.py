# subscriber que escucha a los taxis y recoge sus posiciones. también seleccionará un taxi aleatorio por ahora para asignarle un servicio.
import zmq
import time

# Función para manejar la recepción de posiciones de los taxis
def servidor():
    context = zmq.Context()
    
    # Crear socket como suscriptor (Subscriber)
    socket = context.socket(zmq.SUB)
    for id_taxi in range(1, 5):  # Suscribirse a múltiples taxis (ejemplo con 4 taxis)
        socket.connect(f"tcp://localhost:555{id_taxi}")
    
    socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Escuchar todos los mensajes

    print("Servidor escuchando a los taxis...")
    
    taxis = {}

    while True:
        # Recibir posición del taxi
        mensaje = socket.recv_string()
        print(f"Recibido: {mensaje}")

        # Extraer ID y posición del taxi
        partes = mensaje.split()
        id_taxi = int(partes[1])
        posicion = partes[-1]

        # Actualizar la posición del taxi en el servidor
        taxis[id_taxi] = posicion

        # ****** Aquí puedes agregar la lógica para asignar servicios

        if len(taxis) > 1:  # Simular que luego de recibir múltiples posiciones asigna un servicio
            taxi_seleccionado = seleccionar_taxi(taxis)
            print(f"Servicio asignado al taxi {taxi_seleccionado}")

        # Simular tiempo de espera
        time.sleep(1)

# Función para seleccionar el taxi para un servicio
def seleccionar_taxi(taxis):
    # Aquí puedes agregar la lógica para seleccionar el taxi más cercano
    return random.choice(list(taxis.keys()))

if __name__ == "__main__":
    servidor()
