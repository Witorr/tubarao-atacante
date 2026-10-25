# Componentes Qt 6 — v0.7.0

A interface está em `x11_ui.py`. A dependência é PySide6, instalada pelo pacman no CachyOS/Arch.

- `Theme(QObject)`: paletas, animação de cores de 360 ms com `QVariantAnimation` e curva InOutCubic, consulta da preferência do sistema em tarefa separada e persistência da escolha.
- `ThemeSwitch(QAbstractButton)`: controle sol/lua desenhado com QPainter Antialiasing. O deslocamento do indicador usa uma animação Qt independente e sincronizada com o tema. Clique, Espaço ou Enter alternam o estado. Mudanças rápidas interrompem a animação a partir da posição atual.
- `Button(QPushButton)`, `Card(QWidget)` e `SmoothSlider(QSlider)`: desenho de curvas em coordenadas fracionárias, com antialiasing, estados de foco/interação e teclado nativo.
- `BrandImage(QWidget)`: transição de opacidade entre as versões clara e escura da identidade.
- `MousePreview(QWidget)`: QImage com máscara da abertura do LED e escalonamento suave. O arquivo original da imagem é preservado.
- `ModernApplication(QMainWindow)`: cinco páginas, diálogos Qt, tarefas HID fora da thread visual e fechamento aguardando a transação ativa.

`x11_appearance.py` contém somente paletas e preferências do Linux, sem dependência de Tk ou Qt. `x11_profiles.py` e o protocolo HID foram mantidos.

O vídeo de referência não é necessário em execução. Não há captura da tela do usuário nem reprodução de um vídeo para simular a transição: os widgets e suas cores são animados pelo Qt. Pillow só foi usado na preparação dos recursos e nas capturas de desenvolvimento, não é dependência do aplicativo.

Referências:
https://doc.qt.io/qtforpython-6/PySide6/QtCore/QPropertyAnimation.html
https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPainter.html

- `MacroPage(QWidget)`: editor de eventos de teclado/mouse, modos locais, validação e salvamento com atribuição atômica.
- `ButtonMap(QWidget)` e `AssignmentDialog(QDialog)`: mapa de cinco botões com setas e cartões acessíveis; biblioteca de macros sem dropdown.
- `RecordingDialog` e `CaptureSurface`: gravação restrita à área dedicada, com captura de tempos e encerramento ao perder foco.
- `Recording`: estado e limites do gravador, sem acesso a hardware ou injeção de entradas.
- `MacroStore`: esquema 3 com leitura dos esquemas anteriores, lock, escrita atômica e referências entre macros e atribuições.
- `NumberField(QSpinBox)` e `StepButton`: campos numéricos com desenho antialiasing, botões −/+, foco, digitação e comportamento nativo de teclado.

O ícone global da aplicação e da janela usa `branding/juliet-icon.png`, transparente, de 256×256 px. O desenho original vem de `juliet-logo.svg`; renderizá-lo não é necessário para executar o programa.
