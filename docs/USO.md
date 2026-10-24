> Edição pública: a imagem do fabricante é opcional e não acompanha o repositório. A ilustração própria é exibida automaticamente. Consulte assets/README.md na raiz.

# Tubarão Atacante · Attack Shark X11 para Linux

**Versão 0.6.0 — interface Qt 6, animação de tema e antialiasing — CachyOS / Arch Linux, receptor USB 2.4 GHz `1D57:FA60`.**

Configurador nativo em Python com Qt 6/PySide6 com quatro telas: **Mouse**, **DPI**, **Iluminação** e **Perfis**. Inclui os sete modos dos anexos, velocidade, cor global, cores por estágio e uma prévia animada local. A edição de DPI preserva o modo de iluminação já escolhido.

## Interface e identidade

Nome do software: **Tubarão Atacante**. A marca mantém a mascote enviada pelo usuário e usa **Google Sans** na tipografia do nome. A fonte oficial e sua licença OFL estão incluídas; não é necessário instalá-la para abrir o programa. O Qt carrega a fonte apenas neste processo. O nome no cabeçalho também possui uma versão renderizada para preservar sua aparência.

A imagem do mouse é o recurso original do software Attack Shark X11. Seu hash coincide com o inventário da engenharia reversa anterior. A imagem inclui a numeração vermelha original dos botões; essa numeração é ilustrativa nesta versão. Os detalhes da extração e da análise do XML original estão em `research/INTERFACE.md`.

Os seis estágios de DPI agora usam sliders verticais, campos de valor, amostras de cor e seleção do estágio ativo, seguindo a organização dos controles originais. Foram removidas as caixas individuais que fragmentavam as linhas. A largura útil é limitada a 1280 px e centralizada em monitores maiores.

As abas **Mouse**, **DPI** e **Iluminação** mantêm cartões e estados de foco Material 3. Os valores de DPI, polling e iluminação aparecem em uma faixa compacta. Os botões aceitam Tab, Enter e Espaço. Os sliders aceitam setas, Home e End; nos controles verticais, cima aumenta e baixo diminui o DPI.

A aba Perfis foi adicionada nesta etapa. Botões laterais e macros entram na etapa seguinte, após a validação dos perfis. Os codecs HID e os relatórios usados continuam os mesmos.

## Abrir no CachyOS / Arch

Feche a versão anterior e extraia **todo o ZIP em uma pasta nova**, mantendo os arquivos e as pastas `branding/`, `assets/` e `fonts/` juntos. Esta versão migra a interface de Tk para **Qt 6/PySide6**.

Instale a dependência pelo repositório do sistema:

```bash
sudo pacman -S --needed pyside6
```

Na pasta extraída, use o Python do sistema:

```bash
/usr/bin/python attack_shark_x11.py
```

Ou execute `sh iniciar.sh`. O iniciador usa `/usr/bin/python` para encontrar o PySide6 instalado pelo pacman. A interface informa a dependência ausente caso seja aberta em um Python que não a possua. Os comandos de terminal continuam funcionando sem carregar Qt.

Clique em **Conectar**. A abertura da janela, a troca de telas e a mudança de tema não enviam ajustes ao mouse. Use **Aplicar** na seção correspondente para gravar.

A regra udev já instalada continua válida. Execute como usuário normal. Os perfis e a preferência de tema continuam nos mesmos arquivos, sem conversão e sem serem substituídos ao extrair o ZIP.

Referência do pacote: https://archlinux.org/packages/extra/x86_64/pyside6/

## Tema e controles visuais

O controle de sol/lua no topo é um componente nativo `ThemeSwitch`, com movimento deslizante de 360 ms inspirado no vídeo enviado. O fundo, os cartões, os textos, os campos e as cores de destaque também fazem uma transição gradual sincronizada com o controle. Uma nova mudança antes do fim da animação parte do estado visual atual, sem saltar para o início. Clique nele, use Espaço ou Enter para alternar claro/escuro. O vídeo não é reproduzido dentro do aplicativo.

