import asyncio
import time
from aiogram.types import Message
from datetime import datetime, timedelta
import math

class EmailProgress:
    def __init__(self, total_emails):
        self.total = total_emails
        self.checked = 0
        self.valid = 0
        self.invalid = 0
        self.start_time = time.time()
        self.last_update = time.time()
        self.eta = 0
    
    def update(self, valid=False):
        """Обновить статистику"""
        self.checked += 1
        if valid:
            self.valid += 1
        else:
            self.invalid += 1
        
        # Рассчитываем ETA
        elapsed = time.time() - self.start_time
        if self.checked > 0:
            time_per_email = elapsed / self.checked
            remaining = self.total - self.checked
            self.eta = time_per_email * remaining
    
    def get_progress_bar(self, width=20):
        """Получить прогресс-бар"""
        progress = self.checked / self.total if self.total > 0 else 0
        filled = int(width * progress)
        bar = "█" * filled + "░" * (width - filled)
        percentage = progress * 100
        
        return f"[{bar}] {percentage:.1f}%"
    
    def format_time(self, seconds):
        """Форматировать время"""
        if seconds < 60:
            return f"{seconds:.1f} сек"
        elif seconds < 3600:
            return f"{seconds/60:.1f} мин"
        else:
            return f"{seconds/3600:.1f} час"
    
    def get_stats_text(self):
        """Получить текст статистики"""
        elapsed = time.time() - self.start_time
        speed = self.checked / elapsed if elapsed > 0 else 0
        
        text = f"""
📧 ПРОВЕРКА ПОЧТ В РЕАЛЬНОМ ВРЕМЕНИ

{self.get_progress_bar()}

📊 СТАТИСТИКА:
├─ Всего почт: {self.total}
├─ Проверено: {self.checked}
├─ 🟢 Валидных: {self.valid}
├─ 🔴 Невалидных: {self.invalid}
├─ 📈 Прогресс: {self.checked}/{self.total} ({self.checked/self.total*100:.1f}%)
├─ ⚡ Скорость: {speed:.1f} почт/сек
├─ ⏱️ Прошло: {self.format_time(elapsed)}
└─ ⏳ Осталось: {self.format_time(self.eta)}

🎯 ЭФФЕКТИВНОСТЬ: {self.valid/max(self.checked, 1)*100:.1f}%
"""
        return text

class ProgressReporter:
	def __init__(self, bot, chat_id):
		self.bot = bot
		self.chat_id = chat_id
		self.msg: Message | None = None

	async def start(self, text: str):
		self.msg = await self.bot.send_message(self.chat_id, text)
		return self.msg

	async def update(self, text: str):
		if self.msg:
			try:
				await self.msg.edit_text(text)
			except:
				pass

	async def finish(self, text: str):
		if self.msg:
			try:
				await self.msg.edit_text(text)
			except:
				pass