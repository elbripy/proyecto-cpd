# Guía Práctica de Laboratorio: Telemetría Transaccional y Observabilidad (Clase 11 - Versión v3)
## Cátedra: Procesamiento de Datos — UCOM
### Docente: Ing. David Britez

Este manual contiene el paso a paso detallado y corregido para avanzar con la **Fase 5 del Proyecto Integrador** en tu entorno de **GitHub Codespaces**. 

Aprenderemos a dotar de "ojos" a nuestro Centro de Procesamiento de Datos (CPD) corporativo mediante una arquitectura de **Observabilidad y Telemetría**. Configuraremos **Prometheus** (Base de Datos de Series Temporales - TSDB) y **Grafana** (plataforma de visualización gráfica) para capturar en tiempo real el tráfico de transacciones de cada sucursal física.

En esta versión, adaptamos de forma definitiva nuestro simulador de Python para procesar el dataset gigante de producción **`online_retail_II.csv`** (824,364 filas) resolviendo los cambios estructurales de columnas, y documentamos las soluciones de red a los errores de conectividad más comunes en entornos en la nube.

---

## 🛠️ PASO 1: RAMIFICACIÓN E HERENCIA DE SEGURIDAD (`git checkout`)

Para mantener las mejores prácticas de la ingeniería de software (*GitFlow*), la nueva rama de telemetría debe heredar directamente de la rama **`hardening`**. Esto nos garantiza que Prometheus y Grafana monitoreen un sistema real blindado con secretos en memoria RAM (`tmpfs`), limitación de hardware de CPU/RAM (`cgroups v2`) y balanceador de carga TCP (HA-Proxy).

Abre tu terminal integrada de VS Code y ejecuta exactamente esta secuencia de comandos:

```bash
# 1. Asegurar que estamos en la raíz del proyecto
cd /workspaces/proyecto-cpd

# 2. Situarse en la rama de hardening donde dejamos los cambios estables de seguridad
git checkout hardening

# 3. Descargar cualquier cambio o actualización remota de esa rama
git pull origin hardening

# 4. Crear y saltar a la nueva rama de trabajo llamada "monitoring"
git checkout -b monitoring

# 5. Confirmar que estás parado sobre la rama correcta
git branch
```

---

## 📁 PASO 2: EL SIMULADOR DE PRODUCCIÓN (`importar_ventas_v4.py`)

El dataset masivo **`online_retail_II.csv`** posee variaciones en el nombre y tipo de sus columnas respecto a nuestras muestras controladas de prueba. Utilizaremos **Pandas** para procesar la información de forma eficiente y la biblioteca oficial **`prometheus_client`** para exponer métricas en el puerto **`8000`** en un hilo paralelo.

### 🔍 Mapeo del Esquema de Datos Real:
*   `InvoiceNo` pasa a ser **`Invoice`** (identificador de factura).
*   `UnitPrice` pasa a ser **`Price`** (precio unitario de venta).
*   `CustomerID` se lee de forma segura como un entero, gestionando los valores nulos (`NaN`) para evitar excepciones.

Crea o reemplaza el archivo **`importar_ventas_v4.py`** en la raíz de tu proyecto con el siguiente código completo de producción:

