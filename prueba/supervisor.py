import subprocess
import time
import os
import signal

#Verificar si Broker ya está corriendo usando pgrep
def broker_esta_corriendo():
    try:
        # Utilizamos el comando pgrep para buscar el proceso broker.py
        resultado = subprocess.run(['pgrep', '-f', 'broker.py'], stdout=subprocess.PIPE)
        if resultado.stdout:  # Si stdout tiene datos, significa que el broker está corriendo
            pid = int(resultado.stdout.decode().strip())
            print(f"El Broker ya está corriendo con PID: {pid}")
            return pid
        else:
            return None
    except Exception as e:
        print(f"Error al verificar si el Broker está corriendo: {e}")
        return None

def iniciar_broker():
    print("Iniciando el Broker...")
    broker_proceso = subprocess.Popen(['python', 'broker.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return broker_proceso

#Verificar si un proceso con PID específico sigue corriendo
def verificar_broker_por_pid(pid):
    try:
        # Verificamos si el proceso con el PID existe
        os.kill(pid, 0)  # Señal 0 no mata el proceso, solo verifica si existe
        return True
    except OSError:
        return False

def supervisor_broker():
    #Función que supervisa el Broker y lo reinicia si se cae
    broker_pid = broker_esta_corriendo()  # Verificar si ya está corriendo
    broker_proceso = None

    if broker_pid:
        print(f"Supervisando el Broker existente con PID {broker_pid}")
    else:
        # Si el Broker no está corriendo se inicia
        broker_proceso = iniciar_broker()

    while True:
        if broker_proceso:
            # Si iniciamos el Broker desde el supervisor, verificar usando `poll()`
            if broker_proceso.poll() is not None:  # Si poll() devuelve algo distinto de None, el proceso terminó
                print("El Broker ha fallado. Reiniciando...")
                broker_proceso = iniciar_broker()
            else:
                print("El Broker está funcionando correctamente (iniciado por supervisor).")
        else:
            if not verificar_broker_por_pid(broker_pid):
                print("El Broker existente ha fallado. Reiniciando...")
                broker_proceso = iniciar_broker()

        time.sleep(3) #cambiar por sincronizacion si hace falta

if __name__ == "__main__":
    supervisor_broker()
