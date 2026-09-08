# Guía Técnica: Hardening del CPD en Rama 'hardening' (Clase 9)
## Cátedra: Procesamiento de Datos — UCOM
### Docente: Ing. David Britez

Esta guía te guiará paso a paso para implementar el **hardening de infraestructura, límites de hardware y balanceo de carga** en tu Centro de Procesamiento de Datos (CPD) virtual. 

Para trabajar de manera profesional sin alterar tu rama principal estable (`main`), realizaremos todo el trabajo dentro de una nueva rama de Git llamada **`hardening`**.

---

## 🛠️ PASO 0: CREAR Y TRABAJAR EN LA RAMA `hardening`

Antes de editar cualquier archivo, abre tu terminal en VS Code y crea una nueva rama independiente para aislar tus experimentos de seguridad:

```bash
# 1. Asegúrate de estar en la rama main y tener el estado limpio
git checkout main
git pull origin main

# 2. Crea y salta a la nueva rama 'hardening'
git checkout -b hardening

# 3. Comprueba que estás parado en la rama correcta
git branch
```

*Verás un asterisco verde al lado de la palabra `* hardening`, lo que confirma que todo tu trabajo ahora se guardará de forma segura en este espacio aislado.*

---

## 🐳 PASO 1: REFACTORIZACIÓN COMPLETA DE `compose.yaml`

Modificaremos nuestro `compose.yaml` original para aplicar tres capas de endurecimiento (hardening) de producción:
1. **Gobernanza Física (cgroups v2):** Límites de CPU y RAM para evitar saturación de hardware.
2. **Seguridad Perimetral (Hiding Ports):** Retiramos el puerto público `5432` del contenedor de la matriz, blindándolo dentro de la red privada `red_empresarial`.
3. **Criptografía (Secrets):** Inyectamos la contraseña desde un canal temporal en RAM volátil (`tmpfs`) eliminando las credenciales expuestas en texto plano.

Abre tu archivo `compose.yaml` en VS Code y reemplaza todo su contenido con este bloque unificado y corregido de nivel de ingeniería:

```yaml
version: '3.8'

services:
  # ==========================================================
  # NODO MATRIZ (ASUNCIÓN) - TOTALMENTE BLINDADO
  # ==========================================================
  postgres-matriz:
    image: postgres:15-alpine
    container_name: cpd-matriz-db
    networks:
      - red_empresarial
    # Omitimos 'ports' para que nadie en el Host ni fuera de la red privada pueda escanear o atacar este puerto.
    environment:
      POSTGRES_DB: matriz_db
      POSTGRES_USER: ucom_admin
      # postgres oficial lee el secret montado en memoria temporal RAM (tmpfs)
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - datos_matriz:/var/lib/postgresql/data
    secrets:
      - db_password
    # Gobernanza Cgroups v2: límites físicos de silicio
    deploy:
      resources:
        limits:
          cpus: '0.50'        # Máximo 50% de un núcleo de CPU
          memory: 512M        # Evita consumos mayores a 512 Megabytes de RAM
        reservations:
          memory: 256M        # Reserva mínima de 256 MB de RAM garantizada

  # ==========================================================
  # NODO SUCURSAL A (CIUDAD DEL ESTE)
  # ==========================================================
  postgres-sucursal-a:
    image: postgres:15-alpine
    container_name: cpd-sucursala-db
    networks:
      - red_empresarial
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: sucursal_a_db
      POSTGRES_USER: ucom_admin
      POSTGRES_PASSWORD: password_sucursal_a
    volumes:
      - datos_sucursal_a:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '0.25'        # Límite estricto de 255% de CPU
          memory: 256M        # Máximo de 256 MB de RAM
        reservations:
          memory: 128M        # Garantía mínima de 128 MB

  # ==========================================================
  # NODO SUCURSAL B (ENCARNACIÓN)
  # ==========================================================
  postgres-sucursal-b:
    image: postgres:15-alpine
    container_name: cpd-sucursalb-db
    networks:
      - red_empresarial
    ports:
      - "5434:5432"
    environment:
      POSTGRES_DB: sucursal_b_db
      POSTGRES_USER: ucom_admin
      POSTGRES_PASSWORD: password_sucursal_b
    volumes:
      - datos_sucursal_b:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M
        reservations:
          memory: 128M

  # ==========================================================
  # NODO SUCURSAL C (CORONEL OVIEDO)
  # ==========================================================
  postgres-sucursal-c:
    image: postgres:15-alpine
    container_name: cpd-sucursalc-db
    networks:
      - red_empresarial
    ports:
      - "5435:5432"
    environment:
      POSTGRES_DB: sucursal_c_db
      POSTGRES_USER: ucom_admin
      POSTGRES_PASSWORD: password_sucursal_c
    volumes:
      - datos_sucursal_c:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M
        reservations:
          memory: 128M

  # ==========================================================
  # BALANCEADOR DE CARGA TCP (HA-PROXY CAPA 4 EN EL BORDE)
  # ==========================================================
  cpd-balanceador:
    image: haproxy:2.8-alpine
    container_name: cpd-balanceador
    ports:
      - "5432:5432"          # Único puerto expuesto en el host para canalizar el tráfico a la Matriz
    networks:
      - red_empresarial
    volumes:
      - ./balanceador/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
    depends_on:
      - postgres-matriz

# Definición de la Red y Sistemas de Almacenamiento Lógicos
networks:
  red_empresarial:
    driver: bridge

volumes:
  datos_matriz:
  datos_sucursal_a:
  datos_sucursal_b:
  datos_sucursal_c:

# Declaración del Secret local
secrets:
  db_password:
    file: ./db_password.txt
```

