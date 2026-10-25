# Continuidade no Codex

Estado atual: v0.7.0, interface Qt 6 com cinco abas, transição de tema, perfis locais e consultas/gravações HID existentes. A aba Macros oferece gravação local de teclado/mouse, revisão de eventos, modos de execução como configuração e atribuição local aos cinco botões. Há conclusão assistida de atalhos incompletos, campos numéricos com −/+ e ícone transparente corrigido. A versão pública usa ilustração própria quando não há recursos opcionais locais.

As macros e suas atribuições ainda não são executadas no Linux nem gravadas no dispositivo. Os modos hold/toggle/repeat são apenas configurações locais. O gravador recebe entradas somente dentro da área indicada. Não apresentar essas funções como execução validada no X11.

Próxima etapa: obter evidências das rotinas de macros e de associação aos botões na engenharia reversa, mapear o formato e implementar codecs offline antes de habilitar escrita. Preserve backup, validação, releitura e compatibilidade dos perfis e macros existentes. Não inventar bytes, offsets ou limites de firmware.

Leia `AGENTS.md`, `README.md`, `docs/MACROS.md` e os testes antes de alterar o protocolo. Os arquivos privados da instalação Windows e o projeto Ghidra não acompanham o repositório. Não publicar esses recursos. A suíte de 141 testes usa receptor e entradas simulados; a execução física de macros continua pendente.

Repositório: https://github.com/Witorr/tubarao-atacante (branch principal `main`).
