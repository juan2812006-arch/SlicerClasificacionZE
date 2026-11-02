# Protocolo de pruebas de usabilidad — Clasificación de ZE

Documento para planificar, ejecutar y analizar las pruebas de usabilidad de la
extensión. Los formularios están en [FORMULARIOS.md](FORMULARIOS.md), las
plantillas de registro de datos en `plantilla_resultados_tareas.csv` y
`plantilla_resultados_sus.csv`, y la revisión previa de la interfaz en
[EVALUACION_HEURISTICA.md](EVALUACION_HEURISTICA.md).

## 1. Objetivo

Comprobar si las personas a las que va dirigida la extensión pueden, sin
ayuda:

1. preparar y visualizar un paciente;
2. interpretar correctamente los resultados (qué regiones son SOZ, qué
   significa cada color y cada probabilidad);
3. usar los controles de exploración 3D (tabla, opacidad, electrodos);
4. configurar el procesamiento de un paciente nuevo;
5. entender un error y corregirlo.

Y medir su **eficacia** (tareas completadas), **eficiencia** (tiempo, errores,
ayudas) y **satisfacción** (SEQ por tarea y SUS al final), siguiendo la
definición de usabilidad de la norma ISO 9241-11.

## 2. Método

* **Tipo**: prueba moderada, presencial o remota con pantalla compartida, con
  el protocolo de **pensar en voz alta** (*think-aloud*): la persona dice lo que
  piensa, busca y espera mientras trabaja.
* **Duración**: 45–60 minutos por participante.
* **Datos**: los de **demostración** (cerebro *fsaverage* y datos clínicos
  sintéticos). Ninguna tarea necesita esperar las horas de FreeSurfer ni usar
  datos de pacientes reales.
* **Roles**:
  * *Moderador/a*: lee las consignas, no ayuda salvo bloqueo (ver 5.3).
  * *Observador/a* (recomendado): toma tiempos y anota en la hoja de
    observación.

## 3. Participantes

| Perfil | Quiénes | Número recomendado |
|---|---|---|
| A — Usuario clínico | Neurólogos, neurofisiólogos, neurocirujanos, residentes que trabajan con epilepsia. | 5 o más |
| B — Usuario técnico | Ingenieros biomédicos, investigadores, técnicos de neuroimagen. | 3–5 |

Con 5 participantes por perfil se suelen detectar la mayoría de los problemas
graves de usabilidad (Nielsen y Landauer, 1993). Es preferible hacer dos rondas
de 5 (corregir entre ambas) que una de 10.

Criterios: no haber participado en el desarrollo de la extensión. Registre la
experiencia previa con 3D Slicer y FreeSurfer (cuestionario inicial): es una
variable importante para el análisis.

## 4. Preparación del equipo (antes de cada sesión)

### 4.1 Una sola vez

- [ ] 3D Slicer 5.x instalado y la extensión cargada (aparece el módulo
      **Clasificación de ZE**).
- [ ] FreeSurfer instalado con `license.txt` (por ejemplo
      `/Applications/freesurfer/8.2.0`).
- [ ] **Ensayo completo** con la demostración, para que la extensión instale
      sus paquetes de Python (pulse **Instalar** cuando lo pida; requiere
      internet, solo la primera vez). Si se
      salta este paso, la tarea T2 incluirá una espera de instalación ajena a la
      usabilidad.
- [ ] Copiar en el escritorio la carpeta `materiales/` de este directorio.
- [ ] Programa de grabación de pantalla y audio (QuickTime, OBS...) probado.
- [ ] Ejecutar los tests automáticos (comando en el `README.md` de la
      extensión) y comprobar que terminan en `OK`.

### 4.2 Antes de cada participante (dejar la extensión "como nueva")

1. Cerrar Slicer.
2. Borrar la carpeta de resultados de la sesión anterior
   (por defecto `~/ClasificacionZE_resultados`).
3. Abrir Slicer y, en la consola de Python (*View > Python Console*), borrar
   las preferencias guardadas de la extensión:

   ```python
   for clave in ("freesurfer", "subjectsDir", "ultimaCarpeta"):
       qt.QSettings().remove("Visualizacion/" + clave)
   ```
4. Ir al módulo **Welcome** (no dejar abierta la extensión: abrirla es parte de
   T1).
5. Comprobar que la grabación funciona.

## 5. Desarrollo de la sesión

| Fase | Tiempo | Qué se hace |
|---|---|---|
| Bienvenida y consentimiento | 5 min | Leer el guion 5.1, firmar el consentimiento. |
| Cuestionario inicial | 3 min | Perfil y experiencia (FORMULARIOS.md, sección 2). |
| Tareas T1–T8 | 30–40 min | Leer cada consigna; tras cada tarea, pregunta SEQ. |
| Cuestionario SUS | 3 min | FORMULARIOS.md, sección 4. |
| Entrevista final | 5–10 min | FORMULARIOS.md, sección 5. |

