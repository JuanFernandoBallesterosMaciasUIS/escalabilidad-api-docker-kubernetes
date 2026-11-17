# Proyecto Final: Análisis del comportamiento de una aplicación en distintos escenarios de despliegue

Una API REST de productos (FastAPI + PostgreSQL, 10.000 registros) desplegada con:

1. **Docker Compose** (una sola máquina)
2. **Kubernetes (kind)** con **1, 2 y 3 nodos**, cada uno con **1, 2 y 3 réplicas** de la API

Se le aplicó carga con **JMeter** (10, 50 y 100 usuarios) y en el notebook se analizan el tiempo medio de respuesta y el throughput.

## Estructura

```
app/                  Código de la API (main.py), requirements.txt y Dockerfile
docker-compose.yml    Despliegue de la Fase 1
k8s/                  YAML de Kubernetes (postgres.yaml, api.yaml) y clústeres kind de 1, 2 y 3 nodos
jmeter/prueba.jmx     Plan de pruebas de JMeter
ejecutar_pruebas.ps1  Script que corre todos los escenarios
resultados/           CSV de JMeter (uno por escenario/réplicas/carga) y ubicación de los pods
analisis.ipynb        Notebook con la documentación, las gráficas y las conclusiones
reporte.pdf           Instrucciones de ejecución y enlaces
presentacion.pptx     Presentación
```

## Requisitos

- Docker Desktop (con 8 GB de RAM o más asignados)
- kubectl (viene con Docker Desktop)
- [kind](https://kind.sigs.k8s.io/) v0.27.0 (el script lo busca en `tools/kind.exe`)
- Java 8 o superior y [JMeter 5.6.3](https://jmeter.apache.org/) (el script lo busca en `../apache-jmeter-5.6.3`)

## Cómo ejecutar

### Solo la API (Docker Compose)
```powershell
docker compose up -d --build
curl http://localhost:8080/productos?page=1
curl http://localhost:8080/productos/10
curl -X POST http://localhost:8080/productos -H "Content-Type: application/json" -d '{"nombre":"Mesa","categoria":"Hogar","precio":120.5,"stock":10}'
docker compose down
```

### Kubernetes a mano (ejemplo con 2 nodos y 3 réplicas)
```powershell
docker build -t api-productos:1.0 ./app
kind create cluster --config k8s/kind-2nodos.yaml
kubectl taint nodes --all node-role.kubernetes.io/control-plane-
kind load docker-image api-productos:1.0
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/api.yaml
kubectl scale deployment api-deployment --replicas=3
kubectl get pods -o wide          # muestra en qué nodo quedó cada pod
curl http://localhost:8080/health
kind delete cluster
```

### Todas las pruebas de carga
```powershell
powershell -ExecutionPolicy Bypass -File .\ejecutar_pruebas.ps1
```
Tarda unos 45 minutos. Los resultados quedan en `resultados/`.

### Notebook
Se puede abrir `analisis.ipynb` en GitHub (las gráficas ya están generadas) o en Google Colab. En Colab, la primera celda clona el repositorio para tener acceso a los CSV.
