from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import find_dotenv, load_dotenv

from price_monitor.diff import diff_products
from price_monitor.notify import deliver_message, format_diff_message
from price_monitor.parser import DEFAULT_CATALOGUE_URL, SupportsGet, scrape_catalogue
from price_monitor.storage import load_snapshot, save_csv, save_excel, save_snapshot

logger = logging.getLogger(__name__)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PACKAGE_ROOT / "data"


@dataclass(frozen=True)
class MonitorConfig:
    start_url: str = DEFAULT_CATALOGUE_URL
    max_pages: int = 2
    data_dir: Path = DEFAULT_DATA_DIR
    xlsx_name: str = "catalogue.xlsx"
    csv_name: str = "catalogue.csv"
    snapshot_name: str = "snapshot.json"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    timeout: float = 20.0
    delay_seconds: float = 0.4


def run(config: MonitorConfig, session: SupportsGet | None = None) -> int:
    products = scrape_catalogue(
        config.start_url,
        max_pages=config.max_pages,
        session=session,
        timeout=config.timeout,
        delay_seconds=config.delay_seconds,
    )
    data_dir = config.data_dir
    xlsx_path = data_dir / config.xlsx_name
    csv_path = data_dir / config.csv_name
    snapshot_path = data_dir / config.snapshot_name
    save_excel(xlsx_path, products)
    save_csv(csv_path, products)
    logger.info("Сохранено %s позиций: %s и %s", len(products), xlsx_path, csv_path)

    previous = load_snapshot(snapshot_path)
    if previous is None:
        save_snapshot(snapshot_path, products, source_url=config.start_url)
        logger.info(
            "Первый запуск: снимок сохранён (%s позиций). Уведомление не отправлялось.",
            len(products),
        )
        return 0

    previous_products, previous_url = previous
    if previous_url and previous_url != config.start_url:
        logger.warning(
            "URL каталога изменился (%s → %s). Новые ссылки могут выглядеть как новые товары.",
            previous_url,
            config.start_url,
        )
    diff = diff_products(previous_products, products)
    if diff.removed_count:
        logger.info(
            "В снимке больше нет %s позиций. Отдельный алерт по ним не шлётся.",
            diff.removed_count,
        )
    if not diff.has_alerts:
        save_snapshot(snapshot_path, products, source_url=config.start_url)
        logger.info("Изменений цен и новых товаров нет.")
        return 0

    message = format_diff_message(diff, source_url=config.start_url, checked=len(products))
    try:
        channel = deliver_message(
            message,
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            timeout=config.timeout,
        )
    except requests.RequestException:
        logger.exception(
            "Не удалось отправить сводку в Telegram. "
            "Снимок не обновлён, следующий запуск повторит алерт."
        )
        return 1
    save_snapshot(snapshot_path, products, source_url=config.start_url)
    logger.info("Сводка отправлена (%s), снимок обновлён.", channel)
    return 0


def build_config(argv: list[str] | None = None) -> MonitorConfig:
    env_file = find_dotenv(usecwd=True)
    if env_file:
        load_dotenv(env_file)
    parser = argparse.ArgumentParser(
        description=(
            "Снимает каталог books.toscrape.com, сохраняет Excel/CSV и шлёт изменения в Telegram."
        ),
    )
    parser.add_argument("--url", default=os.getenv("CATALOGUE_URL", DEFAULT_CATALOGUE_URL))
    parser.add_argument("--max-pages", type=int, default=int(os.getenv("MAX_PAGES", "2")))
    parser.add_argument("--data-dir", default=os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)))
    parser.add_argument("--delay", type=float, default=float(os.getenv("REQUEST_DELAY", "0.4")))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("REQUEST_TIMEOUT", "20")))
    args = parser.parse_args(argv)
    return MonitorConfig(
        start_url=args.url,
        max_pages=args.max_pages,
        data_dir=Path(args.data_dir),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        timeout=args.timeout,
        delay_seconds=args.delay,
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(build_config(argv))


if __name__ == "__main__":
    raise SystemExit(main())
