cmake_minimum_required(VERSION 3.28.0...3.28.0 FATAL_ERROR)

project(ClasificacionZE)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/juan2812006-arch/SlicerClasificacionZE")
set(EXTENSION_CATEGORY "Neuroimaging")
set(EXTENSION_CONTRIBUTORS "Juan Andrés Martínez Castellanos (Pontificia Universidad Javeriana), Ana Rebeca Torres Vargas (Pontificia Universidad Javeriana)")
set(EXTENSION_DESCRIPTION "Epileptogenic zone classification: processes a T1 MRI with FreeSurfer, predicts epileptogenic cortical regions (Destrieux atlas) from sEEG markers with a machine-learning model and shows them in 3D with scalp EEG and SEEG electrodes. User interface in Spanish. License: PolyForm Noncommercial 1.0.0 (no commercial use).")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/juan2812006-arch/SlicerClasificacionZE/main/Visualizacion/Resources/Icons/Visualizacion.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/juan2812006-arch/SlicerClasificacionZE/main/Visualizacion/Resources/Docs/imagenes/resultados_3d.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(Visualizacion)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
