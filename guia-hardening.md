# Guía de Laboratorio Práctico: Hardening de PostgreSQL y pg_hba.conf en Codespaces (Versión Completa v4)
## Cátedra: Procesamiento de Datos (UCOM)
### Docente: Ing. David Britez

Este manual contiene la documentación técnica, los fundamentos de red de contenedores y el paso a paso final corregido para implementar un **bloqueo perimetral real** en la base de datos central del CPD corporativo.

Aprenderemos a configurar PostgreSQL para que bloquee activamente las conexiones que provienen del host de desarrollo o de contenedores de ataque externos (los cuales ingresan enmascarados a través del NAT de Docker con la IP de la puerta de enlace `172.18.0.1`), mientras permitimos de manera transparente el tráfico transaccional legítimo proveniente de las sucursales de Asunción, CDE, Encarnación y Coronel Oviedo dentro del clúster virtual.

---

## 🔍 1. FUNDAMENTO TEÓRICO Y FÍSICA DE REDES EN DOCKER

### El fenómeno del enmascaramiento IP (NAT)
Cuando levantamos un contenedor temporal "intruso" para realizar un ataque perimetral de red contra nuestra base de datos central (`cpd-matriz-db`), no podemos hacerlo usando directamente el nombre DNS de Docker (`postgres-matriz`) si dicho contenedor no pertenece físicamente a la red privada `red_empresarial`. 

Para simular este ataque, forzamos la conexión redirigiendo la petición a través del puerto expuesto del Host (`5432`) utilizando la pasarela virtual del puente de Docker (`host.docker.internal`).

Al cruzar la frontera de red del host hacia el contenedor, el sistema operativo realiza una traducción de direcciones de red (**NAT - Network Address Translation**). Desde el punto de vista del motor PostgreSQL central, el paquete de red **no proviene de "localhost" ni de la IP del atacante**, sino que entra físicamente con la dirección IP de la puerta de enlace (Gateway) del puente de Docker, la cual es de forma predeterminada la **`172.18.0.1`**.

### El peligro del "Sombreado de Reglas" (Shadowing)
PostgreSQL evalúa las reglas de control de acceso del archivo `pg_hba.conf` de **arriba hacia abajo**, deteniéndose de manera inmediata en la **primera coincidencia** que encuentre. 

Si el archivo de configuración original contiene una regla abierta de red como:
```text
host    all             all             all                     scram-sha-256
```
Cualquier intento de conexión externa (incluyendo al atacante enmascarado en la IP `172.18.0.1`) coincidirá con la palabra clave `all` (que abarca todas las IPs de red). Postgres se detendrá en esa línea, le solicitará la contraseña y le otorgará el acceso, **ignorando por completo cualquier regla de bloqueo o restricción perimetral que hayamos escrito más abajo en el archivo**. 

Por lo tanto, para lograr un **bloqueo real**, es obligatorio **comentar o eliminar la regla abierta por defecto** y declarar las políticas de acceso en un orden jerárquico estricto.

---

## 📁 2. ARCHIVO DE CONFIGURACIÓN `pg_hba.conf` DE LA UCOM

Abre el archivo `pg_hba.conf` en tu editor de **VS Code** y reemplaza todo su bloque de configuración final de red con la siguiente estructura de precisión monocromática:

```text
# ==============================================================================
# REGLAS DE SEGURIDAD PERIMETRAL (HARDENING DE PRECISIÓN) - UCOM
# ==============================================================================
# Este bloque de seguridad gobierna de manera jerárquica el tráfico TCP/IP del CPD.
# Las reglas se evalúan estrictamente de arriba hacia abajo.

# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Regla 1: Permitir conexión local (dentro de la propia consola de la Matriz)
local   all             all                                     trust

# Regla 2: BLOQUEAR explícitamente la IP del Gateway de Docker (172.18.0.1)
# Esto de forma perimetral neutraliza los ataques redirigidos por el Host de Codespaces (localhost)
host    matriz_db       ucom_admin      172.18.0.1/32           reject

# Regla 3: Permitir conexiones transaccionales legítimas de las sucursales
# Se autoriza a todo el rango CIDR de la subred interna del CPD de la UCOM
host    matriz_db       ucom_admin      172.18.0.0/16           scram-sha-256

# Regla 4: Rechazar de forma defensiva cualquier otro tráfico de red no identificado
host    all             all             all                     reject
```

---

## 🛠️ 3. GUÍA DE EJECUCIÓN PASO A PASO EN CODESPACES

Sigue estrictamente esta secuencia de comandos de terminal en tu espacio de trabajo de VS Code para desplegar el clúster, editar la configuración y verificar los bloqueos en caliente.

