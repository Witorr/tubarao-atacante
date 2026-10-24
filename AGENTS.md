# Instruções para agentes e colaboradores

## Objetivo
Configurador livre do Attack Shark X11 para CachyOS/Arch Linux, receptor 1D57:FA60. UI Qt 6/PySide6; backend Python padrão com hidraw/ioctl. Interface em português.

## Autoridade técnica
- `attack_shark_x11.py`: validação, transações, backups, comandos e lançamento.
- `x11_protocol.py`: descoberta, descritores e consultas; tabela de DPI MIT atribuída.
- `x11_profiles.py`: armazenamento local com validação, lock e escrita atômica.
- `x11_ui.py`: Qt, tarefas fora da thread gráfica, animação e renderização.
- `x11_appearance.py`: preferência de tema e integração com Linux.

## Restrições de implementação
Não alterar VID/PID, report lengths, checksums ou ordem de escrita sem evidências. Reports 04/56B, 05/15B, 06/9B e preparação A0/8B. Report 04 precede 05. Manter backup antes de gravação, validação de todos os campos e releitura. Não adicionar reset, pareamento ou atualização de firmware por hipótese. Não usar loops de tentativas de escrita ou restaurar automaticamente.

Não acessar Qt em workers. Capturar os dados na thread visual antes de iniciar transações. Manter fechamento aguardando operações HID ativas. Perfis e preferência de tema existentes devem continuar legíveis. Nunca incluir perfis pessoais, backups, tokens ou caminhos pessoais nos commits.

## Verificação
`QT_QPA_PLATFORM=offscreen python -m unittest discover -v`
Instalação de desenvolvimento: `python -m pip install PySide6-Essentials` em um ambiente virtual. Para o usuário final no CachyOS: pacote `pyside6` do pacman.

## Recursos e licenças
Não publicar instaladores, binários proprietários, bancos Ghidra ou imagens originais da Attack Shark. A ilustração própria é o padrão da distribuição pública. Arquivos opcionais de recursos proprietários são ignorados pelo git. Preservar MIT de Clevs, OFL das fontes e os créditos do template.

## Próxima etapa
Mapear botões laterais e macros com evidências antes de habilitar escrita. O projeto ainda não implementa essas funções. Não apresentar uma funcionalidade simulada como validada no hardware. Entregar mudanças incrementais e separar testes simulados de validações físicas.
