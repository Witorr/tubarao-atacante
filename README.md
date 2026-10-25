<div align="center">
<img src="branding/juliet-logo.png" width="130" alt="Mascote Tubarão Atacante">

# Tubarão Atacante

**Seu Attack Shark X11 no Linux.** Configurador comunitário com interface Qt 6, linguagem visual Material e tema personalizável.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Qt](https://img.shields.io/badge/Qt-6%20%2F%20PySide6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-CachyOS%20%2F%20Arch-1793D1?style=for-the-badge&logo=archlinux&logoColor=white)
[![MIT](https://img.shields.io/badge/License-MIT-bd93f9?style=for-the-badge)](LICENSE)
[![Contribuições](https://img.shields.io/badge/PRs-bem--vindos-50fa7b?style=for-the-badge)](CONTRIBUTING.md)

[Instalação](#-instalando) · [Uso](#-usando) · [Contribuir](CONTRIBUTING.md) · [Licença](#-licença)
</div>

![Transição animada entre os temas claro e escuro, com dados simulados](preview-theme-transition.gif)

> Projeto independente, sem vínculo ou endosso da Attack Shark. Desenvolvido por engenharia reversa para permitir que a comunidade configure o X11 no Linux.

**Versão 0.7.0** · Cinco abas: Mouse, DPI, Iluminação, Perfis e Macros.

## Ajustes e melhorias

- [x] Consulta e aplicação de polling: 125, 250, 500 e 1000 Hz.
- [x] Seis estágios de DPI e cores por estágio.
- [x] Sete modos de iluminação, velocidade e cor global.
- [x] Perfis locais: criar, duplicar, renomear, excluir, salvar e aplicar.
- [x] Tema claro/escuro animado, modo automático e antialiasing.
- [x] Backup anterior à gravação e confirmação por releitura.
- [x] Gravador local de teclado/mouse, revisão de eventos, atrasos e modos de execução.
- [x] Mapa visual dos cinco botões, com criação e atribuição de macros da biblioteca.
- [x] Conclusão assistida de atalhos incompletos, confirmação de salvamento e atualização do mapa.
- [x] Campos numéricos de repetições e atrasos com botões −/+, digitação e teclado.
- [x] Ícone transparente de 256×256 px, sem faixas brancas, na janela e na aplicação.
- [ ] Aplicação das atribuições e execução das macros no mouse, incluindo os botões laterais.
- [ ] Perfis de macros por aplicativo e troca automática de perfil.
- [ ] Empacotamento e testes de hardware para outras variantes.

## 💻 Pré-requisitos

- Linux; foco de validação: CachyOS/Arch.
- Python 3.10 ou superior e PySide6.
- Attack Shark X11 com receptor USB 2.4 GHz `1D57:FA60`.
- Permissão de usuário para a interface hidraw do receptor.

Bluetooth, conexão por cabo, firmware, pareamento, bateria e outros modelos não são suportados nesta versão. Dispositivos da mesma marca podem compartilhar identificadores: compatibilidade não é garantida apenas pelo VID/PID.

## 🚀 Instalando

No CachyOS/Arch:

```bash
sudo pacman -S --needed git pyside6
git clone https://github.com/Witorr/tubarao-atacante.git
cd tubarao-atacante
/usr/bin/python attack_shark_x11.py
```

Para configurar permissões em uma instalação nova:

```bash
sudo install -m 644 70-attack-shark-x11.rules /etc/udev/rules.d/70-attack-shark-x11.rules
sudo udevadm control --reload-rules
```

Desconecte e reconecte o receptor. Execute o configurador como usuário normal.

## ☕ Usando

1. Clique em **Conectar** para ler as configurações reais.
2. Ajuste DPI, polling ou iluminação na aba correspondente.
3. Clique em **Aplicar** para enviar ao mouse.
4. Em **Perfis**, salve os ajustes e use **Aplicar ao mouse** para enviar o perfil salvo.

Carregar um perfil para edição e trocar o tema não gravam ajustes no mouse. Perfis são arquivos locais, não slots extras de memória interna. Uma falha de comunicação pode deixar uma aplicação parcialmente concluída; consulte novamente antes de repetir. Não há tentativas automáticas de restauração.

Consultas pelo terminal, sem gravar ajustes:

```bash
/usr/bin/python attack_shark_x11.py status
/usr/bin/python attack_shark_x11.py lighting-status
```

Configurações locais: `~/.config/tubarao-atacante/`. Backups: `~/.local/state/attack-shark-x11/`. Os caminhos respeitam `XDG_CONFIG_HOME` e `XDG_STATE_HOME`.

### Imagem do dispositivo

A edição pública funciona com uma ilustração vetorial própria. A imagem proprietária do fabricante não acompanha o repositório. Quem já possui os recursos da instalação original pode mantê-los localmente; leia [assets/README.md](assets/README.md). Nenhum executável ou projeto Ghidra proprietário é distribuído aqui.

### Macros: gravar, revisar e atribuir

1. Abra **Macros → Botões do mouse** e clique no número ou cartão de um dos cinco botões.
2. Escolha **Criar e gravar nova macro** ou selecione uma macro da biblioteca, exibida como lista. Não há opções prontas de Copiar/Colar nem dropdown de funções.
3. Dê um nome à macro e clique em **Gravar ações → Gravar**. Execute as combinações de teclado, cliques e rolagens dentro da área de captura. Por exemplo: Ctrl+C, uma pausa de 500 ms, Ctrl+V.
4. Clique em **Parar** e depois em **Usar gravação**. Os intervalos entre eventos são registrados automaticamente. A gravação fica restrita à área indicada; não registra ações em outros programas, movimento do ponteiro ou texto de métodos de entrada compostos. Esc e Tab podem fazer parte da sequência. A repetição automática de uma tecla mantida pressionada é ignorada; pressionar e soltar são eventos separados.
5. Revise os eventos. Use **Editar evento** para alterar um atraso ou recapturar uma tecla/clique/rolagem, **Inserir atraso** para adicionar uma pausa, e Subir/Descer/Remover para organizar a sequência. Ao editar uma tecla ou botão isolado, ajuste seu par de soltura/pressionamento quando necessário.
6. Escolha **Uma vez**, **Enquanto pressionado**, **Alternar** ou **Repetir N vezes**. Esses modos são configurações locais da macro, sem execução nesta etapa.
7. Se a criação começou no mapa, clique em **Salvar → botão N** para salvar e atribuir em uma única operação local. Para uma macro independente, use **Salvar macro** e depois associe-a no mapa.

Se a sequência tiver apenas o pressionamento de uma combinação (por exemplo Ctrl e C), o salvamento oferece acrescentar as solturas finais na ordem inversa e salvar. Cancelar preserva o rascunho. Depois de salvar e atribuir, a tela volta ao mapa com o nome da macro no botão escolhido. Erros de validação ou gravação aparecem em uma janela, além da mensagem de status.

Sair da área de captura interrompe a gravação. Se ainda houver teclas ou botões pressionados, o gravador acrescenta suas solturas finais e informa isso para revisão. Reiniciar a gravação substitui a tomada ainda não incorporada ao editor; cancelar a janela preserva a sequência anterior.

As macros e atribuições ficam em `~/.config/tubarao-atacante/macros.json`, respeitando `XDG_CONFIG_HOME`, com escrita atômica e lock. O formato de perfis existente permanece independente. Os limites de 256 eventos, 60 segundos por atraso, 100 repetições numéricas e uma hora de atrasos totais são limites deste editor, não capacidades confirmadas do firmware.

**Gravação, revisão e atribuição são locais. As macros ainda não são executadas no Linux nem gravadas no X11.** O formato de eventos do dispositivo e seus modos de execução precisam ser confirmados pela engenharia reversa. Veja [estado da pesquisa e validação](docs/MACROS.md).

<details>
<summary>Ver o editor de macros e o mapa dos botões</summary>

Prévias da versão 0.7.0 com dados de exemplo. O mapa usa a ilustração da edição pública.

![Editor de macros com gravação de eventos e campos numéricos −/+](docs/macros-editor.png)

![Mapa dos cinco botões com atribuição local de uma macro](docs/macros-buttons.png)

</details>

## 🧪 Testes

```bash
QT_QPA_PLATFORM=offscreen /usr/bin/python -m unittest discover -v
```

**Validação desta atualização:** 141 testes automatizados passaram. O gravador também foi verificado com eventos de teclado, cliques e rolagem simulados; os campos numéricos foram conferidos por clique, digitação, setas e limites.

A suíte usa um receptor simulado. Ela não comprova o comportamento de cada variante de firmware. A interface anterior teve funções confirmadas pelo usuário em um X11; o projeto continua em desenvolvimento. A integração contínua executa os testes em Python 3.12 e 3.13.

## 📫 Contribuindo

1. Faça um fork e crie uma branch.
2. Descreva o problema e implemente uma mudança com escopo claro.
3. Execute os testes e inclua o resultado no pull request.
4. Para alterações HID, inclua evidências de protocolo e a validação necessária.

Veja [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md) e o [handoff para Codex](CODEX_HANDOFF.md).

## 🤝 Colaboradores e créditos

- [Witorr](https://github.com/Witorr): mantenedor e validação no dispositivo.
- [OpenSharkX11](https://github.com/clevim/OpenSharkX11): tabela de DPI usada sob MIT, com atribuição preservada no código.
- Google Sans: distribuída sob SIL Open Font License; licença em `fonts/OFL.txt`.
- [iuricode/readme-template](https://github.com/iuricode/readme-template): estrutura de apresentação e seções deste README, adaptada do exemplo de repositório. Licença preservada em `licenses/readme-template-MIT.txt`.

## 📝 Licença

O código original deste projeto e a ilustração vetorial própria são distribuídos sob [MIT](LICENSE), permitindo uso, estudo, modificação e redistribuição. Componentes de terceiros mantêm suas licenças; veja [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). A licença MIT não concede direitos sobre marcas e recursos proprietários da Attack Shark.