**Auto** acompanha a preferência do sistema. A detecção usa primeiro o portal de aparência do Linux e, quando necessário, as configurações KDE/GNOME ou GTK. A verificação ocorre em segundo plano a cada cinco segundos; não bloqueia as operações do mouse. Se nenhuma preferência puder ser obtida, usa o tema claro. A preferência manual ou automática é salva em `~/.config/tubarao-atacante/appearance.json` (respeita `XDG_CONFIG_HOME`) e restaurada na próxima abertura.

O tema escuro usa uma paleta inspirada no Dracula: fundo `#282A36`, superfícies `#353747`, seleção `#44475A`, texto `#F8F8F2`, destaque `#BD93F9` e confirmação `#50FA7B`. Logo e nome têm versões próprias para o fundo escuro. Trocar o tema não envia ajustes ao mouse e preserva os campos em edição e as cores dos estágios.

As áreas de rolagem em Perfis usam controles Qt estilizados com indicador fino arredondado, arraste, página, roda e teclado. Quando o conteúdo cabe inteiro, o indicador desaparece. Cartões, botões, sliders e switch usam desenho Qt com antialiasing. A imagem do dispositivo usa transformação suave. O Qt também trata escalas HiDPI do sistema. A interface mantém a linguagem visual Material e a paleta Dracula.

A prévia do LED agora recolore apenas a máscara dos pixels da abertura original. As versões de exibição removem a cor ciano fixa nessa área antes de aplicar a cor selecionada; as bordas têm suavização proporcional à escala. Isso evita o segundo traço sobreposto. `assets/x11-original.png` permanece intacto. A animação continua sendo ilustrativa, sem medir a luz física do dispositivo.

Referências de design: https://api.flutter.dev/flutter/material/Scrollbar-class.html e https://draculatheme.com/spec

## Perfis de configuração

1. Conecte o X11 e ajuste os campos nas abas **Mouse**, **DPI** e **Iluminação**.
2. Abra **Perfis → Criar**, informe um nome e confirme. Isso salva os campos exibidos, incluindo alterações ainda não aplicadas ao mouse.
3. Selecione um perfil na lista para conferir DPI, estágio ativo, cores, polling e iluminação.
4. **Carregar para edição** copia os ajustes salvos para os campos das outras abas. Nenhum ajuste é enviado ao mouse; os indicadores superiores continuam mostrando a última leitura real.
5. Depois de editar os campos, use **Salvar ajustes atuais** para atualizar o perfil selecionado. Há confirmação antes de substituir o conteúdo salvo.
6. **Aplicar ao mouse** envia o perfil **salvo**, não eventuais edições ainda não salvas. O software lê os relatórios atuais, valida todos os valores, salva um backup e aplica os campos suportados. Confirma os três relatórios por releitura.

**Duplicar**, **Renomear** e **Excluir** afetam apenas os perfis deste computador. Excluir pede confirmação e não altera a configuração do mouse. A lista pode ser consultada e organizada sem o mouse conectado; criar, salvar campos, carregar para edição e aplicar exigem conexão nesta versão.

Os perfis ficam em `~/.config/tubarao-atacante/profiles.json`, ou em `$XDG_CONFIG_HOME/tubarao-atacante/profiles.json` quando definido. São predefinições locais, não slots extras de memória do mouse. Não são aplicados automaticamente ao abrir o aplicativo, selecionar um nome ou iniciar um jogo. A interface requer PySide6 nesta versão; o formato dos perfis locais permanece o mesmo.

O arquivo tem escrita atômica, permissões privadas e lock entre instâncias. Nomes são únicos sem distinguir maiúsculas/minúsculas. Dados inválidos ou versões de arquivo desconhecidas são recusados, mantendo o arquivo existente. Os perfis contêm apenas configurações semânticas validadas; não aceitam pacotes HID arbitrários.

A aplicação preserva campos desconhecidos do dispositivo, como parâmetros de repouso e debounce, e não altera quais estágios estão habilitados. Um perfil incompatível com os estágios habilitados é recusado antes da gravação. Se a velocidade estiver marcada para preservar, permanece a velocidade atual do mouse.