```python
# importar_ventas_v4.py
# Simulador Transaccional de Escala de Producción con Exportador de Métricas Nativo
# Cátedra: Procesamiento de Datos - UCOM
# Docente: Ing. David Britez

import os
import time
import random
import pandas as pd
import psycopg2
# Importamos los componentes oficiales de instrumentación de Prometheus
from prometheus_client import start_http_server, Counter, Histogram

# ==============================================================================
# INSTRUMENTACIÓN DE TELEMETRÍA (MÉTRICAS PERSONALIZADAS)
# ==============================================================================
# 1. Contador para la cantidad total de facturas asentadas con éxito o fallo
METRICA_VENTAS_TOTAL = Counter(
    "cpd_ventas_procesadas_total",
    "Cantidad total de facturas de venta registradas de manera exitosa",
    ["sucursal", "estado"]  # Etiquetas (labels) de filtrado dinámico en Grafana
)

# 2. Contador para acumular el volumen de dinero facturado (Métrica de RED)
METRICA_MONTO_TOTAL = Counter(
    "cpd_monto_facturado_total",
    "Volumen monetario acumulado de transacciones comerciales exitosas",
    ["sucursal"]
)

# 3. Histograma para auditar la latencia de red e inserción física en PostgreSQL
METRICA_LATENCIA_TRANSACCION = Histogram(
    "cpd_latencia_transaccion_segundos",
    "Tiempo de respuesta de la inserción SQL a través del balanceador",
    ["sucursal"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0) # Segmentos de tiempo para medir cuellos de botella
)

# Configuración de base de datos abstracta utilizando variables del .env
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"), # Apunta a nuestro balanceador perimetral HA-Proxy
    "database": os.getenv("DB_NAME", "matriz_db"),
    "user": os.getenv("DB_USER", "ucom_admin"),
    "password": os.getenv("DB_PASSWORD", "password_matriz")
}

SUCURSALES_DISPLAY = {
    "Sucursal_Asuncion": {"color": "\033[93m"}, # Amarillo
    "Sucursal_CDE": {"color": "\033[96m"},      # Cian
    "Sucursal_ENC": {"color": "\033[92m"},      # Verde
    "Sucursal_COV": {"color": "\033[94m"}       # Azul
}
RESET_COLOR = "\033[0m"

def ejecutar_simulacion_produccion():
    # 1. Detectar archivo de datos (Programación Defensiva)
    ruta_dataset = "online_retail_II.csv"
    ruta_backup = "ventas_muestra.csv"
    
    if os.path.exists(ruta_dataset):
        print(f"🔥 [OK] Dataset de producción pesado localizado: '{ruta_dataset}'")
        archivo_a_leer = ruta_dataset
    elif os.path.exists(ruta_backup):
        print(f"⚠️ [AVISO] Dataset de producción no encontrado. Usando archivo de respaldo: '{ruta_backup}'")
        archivo_a_leer = ruta_backup
    else:
        print("❌ [FALLO] No se localizó ningún archivo de ventas para procesar en el directorio.")
        return

    # 2. Levantar el servidor de métricas de Prometheus en el puerto 8000
    # Forzamos addr='0.0.0.0' para abrir el puerto en todas las interfaces de red del contenedor/Codespace
    start_http_server(8000, addr='0.0.0.0')
    print("📊 [TELEMETRÍA] Exportador HTTP iniciado. Métricas listas en http://localhost:8000/metrics")
    print("🔌 Conectándose dinámicamente al CPD a través del balanceador...")

    # 3. Cargar datos usando Pandas optimizado en tipos de datos
    df = pd.read_csv(archivo_a_leer, dtype={
        "Invoice": str,
        "StockCode": str,
        "Description": str,
        "Country": str
    })
    print(f"📋 Cargados {len(df)} registros listos para la simulación transaccional continua.\n")
    
    lista_sucursales = list(SUCURSALES_DISPLAY.keys())

    # Procesar transacciones secuencialmente con retraso controlado
    try:
        for idx, row in df.iterrows():
            sucursal_elegida = random.choice(lista_sucursales)
            color = SUCURSALES_DISPLAY[sucursal_elegida]["color"]
            
            # Mapeo exacto según el df.info() de online_retail_II.csv
            factura_id = str(row["Invoice"])
            stock_code = str(row["StockCode"])
            desc = row["Description"] if not pd.isnull(row["Description"]) else "Facturación de Sucursal"
            
            # Saneamiento del identificador de cliente
            if pd.isnull(row["CustomerID"]):
                cust_id = "Consumidor Final"
            else:
                cust_id = str(int(row["CustomerID"])) # Evita flotantes feos de Pandas como 12345.0
                
            cantidad = int(row["Quantity"])
            precio_unitario = float(row["Price"])
            monto_venta = cantidad * precio_unitario
            
            # Saltamos transacciones de devoluciones o ajustes negativos
            if monto_venta <= 0:
                continue

            print(f"{color}[CONEXIÓN REMOTA: {sucursal_elegida.upper()} ➔ CPD CENTRAL]{RESET_COLOR}")
            print(f"   🧾 Factura: {factura_id} | Cliente: {cust_id} | Total: Gs. {monto_venta:,.2f}")
            
            # Guardamos la marca de tiempo de inicio
            tiempo_inicio = time.time()
            
            try:
                # Intento de conexión TCP al balanceador de carga del clúster central
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
                    factura_id,
                    stock_code,
                    desc,
                    cantidad,
                    row["InvoiceDate"],
                    precio_unitario,
                    cust_id,
                    sucursal_elegida
                ))
                conn.commit()
                cursor.close()
                conn.close()
                
                # Calcular latencia de extremo a extremo
                latencia = time.time() - tiempo_inicio
                print(f"   ✅ [ÉXITO] Transacción registrada de forma consistente en {latencia:.4f}s.")
                
                # ==================================================================
                # REGISTRO DE MÉTRICAS EN CALIENTE EN EL EXPORTADOR
                # ==================================================================
                METRICA_VENTAS_TOTAL.labels(sucursal=sucursal_elegida, estado="exito").inc()
                METRICA_MONTO_TOTAL.labels(sucursal=sucursal_elegida).inc(monto_venta)
                METRICA_LATENCIA_TRANSACCION.labels(sucursal=sucursal_elegida).observe(latencia)

            except Exception as e:
                # En caso de caída de la red, firewall o saturación de base de datos
                latencia = time.time() - tiempo_inicio
                print(f"   ❌ [FALLO DE CONEXIÓN] La sucursal no pudo comunicarse con el host central.")
                print(f"      Detalle del error: {e}")
                
                # Registramos el fallo en telemetría para alertar al operador
                METRICA_VENTAS_TOTAL.labels(sucursal=sucursal_elegida, estado="fallo").inc()
                METRICA_LATENCIA_TRANSACCION.labels(sucursal=sucursal_elegida).observe(latencia)
                
            print("-" * 90)
            # Retraso didáctico para permitir ver pasar los datos dinámicos en Grafana
            time.sleep(1.5)
            
    except KeyboardInterrupt:
        print("\n🛑 Simulación detenida de forma segura por el operador.")

if __name__ == "__main__":
    ejecutar_simulacion_produccion()
```

