#-----------------------------------------------------------------------------
set(MODULE_NAME Visualizacion)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/requirements.txt
  Resources/Docs/MANUAL_USUARIO.md
  Resources/Docs/imagenes/panel_modulo.png
  Resources/Docs/imagenes/paso_ejecutar.png
  Resources/Docs/imagenes/panel_resultados.png
  Resources/Docs/imagenes/resultados_3d.png
  Resources/Docs/imagenes/seccion_resultados.png
  Resources/Demo/caracteristicas_demo.csv
  Resources/Demo/eeg_superficie_demo.csv
  Resources/Demo/seeg_dipolos_demo.tsv
  )

#-----------------------------------------------------------------------------
# Carpetas hermanas que el módulo usa en tiempo de ejecución. Se copian a
# ${MODULE_NAME}Lib/ junto a ${MODULE_NAME}.py, en el árbol de build y en el
# paquete instalado; carpetaExtension() en ${MODULE_NAME}.py las busca ahí.
set(MODULE_LIB_DIR ${MODULE_NAME}Lib)

set(MODULE_LIB_FILES
  Pipeline/pipeline_principal.py
  Pipeline/input_t1.py
  Pipeline/conform.py
  Pipeline/talairach.py
  Pipeline/nuintensitycor.py
  Pipeline/normalization.py
  Pipeline/skullstrip.py
  Pipeline/gcareg.py
  Pipeline/canorm.py
  Pipeline/careg.py
  Pipeline/calabel.py
  Pipeline/aseg_presurf.py
  Pipeline/normalization2.py
  Pipeline/maskbfs.py
  Pipeline/segmentation.py
  Pipeline/mri_edit_wm_with_aseg.py
  Pipeline/mri_pretess.py
  Pipeline/fill.py
  Pipeline/mri_tesselate.py
  Pipeline/mris_extract_main_component.py
  Pipeline/smooth1.py
  Pipeline/inflate1.py
  Pipeline/qsphere.py
  Pipeline/fix.py
  Pipeline/white.py
  Pipeline/smooth2.py
  Pipeline/inflate2.py
  Pipeline/sphere2.py
  Pipeline/surfreg.py
  Pipeline/cortparc.py
  Pipeline/cortparc2.py
  Pipeline/pial.py
  Inferencia/inferencia_ml.py
  Inferencia/soz_inferencia.py
  Inferencia/soz_extratrees_sEEG_15pacientes.joblib
  VisualizacionML/visualizacion_ml.py
  VisualizacionML/visualizacion_electrodos.py
  VisualizacionML/visualizacion_electrodos_barra.py
  )

foreach(lib_file ${MODULE_LIB_FILES})
  get_filename_component(lib_file_dir ${lib_file} DIRECTORY)
  configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/../${lib_file}
    ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/${MODULE_LIB_DIR}/${lib_file}
    COPYONLY
    )
  install(
    FILES ${CMAKE_CURRENT_SOURCE_DIR}/../${lib_file}
    DESTINATION ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/${MODULE_LIB_DIR}/${lib_file_dir}
    COMPONENT RuntimeLibraries
    )
endforeach()

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)

  # Register the unittest subclass in the main script as a ctest.
  # Note that the test will also be available at runtime.
  slicer_add_python_unittest(SCRIPT ${MODULE_NAME}.py)

  # Additional build-time testing
  add_subdirectory(Testing)
endif()
