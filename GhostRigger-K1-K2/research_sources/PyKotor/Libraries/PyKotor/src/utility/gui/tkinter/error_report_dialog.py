from __future__ import annotations

import tkinter as tk

from tkinter import ttk
from typing import TYPE_CHECKING, Callable

from utility.gui.common.error_report_dialog import ErrorReportDialogBase

if TYPE_CHECKING:
    from utility.gui.common.error_report_dialog import ErrorReportData


class TkErrorReportDialog(tk.Toplevel, ErrorReportDialogBase):
    def __init__(
        self,
        parent: tk.Misc | None = None,
        on_submit: Callable[[ErrorReportData], None] | None = None,
    ):
        super().__init__(master=parent)
        self._on_submit = on_submit
        self.title("Error handler")
        self.resizable(True, True)

        self._include_logs_var = tk.BooleanVar(value=False)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _build_ui(self):
        container = ttk.Frame(self, padding=12)
        container.grid(row=0, column=0, sticky="nsew")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        additional_label = ttk.Label(container, text="Provide additional information (optional)")
        additional_label.grid(row=0, column=0, sticky="w")

        self._additional_text = tk.Text(container, height=8, width=60, wrap="word")
        self._additional_text.grid(row=1, column=0, sticky="nsew", pady=(4, 10))
        container.rowconfigure(1, weight=1)

        attachments_label = ttk.Label(container, text="Select attachments (optional)")
        attachments_label.grid(row=2, column=0, sticky="w")

        include_logs = ttk.Checkbutton(container, text="Log Files", variable=self._include_logs_var)
        include_logs.grid(row=3, column=0, sticky="w", pady=(2, 10))

        contact_label = ttk.Label(
            container,
            text=(
                "How can we contact you (optional, only if you want to get a response). "
                "Your report is anonymous by default, so you can provide contact info like an email address here."
            ),
            wraplength=520,
            justify="left",
        )
        contact_label.grid(row=4, column=0, sticky="w")

        self._contact_entry = ttk.Entry(container)
        self._contact_entry.grid(row=5, column=0, sticky="ew", pady=(4, 12))

        button_frame = ttk.Frame(container)
        button_frame.grid(row=6, column=0, sticky="e")

        send_button = ttk.Button(button_frame, text="Send report", command=self._handle_submit)
        send_button.grid(row=0, column=0, padx=(0, 0))

    def _handle_submit(self):
        if self._on_submit is not None:
            self._on_submit(self.get_report_data())
        self.destroy()

    def _handle_close(self):
        self.destroy()

    def get_additional_information(self) -> str:
        return self._additional_text.get("1.0", "end-1c").strip()

    def set_additional_information(self, text: str) -> None:
        self._additional_text.delete("1.0", "end")
        self._additional_text.insert("1.0", text)

    def get_include_logs(self) -> bool:
        return bool(self._include_logs_var.get())

    def set_include_logs(self, include: bool) -> None:
        self._include_logs_var.set(include)

    def get_contact_info(self) -> str:
        return self._contact_entry.get().strip()

    def set_contact_info(self, text: str) -> None:
        self._contact_entry.delete(0, "end")
        self._contact_entry.insert(0, text)
