# Tema de Colores y Estilos - Comparador de Respaldos NAS

## Paleta de Colores Principal

| Nombre | Hex | Uso |
|--------|-----|-----|
| Fondo pagina | `#1e1e1e` | body |
| Fondo secciones | `#252526` | .config, .grupo, .stats, .info-box, .flash, .flash-error |
| Fondo items | `#2d2d30` | .ruta-item, .archivo |
| Fondo inputs | `#3c3c3c` | input[type="text"], .btn-icon |
| Borde | `#3e3e42` | bordes de cajas, inputs, items |
| Texto principal | `#d4d4d4` | body, texto general |
| Texto secundario | `#808080` | .meta, .stat-label, .ruta-vacia, .modo-descripcion |

## Colores de Acento

| Nombre | Hex | Uso |
|--------|-----|-----|
| Azul | `#569cd6` | h1, .ruta-num, .btn-guardar, .btn-escanear, .progreso-pct, .progreso-barra-fill (inicio) |
| Verde | `#4ec9b0` | .btn-mantener, .btn-add, .estado-mantener, .progreso-barra-fill (fin) |
| Rojo | `#f48771` | .btn-eliminar, .btn-cancelar, .estado-eliminar, .flash-error |
| Amarillo | `#dcdcaa` | .btn-mover, .btn-browse, .estado-mover |
| Naranja | `#ce9178` | h2, .hash, .destino-config h4 |
| Morado | `#c586c0` | .ejecutar |
| Celeste | `#9cdcfe` | .ruta |

## Estilos de Componentes

### body
- font-family: 'Segoe UI', Arial, sans-serif
- margin: 20px
- background: #1e1e1e
- color: #d4d4d4

### h1
- color: #569cd6

### h2
- color: #ce9178
- font-size: 18px
- margin-top: 25px

### h3
- color: #ce9178 (en .destino-config h4)

### button (base)
- padding: 6px 14px
- border: none
- border-radius: 4px
- cursor: pointer
- font-size: 12px

### input[type="text"]
- width: 100%
- padding: 8px
- background: #3c3c3c
- border: 1px solid #3e3e42
- color: #d4d4d4
- border-radius: 4px
- margin: 5px 0

### .config
- background: #252526
- padding: 15px
- border-radius: 6px
- margin-bottom: 20px

### .grupo
- background: #252526
- border: 1px solid #3e3e42
- margin: 15px 0
- padding: 15px
- border-radius: 6px

### .grupo-header
- display: flex
- justify-content: space-between
- align-items: center
- margin-bottom: 10px

### .archivo
- display: flex
- justify-content: space-between
- align-items: center
- padding: 8px
- margin: 4px 0
- background: #2d2d30
- border-radius: 4px

### .archivo-info
- flex: 1

### .ruta
- color: #9cdcfe
- font-size: 13px

### .meta
- color: #808080
- font-size: 11px

### .acciones
- display: flex
- gap: 8px
- margin-left: 15px

### .hash
- font-family: monospace
- color: #ce9178
- font-size: 12px

### .stats
- display: flex
- gap: 20px
- margin: 15px 0
- flex-wrap: wrap

### .stat-box
- background: #252526
- padding: 15px
- border-radius: 6px
- min-width: 150px
- flex: 1

### .stat-num
- font-size: 24px
- font-weight: bold
- color: #569cd6

### .stat-label
- font-size: 12px
- color: #808080

### .flash
- background: #4ec9b0
- color: #000
- padding: 10px
- border-radius: 4px
- margin: 10px 0

### .flash-error
- background: #f48771
- color: #000
- padding: 10px
- border-radius: 4px
- margin: 10px 0

### .info-box
- background: #252526
- padding: 15px
- border-radius: 6px
- margin: 15px 0
- border-left: 4px solid #569cd6

### .ejecutar
- background: #c586c0
- color: #fff
- padding: 15px 30px
- font-size: 16px
- margin-top: 20px

## Estilos del Editor de Rutas

### .rutas-editor
- margin-top: 10px

### .ruta-item
- display: flex
- align-items: center
- gap: 8px
- margin: 6px 0
- padding: 8px
- background: #2d2d30
- border-radius: 4px
- border: 1px solid #3e3e42

### .ruta-item input
- flex: 1
- margin: 0

### .ruta-num
- color: #569cd6
- font-weight: bold
- min-width: 24px
- text-align: center

### .btn-icon
- background: #3c3c3c
- color: #d4d4d4
- border: 1px solid #3e3e42
- padding: 6px 10px
- font-size: 14px
- min-width: 32px

### .btn-icon:hover
- background: #4e4e4e

### .btn-add
- background: #4ec9b0
- color: #000
- padding: 8px 16px
- font-size: 13px
- margin-top: 8px

### .btn-browse
- background: #dcdcaa
- color: #000
- padding: 8px 16px
- font-size: 13px
- margin-top: 8px
- margin-left: 8px

### .btn-guardar
- background: #569cd6
- color: #fff
- padding: 12px 24px
- font-size: 14px
- margin-top: 12px

### .btn-cancelar
- background: #f48771
- color: #000
- padding: 12px 24px
- font-size: 14px
- margin-top: 12px
- margin-left: 8px

### .ruta-vacia
- color: #808080
- font-style: italic
- padding: 10px
- text-align: center

## Estilos de Estados

### .estado
- padding: 4px 8px
- border-radius: 3px
- font-size: 11px
- font-weight: bold

### .estado-mantener
- background: #4ec9b0
- color: #000

### .estado-eliminar
- background: #f48771
- color: #000

### .estado-mover
- background: #dcdcaa
- color: #000

### .estado-consolidar
- background: #569cd6
- color: #fff

## Estilos de la Barra de Progreso

### .progreso-container
- display: none
- background: #252526
- border: 1px solid #3e3e42
- border-radius: 6px
- padding: 15px
- margin: 15px 0

### .progreso-container.activo
- display: block

### .progreso-info
- display: flex
- justify-content: space-between
- margin-bottom: 8px
- font-size: 13px

### .progreso-mensaje
- color: #d4d4d4

### .progreso-pct
- color: #569cd6
- font-weight: bold

### .progreso-barra-bg
- background: #3c3c3c
- border-radius: 4px
- height: 24px
- overflow: hidden

### .progreso-barra-fill
- background: linear-gradient(90deg, #569cd6, #4ec9b0)
- height: 100%
- width: 0%
- border-radius: 4px
- transition: width 0.3s ease
- display: flex
- align-items: center
- justify-content: flex-end
- padding-right: 8px
- font-size: 11px
- color: #000
- font-weight: bold

### .progreso-ruta
- margin-top: 8px
- font-size: 11px
- color: #808080
- font-family: monospace
- white-space: nowrap
- overflow: hidden
- text-overflow: ellipsis

## Estilos de Configuracion de Destino

### .destino-config
- background: #2d2d30
- border: 1px solid #3e3e42
- border-radius: 6px
- padding: 15px
- margin-top: 15px

### .destino-config h4
- color: #ce9178
- margin-top: 0
- margin-bottom: 10px

### .modo-toggle
- display: flex
- align-items: center
- gap: 10px
- margin: 10px 0
- padding: 10px
- background: #252526
- border-radius: 4px
- cursor: pointer

### .modo-toggle input[type="checkbox"]
- width: 18px
- height: 18px
- cursor: pointer

### .modo-toggle label
- cursor: pointer
- font-size: 13px

### .modo-activo
- border: 1px solid #4ec9b0

### .modo-descripcion
- font-size: 11px
- color: #808080
- margin-left: 28px
