# Ejecuta todos los escenarios de prueba y guarda los resultados de JMeter en resultados/
#   Escenario 1: Docker Compose (1 replica)
#   Escenarios 2-4: Kubernetes (kind) con 1, 2 y 3 nodos x 1, 2 y 3 replicas
# Cada configuracion se prueba con 10, 50 y 100 usuarios durante 60 segundos.
#
# Uso:  .\ejecutar_pruebas.ps1            (todo)
#       .\ejecutar_pruebas.ps1 -Solo compose
#       .\ejecutar_pruebas.ps1 -Solo 2      (solo el cluster de 2 nodos)

param([string]$Solo = "todo")

$JMETER_JAR = "..\apache-jmeter-5.6.3\bin\ApacheJMeter.jar"   # se llama con java -jar
$KIND     = ".\tools\kind.exe"
$CARGAS   = @(10, 50, 100)   # usuarios concurrentes
$DURACION = 60               # segundos por prueba
$REPLICAS = @(1, 2, 3)

Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force resultados | Out-Null

function Esperar-Api {
    for ($i = 0; $i -lt 60; $i++) {
        try { Invoke-RestMethod http://localhost:8080/health -TimeoutSec 2 | Out-Null; return } catch { Start-Sleep 2 }
    }
    throw "La API no respondio en localhost:8080"
}

function Correr-Cargas($nombre, $limpiarBD) {
    foreach ($u in $CARGAS) {
        & $limpiarBD   # borra los productos creados por pruebas anteriores
        Start-Sleep 5
        Write-Host ">>> $nombre con $u usuarios"
        $csv = "resultados\${nombre}_${u}u.csv"
        Remove-Item $csv -ErrorAction SilentlyContinue
        java -jar $JMETER_JAR -n -t jmeter\prueba.jmx "-JUSUARIOS=$u" "-JDURACION=$DURACION" -l $csv -j "resultados\jmeter.log" | Select-String "summary ="
    }
}

$SQL_LIMPIAR = "DELETE FROM productos WHERE id > 10000"

# ---------------- Escenario 1: Docker Compose ----------------
if ($Solo -eq "todo" -or $Solo -eq "compose") {
    docker compose up -d --build
    Esperar-Api
    Correr-Cargas "compose_1n_1r" { docker compose exec -T db psql -U postgres -d tienda -q -c $SQL_LIMPIAR }
    docker compose down
}

# ---------------- Escenarios 2-4: Kubernetes ----------------
docker build -t api-productos:1.0 .\app
foreach ($n in 1, 2, 3) {
    if ($Solo -ne "todo" -and $Solo -ne "$n") { continue }

    $config = if ($n -eq 1) { "k8s\kind-1nodo.yaml" } else { "k8s\kind-${n}nodos.yaml" }
    & $KIND delete cluster
    & $KIND create cluster --config $config

    # Permitir pods en el control-plane (asi todos los nodos trabajan)
    kubectl taint nodes --all node-role.kubernetes.io/control-plane- 2>$null
    # Cada nodo simula una maquina de 2 CPU y 3 GB de RAM
    foreach ($nodo in (& $KIND get nodes)) { docker update --cpus 2 --memory 3g --memory-swap 3g $nodo | Out-Null }

    & $KIND load docker-image api-productos:1.0
    kubectl apply -f k8s\postgres.yaml
    kubectl rollout status deployment/postgres-deployment --timeout=180s
    kubectl apply -f k8s\api.yaml
    kubectl rollout status deployment/api-deployment --timeout=180s

    foreach ($r in $REPLICAS) {
        kubectl scale deployment api-deployment --replicas=$r
        kubectl rollout status deployment/api-deployment --timeout=180s
        Esperar-Api
        $nombre = "k8s_${n}n_${r}r"
        kubectl get pods -o wide | Out-File "resultados\pods_$nombre.txt"   # en que nodo quedo cada pod
        Correr-Cargas $nombre { kubectl exec deploy/postgres-deployment -- psql -U postgres -d tienda -q -c $SQL_LIMPIAR }
    }
    & $KIND delete cluster
}

Write-Host "Listo. Resultados en la carpeta resultados\"
