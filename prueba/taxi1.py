import zmq
import time
import random
import json

# IP del broker
ip_broker = 'localhost'

def mover_taxi(id_taxi, grid_size, velocidad, max_servicios):
    context = zmq.Context()
    
    # Publisher para enviar información a los Brokers
    pub_socket = context.socket(zmq.PUB)
    pub_socket2 = context.socket(zmq.PUB)
    
    try:
        # Conectar a ambos brokers
        pub_socket.connect(f"tcp://{ip_broker}:5555")
        pub_socket2.connect(f"tcp://{ip_broker}:5755")
        
        # Socket REP para recibir servicios
        rep_socket = context.socket(zmq.REP)
        rep_socket.bind(f"tcp://*:556{id_taxi}")
        
        print(f"Taxi {id_taxi} iniciado y conectado a los brokers")
        
        x, y = random.randint(0, grid_size[0] - 1), random.randint(0, grid_size[1] - 1)
        servicios_realizados = 0
        
        while servicios_realizados < max_servicios:
            # Enviar la posición actual
            taxi_posicion = {"x": x, "y": y}
            mensaje = json.dumps(taxi_posicion)
            
            # Enviar a ambos brokers
            pub_socket.send_string(f"ubicacion_taxi {id_taxi} {mensaje}")
            pub_socket2.send_string(f"ubicacion_taxi {id_taxi} {mensaje}")
            
            print(f"Taxi {id_taxi} enviando posición: ({x}, {y})")
            
            # Poll para recibir servicios
            poller = zmq.Poller()
            poller.register(rep_socket, zmq.POLLIN)
            
            # Esperar hasta 1 segundo por solicitudes de servicio
            socks = dict(poller.poll(1000))
            
            if rep_socket in socks:
                servicio = rep_socket.recv_string()
                print(f"Taxi {id_taxi} recibió servicio: {servicio}")
                rep_socket.send_string(f"Taxi {id_taxi} aceptando servicio")
                servicios_realizados += 1
            
            # Simular movimiento
            x, y = mover_taxi_en_grilla(x, y, grid_size, velocidad)
            time.sleep(1)  # Enviar actualización cada segundo
            
    except Exception as e:
        print(f"Error en taxi {id_taxi}: {e}")
    finally:
        print(f"Taxi {id_taxi} cerrando conexiones")
        pub_socket.close()
        pub_socket2.close()
        rep_socket.close()
        context.term()

def mover_taxi_en_grilla(x, y, grid_size, velocidad):
    direccion = random.choice(['norte', 'sur', 'este', 'oeste'])
    
    if direccion == 'norte' and y < grid_size[1] - velocidad:
        y += velocidad
    elif direccion == 'sur' and y >= velocidad:
        y -= velocidad
    elif direccion == 'este' and x < grid_size[0] - velocidad:
        x += velocidad
    elif direccion == 'oeste' and x >= velocidad:
        x -= velocidad
    
    return x, y

if __name__ == "__main__":
    # Configuración del taxi
    id_taxi = 1 
    grid_size = (10, 10)
    velocidad = 1
    max_servicios = 10
    
    print(f"Iniciando taxi {id_taxi}")
    mover_taxi(id_taxi, grid_size, velocidad, max_servicios)