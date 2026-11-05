# Validación de esta instalación

Fecha: 5 de noviembre de 2026. Proyecto: `C:\dev\Gen STL`.

## Equipo y motor

- Windows, NVIDIA GeForce RTX 3050 6GB Laptop GPU, 6144 MiB VRAM, aproximadamente 16 GB RAM.
- Python 3.12, PyTorch `2.6.0+cu124`, torchvision `0.21.0+cu124`; CUDA disponible.
- Mini Turbo y multivista descargados y verificados con SHA-256. Segmentador U2NetP descargado y probado con una imagen sobre blanco.
- Código oficial de Tencent sin modificaciones; adaptación de carga y memoria en `app/engine.py` y `app/worker.py`.

## Generaciones reales en GPU

Calidad Borrador, semilla 12345, lado mayor de 100 mm. No se utilizaron mallas preconstruidas como sustituto de IA.

| Prueba | Modelo | Pasos | Resolución | Caras | Vértices | Malla cerrada | Tiempo del motor |
|---|---|---:|---:|---:|---:|---|---:|
| Una imagen | Mini Turbo | 5 | 128³ | 80.448 | 40.220 | Sí | 26,8 s |
| Frontal, izquierda y trasera | Hunyuan3D-2mv | 20 | 128³ | 70.422 | 35.215 | Sí | 100,2 s |

El tiempo informado por el worker incluye carga, preparación, inferencia y exportación después de importar el motor; no incluye arranque del intérprete, cola ni instalación inicial. Son dos ejemplos, no una garantía de rendimiento o calidad para cualquier imagen.

Trabajos conservados en el historial:

- `data/jobs/314128d08f254615b407949836d0a5f9/`: pingüino de demostración, una imagen. Dimensiones de impresión: 65,77 × 55,76 × 100 mm.
- `data/jobs/0f7b497e0a914256b330870d1b9f2912/`: conjunto oficial multivista. Dimensiones: 66,03 × 55,71 × 100 mm.

## Exportación y descarga

Se descargaron mediante HTTP y reabrieron **los ocho archivos reales**, cuatro por generación, con Trimesh. Se verificaron vértices finitos, caras, escala de 100 mm y coherencia entre formatos. Las pruebas de API verifican además la rotación de ejes con una malla asimétrica. Los GLB incluyen normales explícitas y el visor también las recalcula para evitar superficies negras cuando un archivo no las contiene.

La descarga STL de una imagen se activó desde el botón de la interfaz. El archivo en Descargas coincide por SHA-256 con el archivo del trabajo. Los tamaños, hashes y dimensiones de las ocho descargas quedan en `data/export-validation.json`.

## Cancelación real y reinicio

Se inició una generación en calidad Alta y se canceló cuando el muestreo había llegado al 37 %. Se verificó estado `cancelled`, ausencia de procesos `app.worker` para ese trabajo y retorno de la GPU a aproximadamente 261 MiB de uso general, sin actividad de generación. Windows detiene el árbol del proceso, incluido el hijo del redirector del entorno virtual. Registro: `data/cancel-validation.json`.

Los registros de la prueba de cancelación y de una incompatibilidad inicial de carga corregida se conservan en `data/diagnostics/`, fuera de la biblioteca visible. Se reinició el servidor para comprobar que el historial y los archivos completados se recuperan del disco.

## Pruebas automáticas e interfaz

`python -m pytest -q`: **12 pruebas aprobadas**. Incluyen validación de imágenes y vistas, límites de parámetros, recuperación de trabajos interrumpidos, cancelación de trabajos en cola, persistencia, bloqueo de origen cruzado y descarga de formatos. La exportación GLB comprueba la presencia de normales en el archivo. Starlette emite un aviso de deprecación de su adaptador de pruebas con httpx; no afecta estas comprobaciones ni el funcionamiento de la app.

Comprobaciones adicionales: importación CUDA, `pip check` sin conflictos, sintaxis JavaScript y Python, ejecución satisfactoria de `instalar.ps1 -SinModelos`, y ausencia de cambios en el repositorio del motor.

Interfaz revisada en navegador a ancho móvil y escritorio: carga de una imagen y de tres archivos simultáneos, asignación de vistas, generación real, progreso, visor, iluminación, descarga STL, ayuda e historial. Las tres vistas se comprobaron individualmente antes de enviar el trabajo. Vista guardada en `docs/vista-previa.jpg`.

## Límites de esta validación

Se verificaron generaciones completas en Borrador con una y tres imágenes. No se probaron exhaustivamente todas las combinaciones de dos/cuatro vistas, semillas o resoluciones Estándar/Alta, ni impresión física, texturas o uso con otros equipos. Alta se utilizó para la prueba de cancelación, sin completarse. Los modelos son estimaciones generativas y la malla cerrada no certifica espesor ni imprimibilidad física.
