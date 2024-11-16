# broker.py
import zmq
import time

def broker():
    context = zmq.Context()
    
    # Socket para recibir mensajes de los taxis
    frontend = context.socket(zmq.SUB)
    frontend.bind("tcp://*:5555")
    frontend.setsockopt_string(zmq.SUBSCRIBE, "")  # Suscribirse a todos los mensajes
    
    # Socket para reenviar mensajes al servidor
    backend = context.socket(zmq.PUB)
    backend.bind("tcp://*:5556")
    
    print("Broker iniciado - esperando mensajes...")
    zmq.proxy(frontend, backend)
    
    try:
        while True:
            try:
                # Recibir mensaje del taxi
                mensaje = frontend.recv_string(zmq.NOBLOCK)
                print(f"Broker recibió: {mensaje}")
                
                # Reenviar al servidor
                backend.send_string(mensaje)
                print(f"Broker reenvió: {mensaje}")
            except zmq.Again:
                pass  # No hay mensajes disponibles
            
            time.sleep(0.1)  # Pequeña pausa para no saturar el CPU
            
    except KeyboardInterrupt:
        print("Broker terminando...")
    finally:
        frontend.close()
        backend.close()
        context.term()

if __name__ == "__main__":
    broker()