A transação do mouse não é atômica: uma desconexão pode deixar parte dos ajustes aplicada. Não há repetição nem restauração automática. O diagnóstico informa a falha e o caminho do backup; consulte novamente antes de repetir.

## Iluminação

| Nome na interface | Original | Cor usada | Velocidade |
|---|---|---|---|
| Desligado | LED Off | Preserva as cores e desliga o LED | Preservada |
| Estático | Static | Cor global | Preservada |
| Respiração | Breathing | Cor global | 1 a 5 |
| Neon | Neon | Ciclo de cores do efeito | 1 a 5 |
| Respiração multicolor | Color Breathing | Ciclo de cores do efeito | 1 a 5 |
| Cor do DPI | Static DPI | Cor do estágio ativo | Preservada |
| Respiração do DPI | Breathing DPI | Cor do estágio ativo | 1 a 5 |

1. Abra **Iluminação** e selecione o modo.
2. Ajuste a velocidade nos modos animados. **1 é lento e 5 é rápido.**
3. Nos modos Estático e Respiração, clique na cor global para abrir o seletor RGB/hexadecimal.
4. Nos modos que seguem o DPI, defina as cores na aba **DPI**.
5. Clique em **Aplicar iluminação**.

Os controles sem efeito no modo escolhido ficam desabilitados. A prévia é ilustrativa e local: não envia alterações ao mouse, não é uma captura do LED e sua temporização não comprova a duração exata dos efeitos do firmware.

## DPI e polling

Na aba **DPI**, use os controles deslizantes ou digite um DPI exato suportado, selecione o estágio ativo, escolha suas cores e clique em **Aplicar estágios**. Os controles deslizantes usam a lista de valores cuja codificação é conhecida e não ambígua. Valores digitados inválidos são recusados, não arredondados silenciosamente.

Na aba **Mouse**, ajuste o polling para 125, 250, 500 ou 1000 Hz. A alteração só é enviada ao clicar em **Aplicar polling**.

Os indicadores superiores mostram a última configuração lida/confirmada. A imagem do mouse é o recurso original do fabricante; a cor sobre o LED é uma prévia local.

## Comandos de terminal

Consulta completa, sem gravar ajustes:

```bash
python attack_shark_x11.py status
python attack_shark_x11.py lighting-status
```

Exemplos de **alterações** independentes:

```bash
# Respiração roxa, velocidade intermediária
python attack_shark_x11.py set-lighting breathing --speed 3 --rgb '#9c59ff'

# Neon com velocidade alta
python attack_shark_x11.py set-lighting neon --speed 5

# Iluminação seguindo a cor do estágio ativo
python attack_shark_x11.py set-lighting static-dpi

# Desligar a iluminação
python attack_shark_x11.py set-lighting off

python attack_shark_x11.py set-polling 1000
python attack_shark_x11.py set-stage 2
python attack_shark_x11.py set-dpi 1 1600
python attack_shark_x11.py set-color 2 '#79c400'
```

`set-stage`, `set-dpi` e `set-color` preservam o modo de iluminação selecionado. O comando de compatibilidade `follow-stage-color` continua disponível e seleciona explicitamente o modo Cor do DPI.

## Verificação, cópias anteriores e diagnóstico

Antes de qualquer gravação, a aplicação lê e valida os relatórios envolvidos. Salva uma cópia anterior, monta a alteração preservando os demais campos e faz a releitura depois de enviar. O relatório de perfil 04 precede o relatório de iluminação 05, com intervalo entre os envios.

Alterar velocidade não sobrescreve o nibble usado por suspensão; alterar cor global não sobrescreve debounce, suspensão, velocidade ou padding. Os parâmetros não expostos continuam vindo da configuração lida do dispositivo. A soma de verificação é recalculada conforme o software Windows analisado.

As cópias ficam em `$XDG_STATE_HOME/attack-shark-x11`, normalmente `~/.local/state/attack-shark-x11`, com permissão 0600. Os backups de operações de iluminação incluem o relatório 05 anterior. Não há restauração automática nem replay genérico de frames.