### Paso 1: Levantar la Infraestructura y Crear las Tablas
Inicializa el clúster transaccional corporativo y asienta la estructura idempotente en la base de datos de Asunción:

```bash
# 1. Levantar el clúster de base de datos en segundo plano
docker compose up -d

# 2. Verificar que los 4 contenedores del CPD estén activos (Up)
docker compose ps

# 3. Inicializar la tabla de ventas unificada de la Casa Matriz
docker exec -i cpd-matriz-db psql -U ucom_admin -d matriz_db < ddl-v3.sql
```

---

### Paso 2: Flujo DevOps para Extraer y Editar `pg_hba.conf`
Dado que la imagen oficial de PostgreSQL no incluye editores nativos (como `nano` o `vim`) para mantener su tamaño ligero y seguro, utilizaremos un flujo de copia bidireccional de Docker para editar el archivo de manera cómoda utilizando la interfaz visual de VS Code:

```bash
# 1. Extraer el archivo pg_hba.conf original del contenedor a tu Codespace local
docker cp cpd-matriz-db:/var/lib/postgresql/data/pg_hba.conf ./pg_hba.conf
```

> **✏️ Instrucción Visual en el Editor:** 
> 1. En el panel izquierdo de VS Code, haz clic sobre el archivo recién copiado `./pg_hba.conf`.
> 2. Desplázate hasta la parte inferior del archivo.
> 3. **Busca la línea abierta original** (`host all all all scram-sha-256`) y desactívala agregando un carácter `#` al inicio.
> 4. Copia y pega las **Reglas de Seguridad Perimetral UCOM** detalladas en la Sección 2 de este manual.
> 5. Guarda el archivo presionando las teclas **`Ctrl + S`** (o `Cmd + S` en Mac). Asegúrate de que el círculo blanco de archivo sin guardar de la pestaña de VS Code desaparezca por completo.

---

### Paso 3: Inyectar el Archivo y Corregir Permisos de Linux (¡Paso Crítico!)
Cuando copiamos archivos desde el Host hacia un contenedor de Docker, el archivo hereda los identificadores de usuario del Host (`UID 1000`), bloqueando el acceso al motor de Postgres (`UID 999`) por un fallo de permisos de Linux. 

Debemos reasignar el dueño del archivo y limitar los permisos de lectura/escritura de manera obligatoria antes de recargar la configuración, o de lo contrario Postgres abortará silenciosamente la actualización y seguirá usando las reglas antiguas inseguras:

```bash
# 1. Devolver el archivo pg_hba.conf editado al directorio de datos del contenedor
docker cp ./pg_hba.conf cpd-matriz-db:/var/lib/postgresql/data/pg_hba.conf

# 2. Cambiar el propietario del archivo dentro del contenedor al usuario del sistema "postgres"
docker exec -u root cpd-matriz-db chown postgres:postgres /var/lib/postgresql/data/pg_hba.conf

# 3. Asignar permisos chmod 600 (lectura y escritura exclusiva para el dueño) para seguridad interna
docker exec -u root cpd-matriz-db chmod 600 /var/lib/postgresql/data/pg_hba.conf
```

---

### Paso 4: Aplicar la Recarga en Caliente de Políticas de Red
Ordenamos al motor PostgreSQL que relea el archivo `pg_hba.conf` en memoria en caliente sin apagar el clúster ni reiniciar el servicio de facturación:

```bash
docker exec -it cpd-matriz-db psql -U ucom_admin -d matriz_db -c "SELECT pg_reload_conf();"
```

**Resultado esperado en la consola:**
```text
 pg_reload_conf 
----------------
 t
(1 row)
```

---

### Paso 5: Auditar el Estado de las Reglas Activas en Memoria
Para garantizar que el motor PostgreSQL haya asimilado correctamente nuestras directivas de seguridad sin toparse con fallos de sintaxis o denegaciones de lectura, consultamos de forma científica la tabla del sistema `pg_hba_file_rules`:

```bash
docker exec -it cpd-matriz-db psql -U ucom_admin -d matriz_db -c "SELECT line_number, type, database, user_name, address, auth_method, error FROM pg_hba_file_rules;"
```

**Salida exitosa requerida para la aprobación de la práctica:**
Debe listarse la tabla de reglas activa en memoria. Comprueba visualmente que la columna **`error`** de todas las líneas esté completamente **vacía (en blanco)** y que la regla abierta de la línea 100 haya sido desactivada (notarás que tus reglas perimetrales aparecerán al final con números de línea cercanos al 110-120 dependiendo del largo del archivo):

