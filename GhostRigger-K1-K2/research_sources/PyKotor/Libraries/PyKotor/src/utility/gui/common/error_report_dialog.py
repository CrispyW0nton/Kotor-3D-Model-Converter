from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorReportData:
    additional_information: str
    include_logs: bool
    contact_info: str


class ErrorReportDialogBase(ABC):
    @abstractmethod
    def get_additional_information(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def set_additional_information(self, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_include_logs(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def set_include_logs(self, include: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_contact_info(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def set_contact_info(self, text: str) -> None:
        raise NotImplementedError

    def get_report_data(self) -> ErrorReportData:
        return ErrorReportData(
            additional_information=self.get_additional_information(),
            include_logs=self.get_include_logs(),
            contact_info=self.get_contact_info(),
        )