- `verified`: os frames esperados coincidiram com a releitura.
- `unchanged`: os valores já estavam configurados; nenhuma gravação de ajuste necessária.
- `verification_mismatch`: o dispositivo respondeu com diferenças; consulte os detalhes.
- `error`: a operação não pôde ser concluída; consulte novamente antes de repetir.

O botão **Diagnóstico** permite copiar o diagnóstico da última operação, incluindo valores e erros. Se a variante de checksum do firmware não corresponder à observada no software analisado, a operação é interrompida antes da gravação dos ajustes. Não há tentativas automáticas de adivinhar variantes, repetir gravações ou restaurar configurações.

O acesso entre instâncias desta aplicação é serializado com um lock local. Esse lock não controla programas de terceiros. Se fechar a janela durante uma operação, ela aguarda a resposta antes de encerrar.

## Validação e limites

- 98 testes automatizados de protocolo, transações e armazenamento de perfis passaram.
- As quatro telas foram renderizadas e inspecionadas com Qt 6.12; foram conferidas também em janelas de 1000×760 e 1920×1000 e com renderização HiDPI de fator 2.
- Os sete modos foram acionados pela interface com um receptor simulado. Seletor de cores, controles condicionais e posições dos sliders também foram verificados. Os novos sliders foram exercitados por eventos de mouse e teclado, incluindo o bloqueio quando desabilitados; a edição local não alterou os frames do receptor.
- As consultas, o polling e a interpretação dos estágios foram validados pelo usuário no X11. A versão anterior também recebeu confirmação por releitura de perfil e iluminação.
- O usuário confirmou o funcionamento das funcionalidades da versão anterior. Esta revisão altera a apresentação. Os testes desta versão usaram receptor simulado; não houve novo teste físico do X11 neste ambiente.

```bash
QT_QPA_PLATFORM=offscreen /usr/bin/python -m unittest discover -v
```

As imagens `preview-overview.png`, `preview-dpi.png` e `preview-lighting.png` e `preview-profiles.png` mostram a aplicação real com dados simulados para revisão visual. Não são capturas do dispositivo do usuário. `preview-theme-transition.gif` é uma captura da transição real da interface Qt, em ambas as direções; não é o vídeo de referência embutido no programa.

Esta etapa não implementa Bluetooth, cabo USB, macros ou bateria. Também não envia firmware, comandos de pareamento ou reset.

## Permissões em uma instalação nova

A regra `70-attack-shark-x11.rules` já foi aplicada pelo usuário. Se for reproduzir em outra máquina:

```bash
sudo install -m 644 70-attack-shark-x11.rules /etc/udev/rules.d/70-attack-shark-x11.rules
sudo udevadm control --reload-rules
```

Depois, desconecte e reconecte o receptor. Não é preciso executar o aplicativo como root.

## Evidências e atribuição

A base foi reconstruída com Ghidra a partir da instalação Windows do usuário, especialmente as rotinas da família MS_4 `FUN_004a1970`, `FUN_004a2050`, `FUN_004a1d20`, `FUN_004a38a0` e `FUN_004a3f50`. As leituras reais fornecidas pelo usuário confirmaram a estrutura dos relatórios 04, 06 e A0.

A tabela de conversão de DPI foi adaptada de OpenSharkX11, MIT, de Clevs; o aviso completo está junto aos dados em `x11_protocol.py`. Os nomes e controles dos modos também foram comparados com as referências e os anexos do software original.

- https://github.com/clevim/OpenSharkX11/blob/main/src-tauri/src/protocols/dpi.rs
- https://github.com/clevim/OpenSharkX11/blob/main/src-tauri/src/protocols/user_prefs.rs
- https://docs.kernel.org/hid/hidraw.html

O validador do relatório 05 usa a variante de soma de 16 bits observada no binário instalado e preservada na versão 0.1.1. Não substitui esse formato por variantes descritas em projetos de terceiros.
