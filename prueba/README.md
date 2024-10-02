# My-Uber

Proyecto de simulación de un sistema distribuido de transporte similar a Uber, desarrollado como parte del curso de Sistemas Distribuidos. La implementación utiliza tecnologías como **ZeroMQ** para la comunicación entre procesos, y técnicas de **resiliencia y manejo de fallas** para garantizar la continuidad del servicio. 

## Integrantes

- Valeria Arenas
- Juliana Bejarano
- Tatiana Vivas Restrepo

### Profesor
- Osberth De Castro

## Descripción General

El sistema **My-Uber** simula una ciudad representada como una cuadrícula, donde múltiples taxis, manejados como procesos independientes, se mueven dentro de la ciudad y responden a solicitudes de usuarios. El **Servidor Central** coordina estas interacciones, y un **Servidor Réplica** asegura la continuidad del servicio en caso de fallas. El sistema también cuenta con un proceso de **Health-Check** que monitorea el estado del servidor central.

### Componentes Principales

1. **Servidor Central**: Coordina las solicitudes de los usuarios y la asignación de taxis. Funciona como un nodo principal en la arquitectura cliente-servidor.
2. **Servidor Réplica**: Nodo de respaldo que asume el control en caso de que el Servidor Central falle.
3. **Usuarios**: Representados como hilos, envían solicitudes de taxis y esperan la asignación de un taxi.
4. **Taxis**: Procesos independientes que envían actualizaciones de su posición y responden a solicitudes de servicios.
5. **Health-Check**: Un proceso de monitoreo que verifica el estado del Servidor Central y activa el Servidor Réplica en caso de falla.

## Tecnologías Utilizadas

- **ZeroMQ**: Middleware de mensajería utilizado para la comunicación eficiente y segura entre taxis, usuarios y servidores.
- **Python**: Lenguaje utilizado para desarrollar los componentes del sistema.
- **JSON**: Almacenamiento de datos persistente que guarda la información de los servicios de taxis.

## Estructura del Proyecto

El proyecto incluye los siguientes archivos y carpetas:

- [**servidorcentral.py**](./servidorcentral.py): Código para el Servidor Central. 
- [**servidorreplica.py**](./servidorreplica.py): Código para el Servidor Réplica.
- [**taxi1.py**](./taxi1.py) / [**taxi2.py**](./taxi2.py): Códigos que simulan los taxis como procesos independientes.
- [**usuarios.py**](./usuarios.py): Código que simula usuarios enviando solicitudes de taxis.
- [**healthcheck.py**](./healthcheck.py): Código del proceso de monitoreo (Health-Check).
- [**datos_taxis.json**](./datos_taxis.json): Archivo que almacena información sobre las posiciones de los taxis y los servicios completados.
- [**README.md**](./README.md): Archivo de documentación.