---

## 🔒 PASO 2: CREACIÓN DE ARCHIVOS DE CREDENCIALES Y SEGURIDAD (.gitignore)

1. Crea un archivo llamado exactamente **`db_password.txt`** en la raíz de tu proyecto e ingresa el valor de la contraseña sin espacios ni saltos de línea:
   ```text
   password_matriz
   ```

2. Abre tu archivo **`.gitignore`** de la raíz del proyecto y añade las exclusiones obligatorias de desarrollo. Esto evitará que subas accidentalmente las contraseñas físicas o los binarios locales de la base de datos a tu repositorio público de GitHub:
   ```text
   almacenamiento/
   db_password.txt
   .env
   ```

---

## 📁 PASO 3: CONFIGURACIÓN ABSTRACTA DEL SCRIPT (.env & python)

Siguiendo el principio arquitectónico de desacoplamiento de configuraciones y código (*Twelve-Factor App*), separaremos las IPs y parámetros lógicos del código fuente utilizando variables de entorno externas.

1. Crea un archivo en tu editor llamado **`.env`** en la raíz del proyecto:
   ```text
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=matriz_db
   DB_USER=ucom_admin
   ```

2. Abre tu script **`importar_ventas_v3.py`** y modifícalo para que consuma estas variables desde el sistema de archivos del sistema operativo usando la librería `os` de Python, en lugar de tenerlas hardcoded:

