# TODO - DesDuplicador

## Task: Mostrar "Network" en diálogo de selección de carpeta
- [x] Actualizar estrategia de selección para priorizar PowerShell + COM (`Shell.Application`) con foco en nodo Network.
- [x] Ajustar fallback de diálogos nativos para evitar bloqueo en nodo virtual.
- [ ] Corregir UX del botón verde “+ Agregar otra ruta” cuando el diálogo falla/cancela.
- [ ] Verificar respuesta del endpoint `/api/browse_folder` y documentar comportamiento.

## Progress
- [x] Plan aprobado por el usuario con enfoque PowerShell COM.
- [x] Implementación aplicada en `app.py` para usar `Shell.Application.BrowseForFolder`.
- [ ] Ajustes frontend/backend de manejo de error en curso.
