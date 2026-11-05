# Estudio del servicio y reproducción funcional

Fecha: 5 de noviembre de 2026. Referencia solicitada: https://3d.hunyuan.tencent.com.

## Qué se pudo observar

La página pública carga una aplicación JavaScript y presenta una pantalla de acceso para entrar al estudio. No se accedió a una sesión de Tencent ni se inspeccionaron sus servidores, pesos privados o API interna. El flujo de trabajo requerido por el usuario se implementó a partir del código, modelos y ejemplos publicados por Tencent. Esto es una reproducción funcional independiente de imagen a malla; no constituye una copia exacta ni una recuperación del código propietario del sitio.

## Cómo se transforma una imagen en 3D

Los documentos oficiales describen dos etapas: Hunyuan3D-Shape estima la geometría condicionada por imágenes; Hunyuan3D-Paint agrega texturas. La forma se obtiene por un proceso generativo y extracción de superficie. Una única vista no especifica la cara oculta, por lo que la IA la estima. El modelo multivista añade información de otros ángulos del mismo objeto. Convertir la malla resultante a STL u OBJ es una etapa posterior de exportación; no basta con cambiar la extensión de una imagen.

## Elección técnica

Python integra directamente PyTorch, los modelos oficiales, Pillow, rembg y Trimesh. FastAPI mantiene ligera la aplicación mientras un subproceso ejecuta la IA. Three.js permite inspección interactiva desde el navegador local sin instalar una aplicación gráfica adicional.

Equipo detectado: NVIDIA GeForce RTX 3050 Laptop de 6144 MiB y aproximadamente 16 GB RAM. Se elige Mini Turbo para una foto y resolución inicial 128³. Se evita el módulo de texturas, que requiere más VRAM y extensiones nativas. Para multivista se prepara Hunyuan3D-2mv con las claves de vista del ejemplo oficial. Hay un solo trabajo activo en GPU; los componentes encoder/DiT/VAE se trasladan por etapas para reducir memoria. El checkpoint y el encoder siguen exigiendo RAM y las resoluciones altas pueden superar la VRAM disponible.

La adaptación por etapas está en el código de la app. El método de offload del upstream utiliza una propiedad `components` que no está definida en la clase fijada; por eso se llaman explícitamente las etapas del pipeline. Se fija una revisión del repositorio para que esta adaptación no dependa de cambios futuros.

La carga evita la copia inicial FP32 del pipeline: crea parámetros en el dispositivo meta con Accelerate, mapea los safetensors en CPU y los asigna directamente. Los buffers no persistentes se crean en CPU. El VAE de estos checkpoints sólo publica los pesos de decodificación; sus módulos de codificación de nubes de puntos ausentes se excluyen, y se comprueba de forma estricta el resto de los pesos. Los archivos del upstream no se modifican.

## Alcance entregado

Entrada de una a cuatro imágenes, selección semántica de vistas, eliminación opcional de fondo, inferencia local real, semilla repetible dentro de las limitaciones del hardware, tres resoluciones, historial, cancelación, visor y exportación STL/OBJ/GLB/PLY. Sin texturas generadas, edición topológica avanzada, rigging, animación ni equivalencia de calidad garantizada con el servicio online. Los modelos publicados y la versión del servicio web pueden ser distintos.

## Fuentes primarias

- [Sitio de referencia](https://3d.hunyuan.tencent.com/).
- [Repositorio oficial y arquitectura](https://github.com/Tencent-Hunyuan/Hunyuan3D-2).
- [Ejemplo oficial Mini Turbo](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/examples/faster_shape_gen_with_flashvdm_mini_turbo.py).
- [Ejemplo oficial multivista](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/examples/shape_gen_multiview.py).
- [Pesos Mini](https://huggingface.co/tencent/Hunyuan3D-2mini).
- [Pesos multivista](https://huggingface.co/tencent/Hunyuan3D-2mv).
- [Artículo técnico Hunyuan3D 2.0](https://arxiv.org/abs/2501.12202).
- [Hunyuan3D 2.1 y sus requisitos](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1).

Las fuentes describen los componentes públicos. Las decisiones de diseño de Gen STL y la adaptación al equipo son implementación propia; no se afirma que describan la infraestructura privada de Tencent.
