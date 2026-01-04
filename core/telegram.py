# ===== core/telegram.py =====
# Telegram уведомления
# =====================

import requests
from typing import Optional
from core.types import CoinRow


class TelegramBot:
    """Отправка уведомлений в Telegram."""
    
    def __init__(self, token: str, chat_id: int, thread_id: Optional[int] = None):
        self.token = token
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send(self, text: str) -> bool:
        """Отправить сообщение."""
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if self.thread_id:
                payload["message_thread_id"] = self.thread_id
            
            r = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=15)
            return r.status_code == 200
        except:
            return False
    
    def send_signal(self, row: CoinRow) -> bool:
        """Отправить сигнал."""
        emoji = {"ВХОД": "🚨", "Готовность": "🟡", "Интерес": "🔵"}.get(row.status, "⚪")
        text = (
            f"{emoji} <b>{row.symbol.replace('USDT', '')}</b>\n"
            f"Статус: {row.status} | Скор: {row.score:.0f}\n"
            f"Тип: {row.watch_type}\n\n"
            f"Цена: {row.price_now:.6f} | 24ч: {row.change_24h_pct:+.1f}%\n"
            f"Вход: {row.entry_price:.6f}\n"
            f"SL: {row.sl_price:.6f} | TP1: {row.tp1:.6f}\n"
            f"R/R: {row.rr:.2f}"
        )
        return self.send(text)
    
    def send_open(self, symbol: str, entry: float, leverage: float, status: str, score: float) -> bool:
        """Уведомление об открытии."""
        text = (
            f"🔻 <b>SHORT OPEN</b>\n"
            f"{symbol.replace('USDT', '')} @ {entry:.6f}\n"
            f"Плечо: {leverage:.1f}x | {status} ({score:.0f})"
        )
        return self.send(text)
    
    def send_close(self, symbol: str, pnl_pct: float, pnl_usd: float, reason: str, balance: float) -> bool:
        """Уведомление о закрытии."""
        emoji = "🟢" if pnl_usd > 0 else "🔴"
        text = (
            f"{emoji} <b>CLOSED</b> {symbol.replace('USDT', '')}\n"
            f"PnL: {pnl_pct:+.2f}% ({pnl_usd:+.2f}$)\n"
            f"Причина: {reason}\n"
            f"Баланс: {balance:.2f}$"
        )
        return self.send(text)


# Singleton
_bot: Optional[TelegramBot] = None

def init_telegram(token: str, chat_id: int, thread_id: Optional[int] = None):
    """Инициализировать бота."""
    global _bot
    _bot = TelegramBot(token, chat_id, thread_id)

def get_telegram() -> Optional[TelegramBot]:
    """Получить бота."""
    return _bot

def tg_send(text: str) -> bool:
    """Отправить сообщение."""
    if _bot:
        return _bot.send(text)
    return False