```text
 line_number | type  |   database    |  user_name   |  address   |  auth_method  | error 
-------------+-------+---------------+--------------+------------+---------------+-------
          89 | local | {all}         | {all}        |            | trust         | 
          91 | host  | {all}         | {all}        | 127.0.0.1  | trust         | 
          93 | host  | {all}         | {all}        | ::1        | trust         | 
          96 | local | {replication} | {all}        |            | trust         | 
          97 | host  | {replication} | {all}        | 127.0.0.1  | trust         | 
          98 | host  | {replication} | {all}        | ::1        | trust         | 
         110 | local | {all}         | {all}        |            | trust         | 
         114 | host  | {matriz_db}   | {ucom_admin} | 172.18.0.1 | reject        | 
         118 | host  | {matriz_db}   | {ucom_admin} | 172.18.0.0 | scram-sha-256 | 
         121 | host  | {all}         | {all}        | all        | reject        | 
(10 rows)
```

---

## 🧪 4. PRUEBAS DE ESTRÉS Y CIBERSEGURIDAD APLICADA

### Prueba A: Simulación de Ataque Perimetral Externo
Corremos un contenedor temporal suelto fuera de la red interna corporativa (`red_empresarial`) y forzamos una conexión remota utilizando el direccionamiento del host. El sistema debe denegar de forma inmediata el handshake TCP/IP sin solicitar credenciales:

```bash
docker run --rm -it --add-host=host.docker.internal:host-gateway postgres:15-alpine psql -h host.docker.internal -p 5432 -U ucom_admin -d matriz_db
```

**Resultado de seguridad esperado (Intrusión bloqueada con éxito):**
```text
psql: error: connection to server at "host.docker.internal" (172.17.0.1), port 5432 failed: FATAL:  pg_hba.conf rejects connection for host "172.18.0.1", user "ucom_admin", database "matriz_db", no encryption
```
*¡Excelente! El motor central identificó de manera correcta la firma IP del host (172.18.0.1), hizo coincidir la petición con la Regla de Bloqueo de tu `pg_hba.conf` y expulsó al atacante de inmediato.*

---

### Prueba B: La Falla de Ejecución del Script (Efecto Pedagógico)
Para comprender a fondo la seguridad perimetral, forzaremos una ejecución del script de integración de Python tal como viene por defecto (buscando `localhost` en el puerto `5432`). 

Ejecuta el script desde la terminal principal de tu Codespace:

```bash
# 1. Instalar dependencias en el Host de Codespaces (si no se hizo antes)
pip install pandas psycopg2-binary

# 2. Correr la simulación transaccional distribuida desde el Host externo
python3 importar_ventas_v3.py
```

**Resultado de seguridad esperado (¡Rechazo Seguro del Script!):**
El script de automatización fallará de inmediato al intentar inyectar las ventas remotas de las sucursales:

```text
🚀 INICIANDO SIMULACIÓN DE CONEXIÓN REMOTA MULTI-SUCURSAL (CASA MATRIZ)...
==========================================================================================
📋 Cargados los primeros 9 registros de ventas para la simulación.

[CONEXIÓN REMOTA: SUCURSAL_ASUNCION ➔ CASA MATRIZ]
   ↳ Detalles: Factura: 536366 | Item: HAND WARMER UNION JACK | Cantidad: 6 | Precio: L 1.85
   🔌 Conectándose remotamente al puerto 5432 de la Casa Matriz...
   ❌ [FALLO] No se pudo asentar la transacción de Sucursal_Asuncion.
      Detalle técnico: connection to server at "localhost" (::1), port 5432 failed: FATAL:  pg_hba.conf rejects connection for host "172.18.0.1", user "ucom_admin", database "matriz_db", no encryption
```

*   **¿Por qué ocurre este fallo?**  
    El script de Python corre sobre el Host de Codespaces y busca `localhost:5432`. El tráfico es redirigido por Docker al contenedor central. Al entrar al contenedor, se realiza un proceso de NAT que enmascara el origen con la IP del Gateway del Host (**`172.18.0.1`**). Como tu regla de hardening prohíbe de forma explícita el tráfico de la IP `.1/32` con un `reject`, el motor Postgres intercepta la transacción de Python y le deniega el acceso. ¡La base de datos central de Asunción está a salvo de accesos del Host de desarrollo!

---

### Prueba C: Despliegue de la Simulación en la Red Segura (Solución Definitiva)
Para solucionar el fallo de la Prueba B, debemos hacer que el script de automatización de ventas corra **dentro del entorno de red segura del CPD** (`proyecto-cpd_red_empresarial`) para que la base de datos lo reconozca como un servicio legítimo de sucursal con una IP interna en el rango `172.18.0.0/16`.

#### **Paso 1: Modificar el host en el Script `importar_ventas_v3.py`**
Abre el archivo `importar_ventas_v3.py` en tu panel de VS Code. Busca el bloque de configuración de base de datos (`DB_CONFIG`) alrededor de la línea 13 y cambia el parámetro `"host"` para usar el DNS interno del contenedor central en vez de localhost:

