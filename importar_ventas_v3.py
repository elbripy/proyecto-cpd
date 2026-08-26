# importar_ventas_v3.py
# Script de simulación transaccional distribuida en tiempo real (Conexión Centralizada)
# Cada fila del CSV simula ser una venta remota que una sucursal inyecta en la base de datos central de Asunción
# Cátedra: Procesamiento de Datos - UCOM 2026
# Docente: Ing. David Britez

import os
import time
import random
import pandas as pd
import psycopg2

# Configuración única para conectarse a la Casa Matriz (Puerto 5432)
# Las sucursales se conectan remotamente al nodo central del CPD para asentar sus ventas
DB_CONFIG = {
    "host": "postgres-matriz",
    "port": "5432",  # Puerto de la Casa Matriz
    "database": "matriz_db",
    "user": "ucom_admin",
    "password": "password_matriz"
}

# Colores y configuraciones visuales para simular de qué sucursal proviene el tráfico
SUCURSALES_DISPLAY = {
    "Sucursal_Asuncion": {"color": "\033[93m"},  # Amarillo
    "Sucursal_CDE": {"color": "\033[96m"},       # Cian
    "Sucursal_ENC": {"color": "\033[92m"},       # Verde
    "Sucursal_COV": {"color": "\033[94m"}        # Azul
}

RESET_COLOR = "\033[0m"

def ejecutar_simulacion_centralizada(ruta_csv, db_offline=False):
    print("🚀 INICIANDO SIMULACIÓN DE CONEXIÓN REMOTA MULTI-SUCURSAL (CASA MATRIZ)...")
    print("==========================================================================================")
    
    # 1. Leer el archivo CSV
    if not os.path.exists(ruta_csv):
        print(f"❌ Error: No se encuentra el archivo '{ruta_csv}' en el directorio actual.")
        return
        
    df = pd.read_csv(ruta_csv)
    
    # 2. Limitar estrictamente a los primeros 9 registros del CSV
    df_simulacion = df.head(9).copy()
    print(f"📋 Cargados los primeros {len(df_simulacion)} registros de ventas para la simulación.\n")
    
    lista_sucursales = list(SUCURSALES_DISPLAY.keys())
    
    # 3. Procesar fila por fila con delay de 2 segundos
    for idx, row in df_simulacion.iterrows():
        # Selección aleatoria de la sucursal que origina la venta
        sucursal_elegida = random.choice(lista_sucursales)
        color = SUCURSALES_DISPLAY[sucursal_elegida]["color"]
        
        # Saneamiento del registro
        desc = row["Description"] if not pd.isnull(row["Description"]) else "Sin descripción"
        cust_id = str(row["CustomerID"]).replace(".0", "") if not pd.isnull(row["CustomerID"]) else None
        
        print(f"{color}[CONEXIÓN REMOTA: {sucursal_elegida.upper()} ➔ CASA MATRIZ]{RESET_COLOR}")
        print(f"   ↳ Detalles: Factura: {row['InvoiceNo']} | Item: {desc} | Cantidad: {row['Quantity']} | Precio: L {row['UnitPrice']}")
        
        if db_offline:
            print(f"   ⚡ [SIMULADO] Conectándose remotamente a {DB_CONFIG['host']}:{DB_CONFIG['port']} ({DB_CONFIG['database']})...")
            print(f"   ✅ [SIMULADO] Venta registrada exitosamente en la base de datos central de Asunción.")
        else:
            try:
                # 4. Conectarse dinámicamente a la base de datos central (Matriz)
                print(f"   🔌 Conectándose remotamente al puerto {DB_CONFIG['port']} de la Casa Matriz...")
                conn = psycopg2.connect(
                    host=DB_CONFIG["host"],
                    port=DB_CONFIG["port"],
                    database=DB_CONFIG["database"],
                    user=DB_CONFIG["user"],
                    password=DB_CONFIG["password"],
                    connect_timeout=3
                )
                cursor = conn.cursor()
                
                # Insertar en la tabla unificada ventas_locales
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
                print(f"   ✅ \033[92m[ÉXITO]\033[0m Registro asentado correctamente en la tabla centralizada de Asunción.")
                
            except Exception as e:
                print(f"   ❌ [FALLO] No se pudo asentar la transacción de {sucursal_elegida}.")
                print(f"      Detalle técnico: {e}")
                print("      💡 Asegúrate de que 'docker compose up -d' esté corriendo y hayas ejecutado 'ddl-v3.sql'.")
                
        print("-" * 90)
        # Delay de 2 segundos para ver pasar el flujo de transacciones en vivo
        time.sleep(2)
        
    print("\n🏁 SIMULACIÓN FINALIZADA. Las sucursales registraron todas las ventas en la Base de Datos Central.")

if __name__ == "__main__":
    ejecutar_simulacion_centralizada("ventas_muestra.csv", db_offline=False)
