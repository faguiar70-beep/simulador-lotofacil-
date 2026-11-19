import os
import json
import socket
import threading
import urllib.request
import urllib.error
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle

Window.clearcolor = (0.035, 0.055, 0.095, 1)
Window.softinput_mode = "below_target"

MODELO = "gemini-3.5-flash-lite"
URL_GEMINI = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODELO + ":generateContent"
)

# Mantém a correção IPv4 que funcionou no Pydroid.
_getaddrinfo_original = socket.getaddrinfo

def somente_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _getaddrinfo_original(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = somente_ipv4


class Painel(BoxLayout):
    def __init__(self, cor=(0.07, 0.10, 0.16, 1), **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*cor)
            self.fundo = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.bind(pos=self._atualizar, size=self._atualizar)

    def _atualizar(self, *_):
        self.fundo.pos = self.pos
        self.fundo.size = self.size


class BolhaMensagem(BoxLayout):
    def __init__(self, texto, autor, **kwargs):
        super().__init__(
            orientation="vertical", size_hint_y=None,
            padding=[dp(12), dp(9)], spacing=dp(4), **kwargs
        )
        self.bind(minimum_height=self.setter("height"))
        cor = (0.08, 0.27, 0.48, 1) if autor == "user" else (0.10, 0.14, 0.22, 1)
        nome = "VOCÊ" if autor == "user" else "MEU ASSISTENTE"
        with self.canvas.before:
            Color(*cor)
            self.fundo = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        self.bind(pos=self._atualizar, size=self._atualizar)

        cab = Label(
            text=nome, size_hint_y=None, height=dp(17), color=(0.38, 0.72, 1, 1),
            bold=True, font_size="10sp", halign="left", valign="middle"
        )
        cab.bind(size=lambda obj, val: setattr(obj, "text_size", val))
        self.add_widget(cab)

        corpo = Label(
            text=texto, size_hint_y=None, color=(0.92, 0.95, 1, 1),
            font_size="14sp", halign="left", valign="top"
        )
        corpo.bind(
            width=lambda obj, val: setattr(obj, "text_size", (val, None)),
            texture_size=lambda obj, val: setattr(obj, "height", val[1])
        )
        self.add_widget(corpo)

    def _atualizar(self, *_):
        self.fundo.pos = self.pos
        self.fundo.size = self.size


class BotaoAzul(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0.05, 0.42, 0.78, 1)
        self.color = (1, 1, 1, 1)
        self.bold = True
        self.font_size = "14sp"


class MeuAssistenteIA(App):
    title = "Meu Assistente IA"

    def build(self):
        # No Pydroid, user_data_dir aponta para a área de dados do app.
        # No futuro APK, será a área privada do aplicativo.
        self.pasta_dados = self.user_data_dir
        self.arquivo_historico = os.path.join(self.pasta_dados, "historico_assistente.json")
        self.arquivo_config = os.path.join(self.pasta_dados, "config_assistente.json")
        self.historico = []
        self.enviando = False
        self.api_key = ""
        self.carregar_configuracoes()
        self.carregar_historico()

        raiz = BoxLayout(
            orientation="vertical", padding=[dp(12), dp(10), dp(12), dp(8)],
            spacing=dp(9)
        )

        cabecalho = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(54))
        titulo = Label(
            text="[b]MEU ASSISTENTE IA[/b]", markup=True, color=(0.95, 0.97, 1, 1),
            font_size="19sp", halign="left", valign="middle", size_hint_y=None,
            height=dp(30)
        )
        titulo.bind(size=lambda obj, val: setattr(obj, "text_size", val))
        subtitulo = Label(
            text="Seu assistente pessoal", color=(0.53, 0.68, 0.82, 1),
            font_size="11sp", halign="left", valign="middle"
        )
        subtitulo.bind(size=lambda obj, val: setattr(obj, "text_size", val))
        cabecalho.add_widget(titulo)
        cabecalho.add_widget(subtitulo)
        raiz.add_widget(cabecalho)

        caixa_chave = Painel(
            orientation="vertical", size_hint_y=None, height=dp(62),
            padding=dp(8), spacing=dp(4)
        )
        self.campo_chave = TextInput(
            text=self.api_key, hint_text="Chave da API Gemini",
            password=True, multiline=False, size_hint_y=None, height=dp(42),
            padding=[dp(10), dp(10)], background_normal="", background_active="",
            background_color=(0.045, 0.07, 0.12, 1),
            foreground_color=(0.92, 0.96, 1, 1),
            hint_text_color=(0.48, 0.57, 0.68, 1),
            cursor_color=(0.25, 0.68, 1, 1), font_size="13sp"
        )
        caixa_chave.add_widget(self.campo_chave)
        raiz.add_widget(caixa_chave)

        self.lista_mensagens = BoxLayout(
            orientation="vertical", size_hint_y=None,
            spacing=dp(10), padding=[dp(1), dp(5)]
        )
        self.lista_mensagens.bind(minimum_height=self.lista_mensagens.setter("height"))
        self.rolagem = ScrollView(do_scroll_x=False, bar_width=dp(3))
        self.rolagem.add_widget(self.lista_mensagens)
        raiz.add_widget(self.rolagem)

        area_entrada = Painel(
            orientation="vertical", size_hint_y=None, height=dp(108),
            padding=dp(9), spacing=dp(7)
        )
        linha = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(45), spacing=dp(7)
        )
        self.entrada = TextInput(
            hint_text="Digite sua mensagem...", multiline=False,
            padding=[dp(10), dp(11)], background_normal="", background_active="",
            background_color=(0.045, 0.07, 0.12, 1),
            foreground_color=(0.94, 0.97, 1, 1),
            hint_text_color=(0.48, 0.57, 0.68, 1),
            cursor_color=(0.25, 0.68, 1, 1), font_size="14sp"
        )
        self.entrada.bind(on_text_validate=self.enviar_mensagem)
        linha.add_widget(self.entrada)

        mic = Button(
            text="🎙", size_hint_x=None, width=dp(45),
            background_normal="", background_color=(0.12, 0.19, 0.29, 1),
            color=(0.75, 0.86, 0.98, 1), font_size="20sp"
        )
        mic.bind(on_release=self.ativar_voz)
        linha.add_widget(mic)
        area_entrada.add_widget(linha)

        self.botao_enviar = BotaoAzul(
            text="ENVIAR MENSAGEM", size_hint_y=None, height=dp(39)
        )
        self.botao_enviar.bind(on_release=self.enviar_mensagem)
        area_entrada.add_widget(self.botao_enviar)
        raiz.add_widget(area_entrada)

        rodape = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(34), spacing=dp(8)
        )
        limpar = Button(
            text="Limpar conversa", background_normal="",
            background_color=(0.12, 0.16, 0.23, 1),
            color=(0.72, 0.80, 0.90, 1), font_size="11sp"
        )
        limpar.bind(on_release=self.limpar_conversa)
        rodape.add_widget(limpar)

        salvar = Button(
            text="Salvar chave", background_normal="",
            background_color=(0.12, 0.16, 0.23, 1),
            color=(0.72, 0.80, 0.90, 1), font_size="11sp"
        )
        salvar.bind(on_release=self.salvar_chave)
        rodape.add_widget(salvar)
        raiz.add_widget(rodape)

        if self.historico:
            for item in self.historico:
                self.adicionar_bolha(item.get("content", ""), item.get("role", "assistant"))
        else:
            self.adicionar_bolha(
                "Olá! Sou seu assistente. Digite uma mensagem para começarmos.",
                "assistant"
            )
        Clock.schedule_once(self.ir_para_final, 0.2)
        return raiz

    def carregar_configuracoes(self):
        try:
            with open(self.arquivo_config, "r", encoding="utf-8") as arq:
                self.api_key = json.load(arq).get("api_key", "")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.api_key = ""

    def salvar_chave(self, *_):
        self.api_key = self.campo_chave.text.strip()
        try:
            os.makedirs(self.pasta_dados, exist_ok=True)
            with open(self.arquivo_config, "w", encoding="utf-8") as arq:
                json.dump({"api_key": self.api_key}, arq)
            self.adicionar_bolha("Chave salva neste dispositivo.", "assistant")
        except OSError as erro:
            self.adicionar_bolha("Não foi possível salvar a chave: " + str(erro), "assistant")

    def carregar_historico(self):
        try:
            with open(self.arquivo_historico, "r", encoding="utf-8") as arq:
                dados = json.load(arq)
                if isinstance(dados, list):
                    self.historico = dados
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.historico = []

    def salvar_historico(self):
        try:
            os.makedirs(self.pasta_dados, exist_ok=True)
            with open(self.arquivo_historico, "w", encoding="utf-8") as arq:
                json.dump(self.historico, arq, ensure_ascii=False, indent=2)
        except OSError:
            self.adicionar_bolha("Não foi possível salvar o histórico.", "assistant")

    def adicionar_bolha(self, texto, autor):
        self.lista_mensagens.add_widget(BolhaMensagem(texto, autor, size_hint_x=1))
        Clock.schedule_once(self.ir_para_final, 0.08)

    def ir_para_final(self, *_):
        self.rolagem.scroll_y = 0

    def ativar_voz(self, *_):
        self.entrada.focus = True
        self.adicionar_bolha(
            "O microfone nativo será integrado na futura versão APK. "
            "No Pydroid, use o microfone do teclado Android para ditar.",
            "assistant"
        )

    def enviar_mensagem(self, *_):
        if self.enviando:
            return
        mensagem = self.entrada.text.strip()
        if not mensagem:
            return
        chave = self.campo_chave.text.strip()
        if not chave:
            self.adicionar_bolha("Insira sua chave Gemini no campo superior.", "assistant")
            return

        self.api_key = chave
        self.salvar_chave()
        self.entrada.text = ""
        self.adicionar_bolha(mensagem, "user")
        self.historico.append({"role": "user", "content": mensagem})
        self.salvar_historico()

        self.enviando = True
        self.botao_enviar.disabled = True
        self.botao_enviar.text = "AGUARDE..."
        threading.Thread(
            target=self.consultar_gemini, args=(chave,), daemon=True
        ).start()

    def consultar_gemini(self, chave):
        try:
            contents = []
            for item in self.historico:
                role = "user" if item.get("role") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": item.get("content", "")}]
                })

            agora = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
            instrucao = (
                "Você é o Meu Assistente IA. Responda em português do Brasil. "
                "Seja claro, direto e útil. Não invente informações; quando não souber, "
                "diga isso. Considere o contexto da conversa. Data e hora local: "
                + agora + "."
            )
            dados = {
                "system_instruction": {"parts": [{"text": instrucao}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
            }
            requisicao = urllib.request.Request(
                URL_GEMINI + "?key=" + chave,
                data=json.dumps(dados).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(requisicao, timeout=60) as resposta:
                retorno = json.loads(resposta.read().decode("utf-8"))

            texto = (
                retorno.get("candidates", [{}])[0]
                .get("content", {}).get("parts", [{}])[0].get("text", "")
            )
            if not texto:
                texto = "A API respondeu, mas não retornou texto."
            Clock.schedule_once(lambda dt, t=texto: self.finalizar_resposta(t, None), 0)

        except urllib.error.HTTPError as erro:
            detalhe = erro.read().decode("utf-8", errors="replace")
            msg = "Erro HTTP " + str(erro.code) + ": " + detalhe[:800]
            Clock.schedule_once(lambda dt, m=msg: self.finalizar_resposta(None, m), 0)
        except Exception as erro:
            msg = "Não foi possível consultar o Gemini: " + str(erro)
            Clock.schedule_once(lambda dt, m=msg: self.finalizar_resposta(None, m), 0)

    def finalizar_resposta(self, texto, erro):
        self.enviando = False
        self.botao_enviar.disabled = False
        self.botao_enviar.text = "ENVIAR MENSAGEM"
        if erro:
            self.adicionar_bolha(erro, "assistant")
            return
        self.adicionar_bolha(texto, "assistant")
        self.historico.append({"role": "assistant", "content": texto})
        self.salvar_historico()

    def limpar_conversa(self, *_):
        self.historico = []
        self.salvar_historico()
        self.lista_mensagens.clear_widgets()
        self.adicionar_bolha("Conversa limpa. Podemos começar novamente.", "assistant")

    def on_stop(self):
        if hasattr(self, "campo_chave"):
            self.api_key = self.campo_chave.text.strip()
            try:
                with open(self.arquivo_config, "w", encoding="utf-8") as arq:
                    json.dump({"api_key": self.api_key}, arq)
            except OSError:
                pass
        if hasattr(self, "historico"):
            self.salvar_historico()


if __name__ == "__main__":
    MeuAssistenteIA().run()
