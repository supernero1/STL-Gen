# Dragón: de dibujo frontal a figura con volumen

5 de noviembre de 2026. La prueba del usuario produjo una figura casi plana: 88,03 × 2,58 × 100 mm. Se preservó ese trabajo sin modificarlo.

## Diagnóstico y comparación real

| Entrada | Reconstrucción | Ancho × fondo × alto (mm) | Observación |
|---|---|---|---|
| Dibujo original frontal | Mini Turbo, Estándar | 88,03 × 2,58 × 100 | Lámina; malla cerrada |
| El mismo dibujo frontal, sin vistas adicionales | Hunyuan3D-2mv, 30 pasos | 89,40 × 0,79 × 100 | También plano; cambiar de motor no resolvió la ambigüedad |
| Referencia reinterpretada como figura redondeada | Mini Turbo, Estándar | 78,23 × 74,97 × 100 | Volumen real en la malla; 279.840 caras; malla cerrada |

La última reconstrucción mantuvo semilla 12345, eliminación de fondo y resolución 192³, como la prueba original. El motor tardó 66,4 segundos en el último caso; ese tiempo no incluye generar previamente la imagen de referencia. La malla no se estiró ni se extruyó a partir de la silueta. Se reabrieron los cuatro archivos exportados para comprobar coordenadas finitas, dimensiones y caras. STL, OBJ y PLY usan mm; GLB usa metros y eje Y vertical.

## Qué se hizo con IA

Se utilizó la herramienta integrada **imagegen**, con la imagen adjunta como referencia de identidad, para reinterpretar el dibujo como un render de una figura tridimensional de resina. Prompt exacto: [dragon-render-3d.txt](prompts/dragon-render-3d.txt). No se utilizó el CLI ni una API key de la app.

La IA estimó volúmenes y partes ocultas. El render es una interpretación del diseño; no proporciona medidas físicas ni una garantía de fidelidad en todos los detalles. Se preparó una imagen de referencia con información de volumen, no un conjunto de vistas ortogonales nuevas.

Archivos dentro del proyecto:

- `data/references/dragon/dragon-original.png`: imagen adjunta preservada.
- `data/references/dragon/dragon-volumen.png`: referencia de volumen generada con IA.
- `data/jobs/1e46cc01ee024984b5194d83e7c0e45c/`: trabajo original del usuario, sin alterar.
- `data/experiments/dragon-mv-frontal/`: comparación con otro motor y la misma referencia plana.
- `data/jobs/d59c7330f2c64dad86967db6108e0672/`: STL/OBJ/GLB/PLY nuevos, visibles en el historial como **Dragón · referencia volumétrica IA**.
- `data/references/dragon/dragon-volumen.stl`: copia del STL listo para abrir, verificada por SHA-256 contra el archivo del trabajo.

## Cambios en la aplicación

La exportación informa `depth_ratio` y `low_depth`. La interfaz muestra un aviso de poca profundidad para relaciones menores al 12 %, incluso en resultados antiguos. «Malla cerrada» se mantiene como propiedad independiente: una lámina también puede ser watertight. Se agregó ayuda específica para ilustraciones y un selector de cámara con Frente, Costado y Atrás para inspeccionar el volumen.

La preparación con IA de la imagen de referencia se hizo en esta conversación. **La app local todavía no genera automáticamente renders o vistas nuevas desde un dibujo.** Agregar esa etapa automática sería una integración adicional; las advertencias y la ayuda no la sustituyen.

Validación: 13 pruebas automáticas aprobadas. La prueba nueva verifica que una caja cerrada de 2,58 mm de espesor se señale como delgada y conserve su espesor al exportar. Los archivos del motor oficial siguen sin modificaciones.

Se verificaron en la interfaz el aviso del trabajo original, el enlace a la ayuda específica, la ausencia del aviso en el resultado nuevo y la vista Costado del modelo volumétrico. Capturas: `docs/dragon-plano.jpg` y `docs/dragon-costado.jpg`.
