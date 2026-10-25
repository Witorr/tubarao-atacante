# Macros: implementação e evidências

## Etapa disponível

O editor permite gravar, nomear, atualizar, excluir e ordenar sequências de teclado e mouse, atrasos e modos de execução. Funciona sem receptor conectado. `x11_macros.py` define um formato semântico versionado e armazenamento local; `x11_macro_ui.py` implementa a aba Qt. Não existe codificador de macros HID ou execução de entradas nesta etapa.

O esquema local não é um formato do firmware. Os limites do editor são explicitamente locais. Teclas devem estar balanceadas, sem soltura anterior ao pressionamento, pressionamento duplicado ou tecla mantida ao final. Ações desconhecidas, comandos arbitrários e campos extras são recusados. Alterações não salvas são protegidas ao trocar de macro, criar outra ou fechar a aplicação.

`macros.json` usa permissão 0600, substituição atômica, fsync e lock exclusivo entre instâncias. Arquivos inválidos ou com versão desconhecida são preservados. Não altera `profiles.json` nem associa automaticamente macros a perfis existentes.

## Mapa visual dos cinco botões

A aba abre no mapa do dispositivo, com cinco cartões, setas e marcadores clicáveis. Os números correspondem às posições da referência visual: clique esquerdo (1), direito (2), clique da roda (3), lateral superior (4) e lateral inferior (5). Esses números não representam códigos HID confirmados. Os cartões também aceitam Tab e Espaço.

Cada botão permite criar uma gravação ou associar uma macro salva da biblioteca, apresentada como lista. O dropdown e as opções prontas Copiar/Colar foram removidos. Referências antigas a esses atalhos continuam legíveis para preservar atribuições já salvas; não aparecem como novas opções na interface. Renomear uma macro mantém as associações pelo ID; excluí-la remove suas associações na mesma escrita atômica. Descartar o diálogo não grava nada.

O arquivo local passa ao esquema 3, com eventos de teclado/mouse, modo opcional e `assignments` para os cinco botões. Arquivos dos esquemas 1 e 2 continuam legíveis e são atualizados apenas na próxima gravação. Sequências antigas sem modo mantêm sua repetição numérica ao abrir o editor. Dados inválidos e referências inexistentes são recusados. A imagem original é opcional: o mapa também desenha uma ilustração própria para a edição pública.

## Gravador e revisão

`x11_recording.py` controla temporização e limites sem acesso a dispositivos. `x11_macro_recorder.py` captura eventos Qt somente dentro da área explícita de gravação. Não instala listeners globais nem intercepta entradas em outros aplicativos. Cliques dos controles Gravar/Parar/Usar gravação não integram a macro. Perder foco ou chegar ao limite encerra a gravação e completa solturas pendentes, com aviso. Uma pausa longa é dividida em eventos de até 60 segundos. O primeiro evento não recebe atraso inicial.

São representados pressionamento/soltura de teclas, cinco botões de mouse e rolagem horizontal/vertical. Teclas fora do vocabulário inicial são preservadas como identificadores Qt validados (`QtKey:N`), sem inventar códigos HID do X11. Esc e Tab são graváveis. Não há captura de movimento de ponteiro ou commits de métodos de entrada. A distinção entre modificadores direitos/esquerdos depende do código nativo disponibilizado pelo backend Qt; quando ausente, usa a identificação genérica. Repetição automática de tecla é ignorada. Rolagem preserva os valores de `angleDelta`, em unidades Qt, sem tratá-los como pixels ou bytes do firmware.

A revisão permite regravar um evento, ajustar atrasos, inserir outra gravação/pausa e excluir ou reordenar passos. A validação de balanceamento permanece obrigatória. Os modos `once`, `hold`, `toggle` e `repeat` são apenas intenções armazenadas. Nenhum agendador, loop, disparo global, injeção de teclado ou gravação no dispositivo foi adicionado. Não é oferecido loop infinito ativo.

Criar a partir do mapa salva a macro e sua associação em uma única escrita atômica. Cancelar uma gravação não altera o rascunho; cancelar a atribuição não grava nada. Perfil por aplicativo e troca automática de perfis não fazem parte desta etapa.

Ao salvar um rascunho com pressionamentos sem soltura, `IncompleteMacroError` identifica as solturas pendentes. A interface prepara uma sequência completa, valida os limites novamente e oferece adicioná-las ao final em ordem inversa ao pressionamento. A confirmação é explícita; cancelar não altera o rascunho nem as atribuições. Outros erros continuam bloqueando o salvamento e são apresentados em uma janela. O armazenamento permanece estrito: não aceita sequências incompletas. Salvar e atribuir com sucesso retorna ao mapa e atualiza o cartão do botão.

APIs de referência: [QKeyEvent](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QKeyEvent.html) e [QWheelEvent](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QWheelEvent.html). O fluxo de produto segue o passo a passo fornecido pelo usuário; o endereço do guia MDBF retornou HTTP 404 nesta consulta.

## O que a análise disponível permite afirmar

O código atual e o relato compartilhado da engenharia reversa identificam a família MS_4 para o receptor X11 e sustentam as operações existentes de DPI, polling e iluminação. O relato cita um pacote com projeto Ghidra anotado, relatório técnico e scripts, mas esse pacote não está presente neste checkout. A conversa compartilhada acessível não forneceu um link utilizável para baixar o projeto Ghidra. `research/INTERFACE.md`, no pacote local anterior, documenta recursos visuais, não o protocolo de macros.

| Item | Evidência disponível | Estado |
| --- | --- | --- |
| Consulta e edição de DPI, polling e iluminação | Código e testes atuais dos relatórios 04/56B, 05/15B e 06/9B | Preservados |
| Formato de eventos de macro | Sem função decompilada ou captura disponível nesta etapa | Pendente |
| Comando de gravação/leitura de macro | Sem sequência documentada disponível | Pendente |
| Associação aos dois botões laterais | Sem offsets e valores confirmados disponíveis | Pendente |
| Slots, tamanho, repetição, atrasos e persistência no firmware | Não demonstrados pelo material acessível | Pendentes |

Não se deve deduzir um comando de macro a partir dos relatórios de DPI/iluminação. Os bytes desconhecidos desses relatórios continuam preservados pelas operações existentes.

## Material necessário para integrar o X11

Disponibilizar localmente o `AttackShark_Linux_engenharia_reversa.zip` ou exportações das funções decompiladas que tratam macros e associação de botões, com endereços e referências. Se houver capturas USB, comparar uma macro mínima (pressionar/soltar uma tecla), a mesma macro com atraso e a atribuição a cada botão lateral. Não publicar o executável, recursos proprietários ou banco Ghidra no repositório público.

A análise precisa identificar IDs e comprimentos dos relatórios, codificação de eventos/teclas, unidades de atraso, limites, fragmentação, checksums, ordem de envio, confirmação, leitura anterior e associação aos botões. Somente então implementar o codec offline com vetores reais, transações com backup e releitura e integração explícita com a interface.

## Validação

`test_macros.py` verifica sequências e limites, rejeição de dados inválidos, CRUD, isolamento dos perfis, permissões, falha de escrita atômica e acesso por duas instâncias. Os testes Qt verificam edição sem acesso ao receptor, persistência, reordenação e cancelamento do descarte. A suíte existente usa receptor simulado para as funções já implementadas.

As capturas da nova aba usam dados locais de exemplo, nos temas claro e escuro e em 1120×820 e 1000×760. Nenhuma macro foi enviada a hardware. A validação física futura deve conferir ambos os botões, tempos, repetição e comportamento após fechar o aplicativo e reconectar o receptor, sem pressupor persistência.
