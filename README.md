# Gen STL Studio

Aplicación local para Windows: una imagen o hasta cuatro vistas del **mismo objeto** → geometría 3D → STL, OBJ, GLB o PLY. Interfaz en español con visor orbital, modo malla, escala, semilla, cola, cancelación e historial persistente.

## Abrir

Haz doble clic en **Iniciar.cmd**. Abre http://127.0.0.1:7860 y conserva la consola abierta. Para detener: Ctrl+C. El servidor escucha sólo en tu equipo.

Carpeta de desarrollo: `C:\dev\Gen STL`. El proyecto puede clonarse en otra ruta. Entorno Python aislado en `.venv`; ninguna dependencia de IA se instala globalmente.

En el equipo de desarrollo se instalaron Mini Turbo, multivista y el segmentador de fondo y se generaron ejemplos reales. Resultados y límites comprobados: [registro de validación](docs/validacion.md). Los pesos, entornos y resultados locales **no se incluyen en el repositorio**; el instalador prepara las dependencias y descarga los modelos.

## Instalación reproducible

Requisitos: Windows x64, Python 3.12, Git, Node.js con npm o pnpm y GPU NVIDIA con controlador compatible con CUDA 12.4. El instalador también reconoce el runtime local de Codex si está disponible. Reserva al menos 20 GB para entorno, caché y modelos (más para multivista).

```powershell
git clone https://github.com/supernero1/STL-Gen.git
cd STL-Gen
powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar.ps1
```

Si ya tienes el proyecto descargado, ejecuta sólo el último comando desde su carpeta. Después abre `Iniciar.cmd`.

La instalación descarga PyTorch CUDA 12.4, las dependencias fijadas, el código oficial en una revisión fija y Mini Turbo (~3,82 GB). `-SinModelos` omite pesos; `-Multivista` descarga además el modelo multivista (~4,93 GB). El segmentador de fondo U2NetP (~4,6 MB) se descarga la primera vez que se utiliza. Al generar varias vistas se descarga automáticamente su modelo si falta. Las fotos no se envían a ningún servicio; las descargas de pesos sí requieren internet. Con todos los pesos necesarios en caché, la inferencia es local.

## Uso

1. Carga PNG, JPG o WebP estáticos, 64–4096 píxeles por lado y hasta 15 MB por archivo. La vista frontal es obligatoria.
2. Una foto usa **Hunyuan3D-2mini Turbo**. Entre dos y cuatro usan **Hunyuan3D-2mv**; asigna frontal, izquierda, trasera y derecha sin repetir. Las imágenes corresponden a un único objeto, no a objetos independientes.
3. Empieza en **Borrador**, especialmente con una RTX 3050 de 6 GB. Estándar y Alta incrementan la resolución de extracción; multivista consume más memoria y tiempo. Los componentes de IA pasan por la GPU de uno en uno. No se garantiza que toda combinación de calidad y vistas quepa en 6 GB.
4. Indica el tamaño del lado mayor en milímetros. La foto no contiene una medida física fiable; es una escala elegida por ti.
5. Genera, inspecciona y descarga. El visor muestra el GLB; todas las exportaciones provienen de la misma malla.

STL, OBJ y PLY se exportan con Z vertical y coordenadas en mm, apoyados en Z=0. STL no codifica unidades: selecciona mm al importarlo en el laminador. GLB usa Y vertical y metros conforme a glTF. Las dimensiones de la interfaz corresponden al modelo de impresión (XYZ). Los formatos son **geometría sin texturas**; STL no almacena color. El color del visor sólo cambia su visualización.

La limpieza elimina geometría degenerada, corrige normales e intenta cerrar agujeros pequeños. El indicador «Malla cerrada» informa el resultado; no promete que cualquier malla sea imprimible. Verifica soportes, espesor, orientación y dimensiones en tu laminador. Las partes ocultas son estimaciones de IA, no fotogrametría ni escaneado dimensional.

### Dibujos frontales que salen planos

Un dibujo con colores planos y contornos puede ser interpretado como una lámina aunque la malla quede cerrada. Aumentar la resolución o engrosar uniformemente el eje de profundidad no reconstruye los costados. Para un personaje completo, prepara primero una referencia como figura de resina en vista de tres cuartos, con cabeza, hocico, cuerpo y base redondeados; luego cárgala aquí. También puedes usar vistas frontal/lateral/trasera coherentes de la misma figura, preparadas por separado con una IA de imágenes.

La app avisa cuando el fondo es menor al 12 % del mayor entre ancho y alto, tanto en trabajos nuevos como antiguos. Es una heurística visual; un relieve, moneda o placa puede ser delgado intencionalmente. No se estira la malla para ocultar el problema. El selector de ángulo del visor permite inspeccionar Frente, Costado y Atrás.

