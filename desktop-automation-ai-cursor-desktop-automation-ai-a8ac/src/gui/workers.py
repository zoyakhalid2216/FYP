"""Background QThread workers so NLP/CV/automation never freeze the UI."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal


class CommandWorker(QThread):
    status = pyqtSignal(str)
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(
        self,
        pipeline,
        text: str,
        user_id: Optional[int],
        source: str = "text",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.text = text
        self.user_id = user_id
        self.source = source

    def run(self) -> None:
        try:
            result = self.pipeline.run_text_command(
                self.text,
                user_id=self.user_id,
                source=self.source,
                status_cb=self.status.emit,
            )
            if result.get("ok"):
                self.finished_ok.emit(result)
            else:
                self.failed.emit(result.get("error") or "Command failed")
                self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    def stop(self) -> None:
        self.pipeline.request_stop()


class WorkflowWorker(QThread):
    status = pyqtSignal(str)
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, pipeline, workflow_id: int, user_id: Optional[int], parent=None) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.workflow_id = workflow_id
        self.user_id = user_id

    def run(self) -> None:
        try:
            result = self.pipeline.run_workflow(
                self.workflow_id,
                user_id=self.user_id,
                status_cb=self.status.emit,
            )
            if result.get("ok"):
                self.finished_ok.emit(result)
            else:
                self.failed.emit(result.get("error") or "Workflow failed")
                self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    def stop(self) -> None:
        self.pipeline.request_stop()


class SpeechWorker(QThread):
    transcribed = pyqtSignal(str)
    failed = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, speech_service, parent=None) -> None:
        super().__init__(parent)
        self.speech_service = speech_service

    def run(self) -> None:
        try:
            text = self.speech_service.listen_once(status_cb=self.status.emit)
            self.transcribed.emit(text)
        except Exception as exc:
            self.failed.emit(str(exc))
