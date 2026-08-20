# 📝 GUÍA DE LABORATORIO: Transacciones Distribuidas en la Base de Datos Centralizada (Clase 6)

---

## 🎯 Objetivo de la Clase Práctica
Aprender a simular un sistema transaccional distribuido en vivo en **GitHub Codespaces**. Cada registro de nuestro archivo CSV de ventas representará a un cliente realizando una compra física en una sucursal geográfica distinta (CDE, Encarnación, Coronel Oviedo o Asunción). El script de Python actuará como el "despachador de red", abriendo conexiones dinámicas de base de datos directamente al puerto central de la **Casa Matriz** (`5432`) para asentar de manera concurrente las ventas en una tabla unificada.

---

## 🛠️ PASO 1: Verificar tus Archivos en Codespaces
Asegúrate de tener creados estos 4 archivos en la raíz de tu proyecto en VS Code:

1. `compose.yaml`: El orquestador de contenedores.
2. `ddl-v3.sql`: El archivo SQL idempotente para crear la tabla de datos unificada.
3. `importar_ventas_v3.py`: El script de simulación con delay de 2 segundos y límite de 9 filas.
4. `ventas_muestra.csv`: El archivo CSV con los datos de ejemplo del comercio minorista.

---

## ⚡ PASO 2: Levantar el Clúster en la Nube
Levantaremos los servidores independientes utilizando Docker Compose:

```bash
# Inicializar los contenedores en segundo plano
docker compose up -d

# Comprobar que todos los nodos estén activos
docker compose ps
```

---

## 💾 PASO 3: Ejecutar la Creación de la Tabla Centralizada
Dado que las sucursales compartirán la base de datos de la **Casa Matriz**, la tabla `ventas_locales` debe existir únicamente en el contenedor central de Asunción. Corremos el comando interactivo enviando el archivo `ddl-v3.sql` directamente al contenedor central:

```bash
docker exec -i cpd-matriz-db psql -U ucom_admin -d matriz_db < ddl-v3.sql
```

**Salida esperada:**
```text
CREATE TABLE
CREATE INDEX
```

---

## 🐍 PASO 4: Instalar Pandas y Ejecutar la Simulación
Instalamos la librería Pandas en la terminal y ejecutamos el script de simulación en tiempo real:

```bash
# Instalar Pandas
pip install pandas

# Ejecutar el simulador transaccional
python3 importar_ventas_v3.py
```

*Verás cómo la consola empieza a reportar de forma ordenada, con un retraso exacto de 2 segundos entre registros, de qué sucursal proviene cada venta y cómo se asienta directamente en el puerto central:*

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
------------------------------------------------------------------------------------------
...
```

---

## 📊 PASO 5: Auditar de Forma Centralizada
Para comprobar que todas las transacciones de las distintas sucursales quedaron asentadas de forma consistente y unificada en la base de datos de la **Casa Matriz**, ejecutamos una consulta directa sobre el contenedor central:

```bash
docker exec -it cpd-matriz-db psql -U ucom_admin -d matriz_db -c "SELECT id, invoice_no, quantity, sucursal, insertado_en FROM ventas_locales;"
```

**Salida exitosa esperada (¡Las sucursales comparten la misma base de datos!):**
```text
 id | invoice_no | quantity |     sucursal      |        insertado_en        
----+------------+----------+-------------------+----------------------------
  1 | 536365     |        6 | Sucursal_CDE      | 2026-08-20 23:12:45.102345
  2 | 536365     |        6 | Sucursal_ENC      | 2026-08-20 23:12:47.124567
  3 | 536366     |        6 | Sucursal_COV      | 2026-08-20 23:12:49.143212
  4 | C536379    |       -1 | Sucursal_Asuncion | 2026-08-20 23:12:51.156789
  5 | 536381     |       10 | Sucursal_CDE      | 2026-08-20 23:12:53.178901
...
```

---

## 🛑 PASO 6: Apagar el CPD de Forma Segura
Al terminar de trabajar, apagamos el clúster para conservar las horas gratuitas de Codespaces:

```bash
docker compose down
```