---

## 📁 PASO 3: CONFIGURACIÓN DE PROMETHEUS (`monitoreo/prometheus.yml`)

Crearemos la estructura para Prometheus y le definiremos de manera específica dónde buscar las métricas. 

En entornos en la nube como Codespaces, la dirección IP que mapea al Host suele ser la **`172.18.0.1`** (la puerta de enlace de nuestra red segura de contenedores) o el puente interno **`host.docker.internal`**. Declararemos las reglas para que Prometheus recopile información de ambas de forma robusta.

Crea una carpeta llamada **`monitoreo`** en la raíz de tu proyecto, y dentro de ella un archivo de configuración de texto llamado **`prometheus.yml`**:

```yaml
# monitoreo/prometheus.yml
# Configuración global del motor de Telemetría del CPD de la UCOM

global:
  scrape_interval: 5s     # Intervalo de raspado rápido de métricas para laboratorios de clase
  evaluation_interval: 5s # Evaluación de expresiones matemáticas en caliente

scrape_configs:
  # 1. Monitoreo del propio motor de Prometheus
  - job_name: 'prometheus_sistema'
    static_configs:
      - targets: ['localhost:9090']

  # 2. Raspado de las métricas de las sucursales (Script de Python)
  - job_name: 'simulador_ventas'
    static_configs:
      # Apuntamos explícitamente a la IP del Gateway de la subred de Codespaces
      - targets: ['172.18.0.1:8000', 'host.docker.internal:8000']
```

---

## 🛠️ PASO 4: ORQUESTACIÓN COMPLETA DEL CPD CON TELEMETRÍA (`compose.yaml`)

Editaremos el archivo de orquestación central **`compose.yaml`** para inyectar los dos nuevos contenedores (`prometheus` y `grafana`) de manera unificada a nuestra red privada, asignándoles volúmenes persistentes dedicados y mapeos de puertos seguros.

Abre tu archivo `compose.yaml` en VS Code, limpia su contenido, y pega esta definición completa:

```yaml
services:
  # ==========================================================
  # NODO MATRIZ (ASUNCIÓN) - BLINDADO SIN PUERTOS EXPUESTOS
  # ==========================================================
  postgres-matriz:
    image: postgres:15-alpine
    container_name: cpd-matriz-db
    environment:
      POSTGRES_DB: matriz_db
      POSTGRES_USER: ucom_admin
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    networks:
      - red_empresarial
    volumes:
      - datos_matriz:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
        reservations:
          memory: 256M

  # ==========================================================
  # RED DE BORDE: BALANCEADOR DE CARGA TCP (HA-PROXY)
  # ==========================================================
  cpd-balanceador:
    image: haproxy:2.8-alpine
    container_name: cpd-balanceador
    ports:
      - "5432:5432" # Unico puerto de base de datos expuesto de cara al Host
    networks:
      - red_empresarial
    volumes:
      - ./balanceador/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
    depends_on:
      - postgres-matriz

  # ==========================================================
  # TELEMETRÍA: PROMETHEUS (TSDB)
  # ==========================================================
  prometheus:
    image: prom/prometheus:v2.45.0
    container_name: cpd-prometheus
    ports:
      - "9090:9090" # Exponemos la consola web de Prometheus
    networks:
      - red_empresarial
    volumes:
      - ./monitoreo/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - datos_prometheus:/prometheus
    extra_hosts:
      - "host.docker.internal:host-gateway" # Permite a Prometheus salir a escuchar al Host de Codespaces
    depends_on:
      - postgres-matriz

  # ==========================================================
  # VISUALIZACIÓN: GRAFANA
  # ==========================================================
  grafana:
    image: grafana/grafana-oss:10.0.3
    container_name: cpd-grafana
    ports:
      - "3000:3000" # Exponemos el panel gráfico al puerto del Host
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin # Credenciales de acceso rápido para el alumno
    networks:
      - red_empresarial
    volumes:
      - datos_grafana:/var/lib/grafana
    depends_on:
      - prometheus

  # ==========================================================
  # SUCURSAL A (CIUDAD DEL ESTE)
  # ==========================================================
  postgres-sucursal-a:
    image: postgres:15-alpine
    container_name: cpd-sucursala-db
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: sucursal_a_db
      POSTGRES_USER: ucom_admin
      POSTGRES_PASSWORD: password_sucursal_a
    networks:
      - red_empresarial
    volumes:
      - datos_sucursal_a:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M
        reservations:
          memory: 128M

  # ==========================================================
  # SUCURSAL B (ENCARNACIÓN)
  # ==========================================================
  postgres-sucursal-b:
    image: postgres:15-alpine
    container_name: cpd-sucursalb-db
    ports:
      - "5434:5432"
    environment:
      POSTGRES_DB: sucursal_b_db
      POSTGRES_USER: ucom_admin
      POSTGRES_PASSWORD: password_sucursal_b
    networks:
      - red_empresarial
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
  # SUCURSAL C (CORONEL OVIEDO)
  # ==========================================================
  postgres-sucursal-c:
    image: postgres:15-alpine
    container_name: cpd-sucursalc-db
    ports:
      - "5435:5432"
    environment:
      POSTGRES_DB: sucursal_c_db
      POSTGRES_USER: ucom_admin
      POSTGRES_PASSWORD: password_sucursal_c
    networks:
      - red_empresarial
    volumes:
      - datos_sucursal_c:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M
        reservations:
          memory: 128M

networks:
  red_empresarial:
    driver: bridge

volumes:
  datos_matriz:
  datos_sucursal_a:
  datos_sucursal_b:
  datos_sucursal_c:
  datos_prometheus:
  datos_grafana:

secrets:
  db_password:
    file: ./db_password.txt
```

