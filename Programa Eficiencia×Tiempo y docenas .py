# Programa para calcular eficiencia por hora y por carga

HORAS = 11

# Número de cargas
n = int(input("Ingrese el numero de cargas: "))

meta = []
produccion = []

total_producido = 0
suma_metas = 0

# Ingreso de datos
for i in range(n):
    print(f"\nCarga {i+1}")
    
    m = float(input("Meta de la carga: "))
    p = float(input("Docenas hechas: "))
    
    meta.append(m)
    produccion.append(p)
    
    suma_metas += m
    total_producido += p

# Horas de paro
horas_paro = float(input("\nIngrese horas de paro total del dia: "))

# 🔹 Docenas por hora por carga
print("\n--- DOCENAS POR HORA POR CARGA ---")
for i in range(n):
    docenas_hora = meta[i] / HORAS
    print(f"Carga {i+1}: {round(docenas_hora,2)} docenas/hora")

# 🔹 Meta promedio del día
meta_promedio = suma_metas / n

# 🔹 Ajuste por tiempo muerto
descuento_paro = (meta_promedio / HORAS) * horas_paro
meta_dia = meta_promedio - descuento_paro

# 🔹 Eficiencia total
eficiencia = (total_producido / meta_dia) * 100

print("\n--- RESULTADOS DEL DIA ---")
print("Meta promedio:", round(meta_promedio,2))
print("Meta ajustada del dia:", round(meta_dia,2))
print("Produccion total:", total_producido)
print("Eficiencia total:", round(eficiencia,2), "%")

# 🔹 Tiempo por carga según eficiencia
print("\n--- TIEMPO POR CARGA SEGUN EFICIENCIA ---")

eficiencia_decimal = eficiencia / 100

for i in range(n):
    docenas_hora = meta[i] / HORAS
    ritmo_real = docenas_hora * eficiencia_decimal
    
    tiempo = produccion[i] / ritmo_real
    
    horas = int(tiempo)
    minutos = int((tiempo - horas) * 60)
    
    print(f"Carga {i+1}: {horas} h {minutos} min")

print("\nPrograma finalizado.")