### 5.1 Guion de bienvenida (leer en voz alta)

> Gracias por participar. Vamos a evaluar una extensión de 3D Slicer, no a
> usted: si algo resulta difícil, es un problema de la herramienta y eso es
> justamente lo que queremos encontrar. Le pediré que haga algunas tareas y que,
> mientras tanto, diga en voz alta lo que piensa: qué busca, qué espera que
> pase, qué le sorprende. Yo no podré ayudarle durante las tareas, salvo que
> se quede bloqueado. Los datos que verá son de demostración, no de un
> paciente real. La sesión se graba (pantalla y voz) solo para analizarla;
> puede detenerla cuando quiera. ¿Tiene alguna pregunta?

### 5.2 Durante las tareas

* Lea la consigna tal cual y entréguela también por escrito.
* Inicie el cronómetro cuando la persona empiece y deténgalo cuando diga que
  terminó o cuando se cumpla el tiempo máximo.
* Si la persona se queda callada, recuérdele: *"¿Qué está pensando?"*.
  No pregunte *"¿Por qué hizo eso?"* durante la tarea (lo influye); déjelo para
  la entrevista.
* No confirme si una respuesta es correcta hasta el final.

### 5.3 Cuándo ayudar

Solo si la persona lleva **2 minutos bloqueada** o pide abandonar. Ayude con
la mínima pista (*"¿Hay algo en el panel que pueda ayudarle?"*) y anote la
ayuda: la tarea pasa a **completada con ayuda**.

## 6. Tareas

Cada tarea indica la **consigna** (se lee al participante), el **criterio de
éxito** (solo para el moderador) y un **tiempo máximo**. El orden importa: cada
tarea parte del estado en que quedó la anterior.

### T1 — Encontrar la extensión y su ayuda (máx. 3 min)

**Consigna:** *"Abra la herramienta de clasificación de zonas epileptogénicas
y busque dónde se explica cómo usarla."*

**Éxito:** abre el módulo **Clasificación de ZE** y abre el **Manual de uso**
(o la sección *Help & Acknowledgement*).

### T2 — Ver un caso de ejemplo (máx. 5 min)

**Consigna:** *"Sin usar datos propios, muestre los resultados de un paciente
de ejemplo."*

**Éxito:** pulsa **Cargar datos de demostración** y después **Visualizar
paciente ya procesado**; aparece el cerebro en 3D y el panel de resultados.

### T3 — Interpretar el resultado (máx. 5 min)

**Consigna:** *"Según la herramienta, ¿qué regiones son epileptogénicas y en
qué hemisferio están? ¿Qué significan las regiones de color amarillo o
naranja?"*

**Éxito (los tres):**
1. nombra al menos dos regiones clasificadas como epileptogénicas (lista de la
   sección *5. Resultados* o filas con 100 % en la tabla);
2. dice que están en el hemisferio izquierdo;
3. explica que el amarillo/naranja son regiones vecinas (propagación), no
   regiones clasificadas como epileptogénicas.

*Si interpreta el amarillo como "algo menos epileptogénica" o el 100 % como
certeza clínica, cuéntelo como éxito parcial y anótelo: mide si se entiende la
probabilidad visual.*

### T4 — Examinar una región (máx. 3 min)

**Consigna:** *"Muestre de cerca en la vista 3D el polo temporal (Pole_temporal)
y, cuando termine, vuelva a la vista de todo el cerebro."*

**Éxito:** selecciona la fila *Pole_temporal* en la tabla (la vista la enfoca) y
pulsa **Quitar selección y restaurar vista**.

### T5 — Electrodos (máx. 5 min)

**Consigna:** *"Haga visible el interior del cerebro para ver los electrodos de
profundidad. ¿Cómo se llama el electrodo que entra por el polo temporal? Luego
oculte los electrodos del cuero cabelludo."*

**Éxito (los tres):** baja la **opacidad de la corteza**; identifica el
electrodo **TP** pasando el cursor sobre él; desmarca **Mostrar EEG de
superficie**.

### T6 — Preparar un paciente nuevo (máx. 6 min)

**Consigna:** *"Prepare el procesamiento de un paciente nuevo, con ID
«paciente 01», usando la imagen T1 y las características que están en la
carpeta materiales. Deje todo listo para empezar, pero no lo inicie."*

Entregue por escrito las rutas:
* T1: `<FreeSurfer>/subjects/fsaverage/mri/T1.mgz`
* Características: `materiales/caracteristicas_validas.csv` (copia de
  `Visualizacion/Resources/Demo/caracteristicas_demo.csv`)

**Éxito:** el paso 4 muestra **Procesar MRI nuevo: ✓ listo**. Para lograrlo
debe darse cuenta de que el ID no admite espacios (por ejemplo, `paciente01` o
`paciente_01`).

*Si pulsa el botón, el diálogo de confirmación permite cancelar. Si lo inicia,
anótelo como error crítico y pulse **Cancelar procesamiento**.*