```python
import os
import time
import random
import pandas as pd
import psycopg2

# Configuración única y abstracta recuperada del archivo .env
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "matriz_db"),
    "user": os.getenv("DB_USER", "ucom_admin"),
    "password": os.getenv("DB_PASSWORD", "password_matriz")  # Inyectada dinámicamente
}

SUCURSALES_DISPLAY = {
    "Sucursal_Asuncion": {"color": "\033[93m"},
    "Sucursal_CDE": {"color": "\033[96m"},
    "Sucursal_ENC": {"color": "\033[92m"},
    "Sucursal_COV": {"color": "\033[94m"}
}
RESET_COLOR = "\033[0m"

def ejecutar_simulacion_centralizada(ruta_csv):
    print("🚀 INICIANDO SIMULACIÓN DE CONEXIÓN REMOTA ABSTRACTA (RAMA HARDENING)...")
    print("==========================================================================================")
    
    if not os.path.exists(ruta_csv):
        print(f"❌ Error: No se encuentra el archivo '{ruta_csv}'.")
        return
        
    df = pd.read_csv(ruta_csv)
    df_simulacion = df.head(9).copy()
    lista_sucursales = list(SUCURSALES_DISPLAY.keys())
    
    for idx, row in df_simulacion.iterrows():
        sucursal_elegida = random.choice(lista_sucursales)
        color = SUCURSALES_DISPLAY[sucursal_elegida]["color"]
        desc = row["Description"] if not pd.isnull(row["Description"]) else "Sin descripción"
        cust_id = str(row["CustomerID"]).replace(".0", "") if not pd.isnull(row["CustomerID"]) else None
        
        print(f"{color}[CONEXIÓN REMOTA: {sucursal_elegida.upper()} ➔ CASA MATRIZ]{RESET_COLOR}")
        print(f"   🔌 Conectándose dinámicamente a {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        
        try:
            conn = psycopg2.connect(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                database=DB_CONFIG["database"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                connect_timeout=3
            )
            cursor = conn.cursor()
            
            query = """
                INSERT INTO ventas_locales (invoice_no, stock_code, description, quantity, invoice_date, unit_price, customer_id, sucursal)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """
            cursor.execute(query, (
                str(row["InvoiceNo"]),
                str(row["StockCode"]),
                desc,
                int(row["Quantity"]),
                row["InvoiceDate"],
                float(row["UnitPrice"]),
                cust_id,
                sucursal_elegida
            ))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"   ✅ \033[92m[ÉXITO]\033[0m Venta asentada correctamente en la base de datos central.")
        except Exception as e:
            print(f"   ❌ [FALLO] No se pudo asentar la transacción.")
            print(f"      Detalle técnico: {e}")
            
        print("-" * 90)
        time.sleep(2)
        
    print("\n🏁 SIMULACIÓN FINALIZADA.")

if __name__ == "__main__":
    ejecutar_simulacion_centralizada("ventas_muestra.csv")
```

---

## 🌐 PASO 4: CONFIGURACIÓN DEL BALANCEADOR DE CARGA TCP (haproxy.cfg)

Crea una carpeta llamada **`balanceador`** en la raíz de tu proyecto, y dentro de ella, un archivo de texto plano llamado **`haproxy.cfg`**:

```text
global
    log stdout format raw local0

defaults
    log     global
    mode    tcp                # Operamos en Capa 4 (Sockets TCP directos para BD)
    timeout connect 5s
    timeout client  30s
    timeout server  30s

# Front-End: Puerto perimetral por donde ingresan las peticiones
frontend db_gateway
    bind *:5432                # Escucha peticiones TCP en el puerto 5432
    default_backend db_cluster

# Back-End: Servidor interno blindado al que se redirigen las peticiones
backend db_cluster
    mode tcp
    balance roundrobin         # Distribución por turnos lógicos
    option pgsql-check user ucom_admin
    server nodo_central postgres-matriz:5432 check
```

---

## 🧪 PASO 5: ORQUESTACIÓN, DESPLIEGUE Y SUBIDA DE LA RAMA

Con toda la arquitectura modelada, levantaremos la infraestructura optimizada y guardaremos los cambios de seguridad dentro de nuestra rama de Git:

```bash
# 1. Apagar clústeres obsoletos para liberar puertos
docker compose down

# 2. Iniciar la infraestructura blindada en segundo plano
docker compose up -d

# 3. Comprobar que los 5 servicios corren de forma estable
docker compose ps

# 4. Inyectar el esquema SQL a la Matriz (La petición fluye a través del balanceador)
docker exec -i cpd-matriz-db psql -U ucom_admin -d matriz_db < ddl-v3.sql

# 5. Ejecutar el script Python (conéctandose de forma segura a localhost:5432)
python3 importar_ventas_v3.py

# 6. Sube los cambios y tu nueva rama 'hardening' a GitHub
git add .
git commit -m "Fase 4: Hardening de compose.yaml, gobernanza cgroups v2, inyección de Secrets y Balanceador TCP"
git push origin hardening
```

*Al realizar el push final, verás que la rama se crea de manera remota en GitHub. Esto le permitirá al docente auditar de forma limpia y por separado tus habilidades técnicas de seguridad perimetral.*