---

## 🔍 PASO 5: GUÍA DE RESOLUCIÓN DE ERRORES CLÁSICOS DE INFRAESTRUCTURA

En la vida del programador full-stack, las cosas no siempre funcionan de buenas a primeras. He aquí el mapa de control ante los 3 dolores de cabeza más comunes en este hito práctico:

### ❌ Error A: `got an unexpected keyword argument 'db_offline'` en el Simulador
*   **Origen:** Ocurre porque la definición de la función `ejecutar_simulacion_centralizada` de la Clase 9 fue simplificada en el paso de abstracción de código, pero al final del archivo seguíamos pasándole un argumento booleano en desuso.
*   **Solución:** Reemplaza completamente tu script de Python por la versión `importar_ventas_v4.py` proporcionada en el **Paso 2**. Hemos removido dicho parámetro, dejándolo mapeado con las columnas reales de producción.

### ❌ Error B: `simulador_ventas` DOWN en Prometheus (`connection refused` en puerto 8000)
*   **Origen:** Prometheus no encuentra el hilo del exportador abierto en el host. O bien el script de Python no está ejecutándose, o el puerto se abrió únicamente para la tarjeta loopback (`127.0.0.1`) imposibilitando el cruce de red.
*   **Solución:** 
    1. Abre una **terminal paralela** en tu Codespace y deja ejecutándose el simulador: `python3 importar_ventas_v4.py` de forma permanente.
    2. Asegúrate de forzar la escucha de red en tu código llamando: `start_http_server(8000, addr='0.0.0.0')`.

### ❌ Error C: `401 Unauthorized` al configurar Prometheus en Grafana
*   **Origen:** Poner en el campo de conexión de Grafana la URL pública que empieza por `https://orange-train-....app.github.dev/`. Esa dirección es de uso privado y cifrado para el usuario a través de GitHub, requiriendo cookies que el contenedor de Grafana no tiene.
*   **Solución:** No uses la dirección web externa de Codespaces. Dado que ambos contenedores comparten la misma red lógica virtual (`red_empresarial`), debes apuntarlo usando el DNS interno de Docker en la URL de Grafana:
    ```text
    http://prometheus:9090
    ```

---

## 💾 PASO 6: GUARDADO Y EMPUJE DE RAMA A GITHUB

Una vez que audites tus targets de Prometheus en verde (**UP**) y conectes con éxito tu base de datos temporal a Grafana, asegura tu avance técnico subiéndolo a la nube:

```bash
# 1. Auditar los cambios detectados
git status

# 2. Agregar los nuevos archivos y carpetas (.env, monitoreo, importar_ventas_v4.py, compose.yaml)
git add .

# 3. Guardar el hito
git commit -m "Fase 5 - Integración de Prometheus, Grafana y Mapeo de online_retail_II.csv en la rama monitoring"

# 4. Empujar la rama 'monitoring' al repositorio público
git push origin monitoring
```
