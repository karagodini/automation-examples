from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XLSX = PACKAGE_ROOT / "data" / "leads.xlsx"


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    leads_xlsx_path: Path = DEFAULT_XLSX
    webhook_secret: str = ""
    google_service_account_file: str = ""
    google_sheet_id: str = ""
    google_sheet_worksheet: str = "Leads"
    openai_api_base: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    request_timeout: float = 20.0

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_base.strip() and self.openai_model.strip())

    @property
    def sheets_enabled(self) -> bool:
        return bool(self.google_service_account_file.strip() and self.google_sheet_id.strip())

    @classmethod
    def from_env(cls) -> Settings:
        env_file = find_dotenv(usecwd=True)
        if env_file:
            load_dotenv(env_file)
        xlsx = os.getenv("LEADS_XLSX_PATH", "").strip()
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            leads_xlsx_path=Path(xlsx) if xlsx else DEFAULT_XLSX,
            webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip(),
            google_service_account_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip(),
            google_sheet_id=os.getenv("GOOGLE_SHEET_ID", "").strip(),
            google_sheet_worksheet=os.getenv("GOOGLE_SHEET_WORKSHEET", "Leads").strip() or "Leads",
            openai_api_base=os.getenv("OPENAI_API_BASE", "").strip(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "").strip(),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT", "20")),
        )
