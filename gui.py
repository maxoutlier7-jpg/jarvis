#!/usr/bin/env python3
"""Interface desktop do Jarvis usando PySide6."""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.config import config
from core.llm import LLM, ProviderError
from core.memory import Memory
from core.tokens import BudgetExceededError
from plugins import list_plugins


STYLESHEET = """
QMainWindow, QWidget#root { background: #080d14; color: #e8f7ff; }
QFrame#sidebar { background: #0b121c; border-right: 1px solid #163246; }
QFrame#topbar { background: #0b121c; border-bottom: 1px solid #163246; }
QFrame#composer { background: #0b121c; border: 1px solid #17384d; border-radius: 16px; }
QFrame#message { background: #0d1722; border: 1px solid #17384d; border-radius: 14px; }
QFrame#message_user { background: #102536; border: 1px solid #15506b; border-radius: 14px; }
QLabel#brand { color: #67e8f9; font-size: 22px; font-weight: 800; letter-spacing: 3px; }
QLabel#subtitle { color: #7193a8; font-size: 11px; }
QLabel#section { color: #5e8297; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#status { color: #67e8f9; font-size: 11px; }
QLabel#title { color: #e8f7ff; font-size: 14px; font-weight: 700; }
QLabel#body { color: #c7d9e3; font-size: 13px; }
QLabel#meta { color: #547386; font-size: 10px; }
QPushButton { background: transparent; color: #89aabd; border: 1px solid transparent; border-radius: 10px; padding: 10px 12px; text-align: left; }
QPushButton:hover { background: #10202d; color: #67e8f9; border-color: #17384d; }
QPushButton#send { background: #19b7d5; color: #041017; font-weight: 800; border-radius: 11px; padding: 11px 18px; }
QPushButton#send:hover { background: #54d8ef; }
QPushButton#mic { background: #10202d; color: #67e8f9; border: 1px solid #1a536b; border-radius: 11px; font-size: 16px; }
QPushButton#mic:hover { background: #143447; }
QPushButton#clear { color: #7c9bad; }
QLineEdit#input { background: transparent; border: none; color: #e8f7ff; padding: 8px; font-size: 13px; }
QComboBox { background: #0e1a25; color: #8fdced; border: 1px solid #1b4055; border-radius: 8px; padding: 7px 10px; }
QComboBox QAbstractItemView { background: #0e1a25; color: #dff8ff; selection-background-color: #12394a; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 7px; }
QScrollBar::handle:vertical { background: #1b4055; border-radius: 3px; }
"""


class ChatWorker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, llm: LLM, message: str, history: list[dict[str, str]]):
        super().__init__()
        self.llm = llm
        self.message = message
        self.history = history

    def run(self) -> None:
        try:
            self.finished.emit(self.llm.chat(self.message, self.history))
        except Exception as exc:
            self.failed.emit(exc)


class JarvisWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.llm = LLM()
        self.memory = Memory(config.MEMORY_MAX_MESSAGES)
        self.thread: Optional[QThread] = None
        self.worker: Optional[ChatWorker] = None
        self.setWindowTitle("J.A.R.V.I.S. — Personal AI")
        self.setMinimumSize(980, 680)
        self.resize(1180, 760)
        self._build_ui()
        self._refresh_status()
        self._welcome()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(235)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        side.setSpacing(10)

        brand = QLabel("J.A.R.V.I.S.")
        brand.setObjectName("brand")
        side.addWidget(brand)
        sub = QLabel("PERSONAL AI SYSTEM")
        sub.setObjectName("subtitle")
        side.addWidget(sub)
        side.addSpacing(25)

        sec = QLabel("SYSTEM")
        sec.setObjectName("section")
        side.addWidget(sec)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(self.llm.available_providers())
        if self.llm.provider in [self.provider_combo.itemText(i) for i in range(self.provider_combo.count())]:
            self.provider_combo.setCurrentText(self.llm.provider)
        self.provider_combo.currentTextChanged.connect(self._change_provider)
        side.addWidget(self.provider_combo)

        self.online = QLabel("●  ONLINE")
        self.online.setObjectName("status")
        side.addWidget(self.online)
        side.addSpacing(15)

        sec2 = QLabel("ACTIONS")
        sec2.setObjectName("section")
        side.addWidget(sec2)
        clear = QPushButton("＋  Nova conversa")
        clear.clicked.connect(self._clear_chat)
        side.addWidget(clear)
        status = QPushButton("◈  System status")
        status.clicked.connect(self._show_status)
        side.addWidget(status)
        help_btn = QPushButton("?  Como usar")
        help_btn.clicked.connect(self._show_help)
        side.addWidget(help_btn)
        side.addStretch(1)

        footer = QLabel("CONTROL TODAY.\nAUTOMATE TOMORROW.")
        footer.setObjectName("subtitle")
        side.addWidget(footer)
        outer.addWidget(sidebar)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top = QFrame()
        top.setObjectName("topbar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(24, 16, 24, 16)
        heading = QVBoxLayout()
        title = QLabel("Assistente pessoal")
        title.setObjectName("title")
        heading.addWidget(title)
        self.model_label = QLabel("Conectando...")
        self.model_label.setObjectName("subtitle")
        heading.addWidget(self.model_label)
        top_layout.addLayout(heading)
        top_layout.addStretch(1)
        self.token_label = QLabel("0 tokens")
        self.token_label.setObjectName("meta")
        top_layout.addWidget(self.token_label)
        main_layout.addWidget(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(28, 28, 28, 28)
        self.chat_layout.setSpacing(14)
        self.chat_layout.addStretch(1)
        self.scroll.setWidget(self.chat_container)
        main_layout.addWidget(self.scroll, 1)

        composer_wrap = QWidget()
        composer_layout = QHBoxLayout(composer_wrap)
        composer_layout.setContentsMargins(20, 12, 20, 18)
        composer = QFrame()
        composer.setObjectName("composer")
        c = QHBoxLayout(composer)
        c.setContentsMargins(10, 7, 8, 7)
        self.input = QLineEdit()
        self.input.setObjectName("input")
        self.input.setPlaceholderText("Fale com o Jarvis...")
        self.input.returnPressed.connect(self._send)
        c.addWidget(self.input, 1)
        mic = QPushButton("◉")
        mic.setObjectName("mic")
        mic.setToolTip("Entrada de voz será adicionada em uma próxima etapa")
        mic.clicked.connect(lambda: self._add_message("system", "Entrada de voz ainda não está ativada nesta versão."))
        c.addWidget(mic)
        send = QPushButton("Enviar  ➤")
        send.setObjectName("send")
        send.clicked.connect(self._send)
        c.addWidget(send)
        composer_layout.addWidget(composer)
        main_layout.addWidget(composer_wrap)

        outer.addWidget(main, 1)

    def _welcome(self) -> None:
        self._add_message(
            "assistant",
            "Olá. Eu sou o **J.A.R.V.I.S.**\n\nSeu sistema está online. Pode me pedir para conversar, pesquisar na web, calcular valores ou ajudar com tarefas."
        )

    def _add_message(self, role: str, text: str, meta: str = "") -> None:
        frame = QFrame()
        frame.setObjectName("message_user" if role == "user" else "message")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        who = QLabel("VOCÊ" if role == "user" else "JARVIS")
        who.setObjectName("section")
        layout.addWidget(who)
        body = QLabel(text.replace("**", ""))
        body.setObjectName("body")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)
        if meta:
            info = QLabel(meta)
            info.setObjectName("meta")
            layout.addWidget(info)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, frame)
        self._scroll_bottom()

    def _scroll_bottom(self) -> None:
        QApplication.processEvents()
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _send(self) -> None:
        if self.thread is not None and self.thread.isRunning():
            return
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        command = text.lower()
        if command in {"/exit", "/quit", "sair"}:
            self.close()
            return
        if command == "/clear":
            self._clear_chat()
            return
        if command == "/status":
            self._show_status()
            return
        if command == "/help":
            self._show_help()
            return
        if command.startswith("/provider"):
            parts = command.split(maxsplit=1)
            if len(parts) == 2 and self.llm.set_provider(parts[1]):
                self.provider_combo.setCurrentText(parts[1])
                self._add_message("assistant", f"Provedor alterado para **{parts[1]}**.")
            else:
                self._add_message("assistant", "Uso: `/provider gemini` ou `/provider groq`.")
            return

        self._add_message("user", text)
        self._set_busy(True)
        history = self.memory.get_history()
        self.thread = QThread()
        self.worker = ChatWorker(self.llm, text, history)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_result)
        self.worker.failed.connect(self._on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self._worker_done)
        self.thread.start()

    def _on_result(self, result) -> None:
        self.memory.add_exchange(self._last_user_message(), result.text)
        meta = f"{result.provider} · {result.model} · {result.prompt_tokens + result.completion_tokens:,} tokens"
        if result.cached:
            meta = f"{result.provider} · cache · 0 tokens"
        self._add_message("assistant", result.text, meta)
        self._refresh_status()
        self._set_busy(False)

    def _on_error(self, exc: Exception) -> None:
        if isinstance(exc, BudgetExceededError):
            message = f"Limite de uso: {exc}"
        elif isinstance(exc, ProviderError):
            message = f"Falha no provedor **{exc.provider}**: {exc.cause}"
        else:
            message = f"Erro: {exc}"
        self._add_message("assistant", message)
        self._set_busy(False)

    def _last_user_message(self) -> str:
        history = self.memory.get_history()
        # The current user message is the newest item outside memory until the response arrives.
        return getattr(self, "_pending_message", "") or (history[-1]["content"] if history else "")

    def _worker_done(self) -> None:
        self._set_busy(False)
        if self.thread:
            self.thread.deleteLater()
        self.thread = None
        self.worker = None

    def _set_busy(self, busy: bool) -> None:
        self.input.setEnabled(not busy)
        self.input.setPlaceholderText("Jarvis está pensando..." if busy else "Fale com o Jarvis...")
        self.online.setText("●  PROCESSANDO" if busy else "●  ONLINE")
        if not busy:
            self.input.setFocus()

    def _change_provider(self, provider: str) -> None:
        if provider and provider != self.llm.provider:
            self.llm.set_provider(provider)
            self._refresh_status()

    def _refresh_status(self) -> None:
        model = config.GEMINI_MODEL if self.llm.provider == "gemini" else config.GROQ_MODEL
        self.model_label.setText(f"{self.llm.provider.upper()}  ·  {model}")
        summary = self.llm.tracker.summary()
        self.token_label.setText(f"{summary['session_total']:,} tokens  ·  {summary['requests']} req")

    def _clear_chat(self) -> None:
        self.memory.clear()
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._welcome()

    def _show_status(self) -> None:
        providers = ", ".join(self.llm.available_providers()) or "nenhum"
        tools = ", ".join(list_plugins()) or "nenhuma"
        self._add_message("system", f"Sistema: ONLINE\nProvedor: {self.llm.provider}\nModelo: {self.model_label.text().split(' · ', 1)[-1]}\nProvedores: {providers}\nFerramentas: {tools}")

    def _show_help(self) -> None:
        self._add_message("system", "Comandos: /status · /clear · /help · /provider gemini · /provider groq · /exit\n\nVocê também pode conversar normalmente e pedir pesquisas web ou cálculos.")


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    font = QFont("Inter", 10)
    app.setFont(font)
    window = JarvisWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_gui())
