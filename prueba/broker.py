# broker.py
import zmq

def broker():
    context = zmq.Context()
    frontend = context.socket(zmq.XSUB)
    frontend.bind("tcp://*:5555")  # Publicadores (taxis) se conectan aquí

    backend = context.socket(zmq.XPUB)
    backend.bind("tcp://*:5556")  # Suscriptores (servidores) se conectan aquí

    zmq.proxy(frontend, backend)  # Manejo del tráfico

    frontend.close()
    backend.close()
    context.term()

if __name__ == "__main__":
    broker()