```python
# Modificación en 'importar_ventas_v3.py' en VS Code:
DB_CONFIG = {
    "host": "postgres-matriz",  # <--- CAMBIAR de 'localhost' a 'postgres-matriz'
    "port": "5432",
    "database": "matriz_db",
    "user": "ucom_admin",
    "password": "password_matriz"
}
```
*Guarda el archivo en el editor presionando **`Ctrl + S`**.*

#### **Paso 2: Correr el simulador en la red interna del CPD**
Ahora, ejecutaremos un contenedor de Python temporal de usar y tirar (`--rm`) acoplado directamente a la red empresarial, montando la carpeta del proyecto y corriendo el script desde el espacio interno:

```bash
docker run --rm -it --network proyecto-cpd_red_empresarial -v "$PWD":/usr/src/app -w /usr/src/app python:3.10-slim sh -c "pip install pandas psycopg2-binary && python importar_ventas_v3.py"
```

*(Nota: Si al ejecutar te dice que la red no existe, puedes listar tus redes de Docker usando `docker network ls` para confirmar si se llama `proyecto-cpd_red_empresarial` o `proyecto_red_empresarial` y ajustar la directiva `--network`).*

**Resultado de integración esperado (¡Conexión Remota Exitosa!):**
Verás pasar la inyección de ventas transaccionales desde las sucursales legítimas en tiempo real y con éxito rotundo:

```text
🚀 INICIANDO SIMULACIÓN DE CONEXIÓN REMOTA MULTI-SUCURSAL (CASA MATRIZ)...
==========================================================================================
📋 Cargados los primeros 9 registros de ventas para la simulación.

[CONEXIÓN REMOTA: SUCURSAL_CDE ➔ CASA MATRIZ]
   ↳ Detalles: Factura: 536365 | Item: WHITE HANGING HEART T-LIGHT HOLDER | Cantidad: 6 | Precio: L 2.55
   🔌 Conectándose remotamente al puerto 5432 de la Casa Matriz...
   ✅ [ÉXITO] Registro asentado correctamente en la tabla centralizada de Asunción.
------------------------------------------------------------------------------------------
[CONEXIÓN REMOTA: SUCURSAL_ENC ➔ CASA MATRIZ]
   ↳ Detalles: Factura: 536365 | Item: WHITE METAL LANTERN | Cantidad: 6 | Precio: L 3.39
   🔌 Conectándose remotamente al puerto 5432 de la Casa Matriz...
   ✅ [ÉXITO] Registro asentado correctamente en la tabla centralizada de Asunción.
```

#### **Paso 3: Validar la Consistencia de Datos en Asunción**
Una vez finalizada la inyección, realizamos una consulta interactiva a la base de datos centralizada de Asunción para verificar la persistencia y autoría de los registros consolidados por sucursal:

```bash
docker exec -it cpd-matriz-db psql -U ucom_admin -d matriz_db -c "SELECT id, invoice_no, quantity, sucursal, insertado_en FROM ventas_locales ORDER BY id;"
```

---

### Paso 6: Liberación segura de recursos de la nube
Para finalizar el laboratorio de forma limpia y ordenada, detenemos la infraestructura virtual para liberar memoria en nuestro Codespace de GitHub:

```bash
docker compose down
```

---

## 📊 5. CRITERIOS DE EVALUACIÓN DE LABORATORIO (RÚBRICA)

Para obtener la calificación completa del trabajo práctico, el alumno deberá presentar ante el docente su consola de Codespaces activa mostrando los siguientes puntos auditados en vivo:

1.  **[1 Pto]** Orquestación exitosa con Compose (`docker compose ps` mostrando los 4 nodos en estado `Up`).
2.  **[1 Pto]** Edición y personalización correctas del archivo `pg_hba.conf` comentando la regla abierta por defecto.
3.  **[1 Pto]** Ejecución correcta del flujo DevOps `docker cp` bidireccional.
4.  **[2 Ptos]** Declaración correcta de los permisos de Linux del archivo en el contenedor (`chown postgres` y `chmod 600`).
5.  **[1 Pto]** Demostración de la consulta de auditoría SQL (`SELECT ... FROM pg_hba_file_rules;` con la columna `error` vacía y el ruteo perimetral activo).
6.  **[1 Pto]** Demostración del fallo didáctico controlado ejecutando el script nativo de Python en el Host.
7.  **[1 Pto]** Demostración en vivo del ataque denegado del contenedor intruso externo (`pg_hba.conf rejects connection...`).
8.  **[2 Ptos]** Demostración del procesamiento transaccional libre de bloqueos corriendo la automatización dentro de la red del CPD con Docker.
