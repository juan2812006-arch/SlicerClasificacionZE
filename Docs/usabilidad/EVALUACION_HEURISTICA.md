# Evaluación heurística previa — Clasificación de ZE

Revisión de la interfaz con las 10 heurísticas de Nielsen, hecha **antes** de
las pruebas con usuarios para no gastar sesiones en problemas evidentes. Para
cada problema se indica su gravedad (0–4, escala de Nielsen) en la versión
anterior y el cambio aplicado.

Una evaluación heurística la hace un evaluador experto, no los usuarios finales:
no sustituye las pruebas con usuarios del
[protocolo](PROTOCOLO_PRUEBAS_USABILIDAD.md). Los puntos de la sección
*Pendiente* son hipótesis que las pruebas deben confirmar o descartar.

## Problemas encontrados y corregidos

| # | Heurística | Problema en la versión anterior | Gravedad | Cambio aplicado |
|---|---|---|---|---|
| 1 | Visibilidad del estado del sistema | Durante horas de procesamiento solo se veía el nombre del script (`mri_tesselate.py`) y el contador de pasos; no había tiempo transcurrido. | 3 | Cada paso se muestra con su nombre en lenguaje claro (*Paso 23/31: Corrección topológica*), con el tiempo transcurrido y la duración final. |
| 2 | Visibilidad del estado del sistema | No se sabía qué faltaba para poder ejecutar: los errores aparecían de uno en uno al pulsar el botón. | 3 | El paso *4. Ejecutar* lista en vivo lo que falta para cada modo, y los botones solo se activan cuando todo está listo (su tooltip repite la lista). |
| 3 | Relación con el mundo real | Términos técnicos: *pipeline*, *Subject ID*, *Directorio de resultados*, nombres de scripts, "sujeto". | 2 | Lenguaje clínico y coherente: *Paciente*, *ID del paciente*, *Procesar MRI nuevo*; los nombres técnicos quedan en el registro detallado. |
| 4 | Control y libertad del usuario | Para volver a ver un paciente había que repetir FreeSurfer (horas). | 4 | Nuevo modo **Visualizar paciente ya procesado** (minutos), sin T1 ni FreeSurfer. |
| 5 | Control y libertad del usuario | Si se cerraba el panel de resultados no había forma de recuperarlo. | 3 | Botón **Mostrar panel de resultados** (sección 5). |
| 6 | Control y libertad del usuario | No se podía detener FreeSurfer. | 3 | Botón **Cancelar procesamiento** con confirmación (y detención al cerrar Slicer). |
| 7 | Consistencia y estándares | El módulo usaba el icono genérico de la plantilla de Slicer; el grupo de controles se llamaba "Transparencia y electrodos" aunque no hubiera electrodos; "sujeto" y "paciente" mezclados. | 1 | Icono propio con los colores de la leyenda; título del grupo según lo cargado; "paciente" en toda la interfaz. |
| 8 | Prevención de errores | El contenido de los archivos (CSV de características, EEG, SEEG) solo se comprobaba **después** de FreeSurfer: un error de formato se descubría horas más tarde. | 4 | Los archivos se leen y validan antes de empezar, con mensajes que indican la causa. |
| 9 | Prevención de errores | Procesar un ID ya procesado sobrescribía sus resultados sin avisar. | 4 | Se ofrece **Visualizar sin reprocesar** o **Reprocesar (sobrescribe)**, y la confirmación avisa si hay resultados anteriores. |
| 10 | Prevención de errores | El ID admitía espacios, tildes o barras, que rompen las rutas de FreeSurfer. | 3 | El ID se valida en vivo (letras, números, `-`, `_`, `.`). |
| 11 | Prevención de errores | El procesamiento empezaba sin confirmación, aunque dura horas. | 2 | Diálogo de confirmación con el resumen del paciente, los archivos y la duración esperada. |
| 12 | Reconocer antes que recordar | FreeSurfer y la carpeta de resultados se pedían en cada sesión; los formatos de archivo no se explicaban en la interfaz. | 3 | Ambos se recuerdan y FreeSurfer se detecta solo; cada campo tiene un tooltip con el formato esperado; se muestra la carpeta exacta del paciente. |
| 13 | Flexibilidad y eficiencia | No había forma de probar la herramienta sin un paciente procesado. | 3 | Botón **Cargar datos de demostración** (*fsaverage* + datos sintéticos). |
| 14 | Diseño estético y minimalista | Un formulario largo sin agrupar y un registro técnico de FreeSurfer siempre visible. | 2 | Pasos numerados en secciones plegables; el registro técnico queda plegado en *Registro detallado*. |
| 15 | Diagnóstico y recuperación de errores | Los fallos mostraban trazas de Python en el registro y no decían en qué paso ni por qué. | 3 | Mensajes en lenguaje claro con causas frecuentes y qué hacer; se indica el paso de FreeSurfer que falló y el registro se guarda en la carpeta del paciente. |
| 16 | Ayuda y documentación | No había manual ni leyenda de colores; la ayuda del módulo era una frase. | 4 | **Manual de uso** integrado (botón del panel), leyenda de colores en el panel de resultados, ayuda del módulo con el uso rápido. |
| 17 | Ayuda y documentación | Se mezclaban dos probabilidades (visual y calibrada) sin explicar la diferencia, lo que invitaba a leer el 100 % como certeza. | 3 | La interfaz solo muestra la probabilidad visual, con leyenda y nota; la sección *5. Resultados* lista las regiones clasificadas como epileptogénicas. La probabilidad calibrada queda en `predicciones_soz_modelo.csv`, explicada en el manual (apartado 8.1). |

## Pendiente (a evaluar en las pruebas)

| # | Observación | Gravedad estimada | Qué observar |
|---|---|---|---|
| P1 | Los nombres de región son los códigos del atlas Destrieux (`G_oc-temp_med-Parahip`), poco legibles para personal clínico. | 2 | Si en T3/T4 los participantes dudan al leer o buscar regiones. Posible solución: columna con el nombre anatómico completo en español. |
| P2 | El tiempo restante de FreeSurfer no se estima (depende del equipo y de la imagen). | 1 | No se evalúa con la demostración; preguntar en la entrevista si sería útil. |
| P3 | Los electrodos EEG se ubican con posiciones estándar del sistema 10-20, no digitalizadas. El manual lo aclara, pero la vista 3D no. | 2 | Si en T5 o en la entrevista alguien los interpreta como posiciones reales. |
| P4 | Seleccionar una región solo es posible desde la tabla, no haciendo clic en el cerebro. | 2 | Si en T4 intentan hacer clic en la vista 3D. |
| P5 | La interfaz solo está en español. | 1 | Solo si hay participantes de otros idiomas. |