La preparación de referencias con IA **todavía no está automatizada dentro de la app local**. El caso del dragón se resolvió con una referencia generada en esta conversación y después se ejecutó la reconstrucción local. Consulta [comparación y archivos del dragón](docs/dragon-volumen.md).

## Arquitectura y estudio del servicio de referencia

Consulta [docs/estudio-tecnico.md](docs/estudio-tecnico.md) para las fuentes, el alcance y las diferencias con el servicio de Tencent.

- **Python 3.12 / PyTorch**: inferencia local Hunyuan3D, segmentación y exportación con Trimesh.
- **FastAPI**: API, recepción de imágenes y servidor local.
- **JavaScript nativo / Three.js**: interfaz y visor WebGL. Three se sirve desde el disco, sin CDN.
- **Un subproceso por trabajo, cola de un consumidor**: evita generaciones simultáneas en la GPU y permite cancelar liberando sus recursos.
- **JSON y archivos locales**: historial persistente sin base de datos externa. Trabajos interrumpidos se señalan al reiniciar; no se reanudan a mitad del muestreo.

`app/main.py` contiene la API; `app/engine.py`, la carga de pesos; `app/worker.py`, la inferencia; `app/mesh.py`, la exportación; `web/`, la interfaz. La carga usa mapeo de memoria, parámetros iniciales en el dispositivo meta y asignación de pesos para reducir duplicados en RAM. El encoder de nubes de puntos del VAE se omite cuando el checkpoint sólo incluye el decodificador de generación. `vendor/Hunyuan3D-2` conserva el código original, sin modificar, revisión `f8db63096c8282cb27354314d896feba5ba6ff8a`.

Se fijan también las revisiones de los pesos: Mini `f90a0f7df7d5e6f71109cf333f6a95a0ae3194a6` y multivista `3a761b539b29fe4ff64714813aa9560fd66f5de0`. Las descargas grandes se reanudan por fragmentos y sólo se promueven a archivo definitivo tras verificar SHA-256. `requirements-lock.txt` registra todas las versiones del entorno validado; para restaurarlo desde cero se necesita el índice CUDA de PyTorch además de PyPI.

## Archivos y privacidad

Cada generación crea `data/jobs/<id>/` con `job.json`, imágenes normalizadas, imágenes preparadas, `model.*`, `result.json` y `worker.log`. El nombre del archivo original nunca se utiliza como ruta. Los pesos y sus licencias están en `.cache/models/`; el segmentador, en `.cache/rembg/`. El entorno, la caché y los datos están excluidos de Git.

El proyecto no incorpora cuentas, pagos ni telemetría propia. Es una app para uso local de una persona; para exponerla a internet harían falta autenticación, límites globales, almacenamiento y operación del servidor GPU.

## Verificación y desarrollo

```powershell
.\.venv\Scripts\python.exe -m pip install pytest==9.2.0
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 7860
```

Las pruebas validan imágenes y vistas, persistencia y cancelación en cola, recuperación al reiniciar, origen de peticiones y descarga de los cuatro formatos. Releen archivos reales para verificar escala, unidades y rotación. El motor se simula únicamente en esas pruebas de API para no descargar pesos ni ocupar la GPU; una generación real debe verificarse por separado. El registro de validación de esta instalación se encuentra en `docs/validacion.md`.

API interactiva: http://127.0.0.1:7860/docs. Endpoints: `GET /api/system`, `GET/POST /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`, `GET /api/jobs/{id}/model/{stl|obj|glb|ply}`.

Si aparece un error de memoria, cierra juegos/otras apps de IA y prueba Borrador y una sola imagen. Si el modelo no descarga, verifica conexión y vuelve a ejecutar `python -m app.download --engine mini` desde `.venv`. Para diagnóstico, consulta `worker.log` del trabajo.

## Licencias y atribución

Aplicación independiente creada para uso de Marcos Medina. Usa el motor de Tencent; no está afiliada, patrocinada ni respaldada por Tencent. El código de esta app y los modelos de terceros son componentes distintos. No se atribuye propiedad de los pesos ni del servicio original.

La licencia comunitaria de Hunyuan3D incluye condiciones de distribución, uso comercial y territorio. Conserva y consulta las licencias de **cada modelo**, no sólo la del repositorio de código, antes de distribuir o vender un servicio. Se incluyen referencias y copias en `licenses/` y en las carpetas de descarga. [Licencia del código oficial](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/LICENSE), [Mini](https://huggingface.co/tencent/Hunyuan3D-2mini/blob/main/LICENSE), [Multivista](https://huggingface.co/tencent/Hunyuan3D-2mv/blob/main/LICENSE).