### T7 — Recuperarse de un error (máx. 5 min)

**Consigna:** *"Ahora visualice el paciente de ejemplo usando el archivo de
características `materiales/caracteristicas_con_error.csv`. Si algo falla,
explique qué pasa y cómo lo solucionaría."*

Antes de leerla: restaure en el paso 2 el ID `fsaverage_demo` (o pulse de nuevo
**Cargar datos de demostración**) y deje que la persona cambie solo el archivo de
características.

**Éxito:** selecciona el archivo, pulsa **Visualizar paciente ya procesado**,
lee el mensaje y explica que los decimales usan punto en vez de coma (o propone
cambiar el separador). No es necesario que edite el archivo.

### T8 — Recuperar los resultados (máx. 3 min)

**Consigna:** *"Cierre el panel de resultados de la derecha. Vuelva a abrirlo y
después abra la carpeta donde quedaron guardados los resultados del paciente."*

**Éxito:** usa **Mostrar panel de resultados** y **Abrir carpeta del
paciente** (sección 5), y señala `predicciones_soz_modelo.csv`.

## 7. Métricas

| Dimensión | Métrica | Cómo se registra | Meta orientativa |
|---|---|---|---|
| Eficacia | Tasa de éxito por tarea: 1 completada, 0,5 con ayuda o parcial, 0 fallida. | Hoja de observación. | ≥ 80 % por tarea. |
| Eficiencia | Tiempo por tarea (s). | Cronómetro o grabación. | Por debajo del máximo en ≥ 80 % de los participantes. |
| Eficiencia | Errores (acciones que no llevan al objetivo) y ayudas del moderador. | Hoja de observación. | Mediana ≤ 1 por tarea. |
| Satisfacción | SEQ por tarea (1–7). | Tras cada tarea. | Media ≥ 5,5. |
| Satisfacción | SUS (0–100). | Al final. | Media ≥ 68 (promedio de la industria); ≥ 80 excelente. |
| Cualitativo | Comentarios, dudas y expectativas del *think-aloud*. | Notas y grabación. | — |

## 8. Análisis

### 8.1 SUS

Para cada participante, con respuestas de 1 a 5:

* ítems impares (1, 3, 5, 7, 9): puntaje − 1;
* ítems pares (2, 4, 6, 8, 10): 5 − puntaje;
* sumar los 10 valores y multiplicar por 2,5 → SUS de 0 a 100.

`plantilla_resultados_sus.csv` tiene una columna para el resultado. En Excel:
`=((B2-1)+(5-C2)+(D2-1)+(5-E2)+(F2-1)+(5-G2)+(H2-1)+(5-I2)+(J2-1)+(5-K2))*2,5`
(con las respuestas de los ítems 1–10 en las columnas B a K).

Un SUS de 68 es el promedio de cientos de estudios; por encima de 80 está
entre el 10 % mejor. Informe la media, la desviación estándar y, si hay al menos
5 participantes, el intervalo de confianza del 95 %.

### 8.2 Tareas

Por tarea: tasa de éxito (con su intervalo de confianza; con muestras pequeñas,
el método de Wilson o el ajustado de Wald), mediana del tiempo y del número de
errores, media del SEQ. Compare perfiles A y B.

### 8.3 Problemas encontrados

Cada problema observado se anota con la tarea, cuántos participantes lo
tuvieron y su gravedad (escala de Nielsen):

| Gravedad | Significado |
|---|---|
| 0 | No es un problema de usabilidad. |
| 1 | Cosmético: arreglar si hay tiempo. |
| 2 | Menor: prioridad baja. |
| 3 | Mayor: prioridad alta. |
| 4 | Catastrófico: arreglar antes de entregar. |

Priorice por gravedad × frecuencia, corrija y, si es posible, repita la prueba
con nuevos participantes para comprobar que la corrección funciona.

## 9. Informe

1. Resumen ejecutivo (3–5 hallazgos principales y SUS medio).
2. Participantes (tabla anonimizada: perfil, experiencia con Slicer y
   FreeSurfer).
3. Resultados por tarea (tabla de métricas del apartado 7).
4. SUS (media, DE, IC 95 %, comparación con 68).
5. Problemas de usabilidad (tabla con gravedad, frecuencia, evidencia o cita del
   participante y propuesta de solución).
6. Cambios realizados y pendientes.

## Referencias

* ISO 9241-11:2018. *Ergonomics of human-system interaction — Part 11:
  Usability: Definitions and concepts.*
* Brooke, J. (1996). SUS: A "quick and dirty" usability scale. En *Usability
  Evaluation in Industry*.
* Sauro, J. y Dumas, J. (2009). Comparison of three one-question, post-task
  usability questionnaires. *CHI 2009* (SEQ).
* Nielsen, J. y Landauer, T. K. (1993). A mathematical model of the finding of
  usability problems. *INTERCHI '93*.
* Nielsen, J. (1994). *Usability Engineering* (escala de gravedad y heurísticas).
