import zmq
import time

def health_check(replica_ip="192.168.1.2", primary_socket_addr="tcp://localhost:5558"):
    context = zmq.Context()

    def create_socket():
        """Crea un socket REQ con el timeout apropiado."""
        sock = context.socket(zmq.REQ)
        sock.connect(primary_socket_addr)
        sock.setsockopt(zmq.RCVTIMEO, 5000)  # 5 segundos de espera
        return sock

    while True:
        retry_attempts = 3
        success = False

        for attempt in range(retry_attempts):
            health_socket = create_socket()  # Crear un nuevo socket para cada intento
            try:
                print("Enviando ping al servidor principal...")
                health_socket.send_string("ping")
                respuesta = health_socket.recv_string()
                print(f"Respuesta recibida: {respuesta}")
                if respuesta == "pong":
                    print("Servidor principal en funcionamiento")
                    success = True
                    break  # Salir del bucle de reintentos si hay éxito
            except zmq.error.Again:
                print(f"Intento {attempt + 1} fallido. Reintentando...")
                # Si es el último intento fallido, activa la réplica
                if attempt == retry_attempts - 1:
                    print("Servidor principal no respondió después de varios intentos, enviando señal a la réplica")
                    ping_replica_to_activate(replica_ip)
            except zmq.ZMQError as e:
                print(f"Error de ZMQ: {e}")
            finally:
                health_socket.close()

            time.sleep(1)  # Esperar antes del siguiente intento

        if success:
            time.sleep(1)
        else:
            break

def ping_replica_to_activate(replica_ip):
    """Envía un ping de activación a la réplica."""
    context = zmq.Context()
    activate_socket = context.socket(zmq.REQ)
    replica_ping_port = "5561"  # Puerto específico para ping de activación

    # Conectar al socket de activación de la réplica
    activate_socket.connect(f"tcp://{replica_ip}:{replica_ping_port}")
    
    # Enviar el ping de activación
    print("Enviando ping a la réplica para activación...")
    activate_socket.send_string("ACTIVATE")
    response = activate_socket.recv_string()
    print(f"Respuesta de la réplica: {response}")
    activate_socket.close()

if __name__ == "__main__":
    health_check(replica_ip="192.168.1.2")
