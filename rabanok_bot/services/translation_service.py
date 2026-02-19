import aiohttp
import json
import logging
from typing import Dict, Optional
import asyncio
from deep_translator import GoogleTranslator
from core.config import Config

logger = logging.getLogger(__name__)

class TranslationService:
	def __init__(self):
		self.translator = GoogleTranslator()
		self.language_map: Dict[str, str] = {
			'RU': 'ru', 'US': 'en', 'GB': 'en', 'DE': 'de', 'FR': 'fr',
			'ES': 'es', 'IT': 'it', 'CN': 'zh-cn', 'JP': 'ja', 'KR': 'ko',
			'BR': 'pt', 'IN': 'hi', 'SA': 'ar', 'TR': 'tr', 'ID': 'id',
			'VN': 'vi', 'TH': 'th', 'NL': 'nl', 'PL': 'pl', 'UA': 'uk'
		}
		# удобный доступ к текстам причин
		self.complaint_texts = Config.COMPLAINT_REASONS

		logger.info("🌍 TranslationService инициализирован")

	def get_language_from_country(self, country_code: str) -> str:
		return self.language_map.get(country_code.upper(), 'en')

	async def translate_text(self, text: str, target_lang: str, source_lang: str = 'auto') -> str:
		try:
			# GoogleTranslator из deep_translator синхронен, запускаем в потоке
			loop = asyncio.get_running_loop()
			result = await loop.run_in_executor(None, lambda: GoogleTranslator(source=source_lang, target=target_lang).translate(text))
			return result
		except Exception as e:
			logger.warning(f"Translate failed: {e}")
			return text

	async def translate_complaint(self, text: str, target_lang: str) -> str:
		return await self.translate_text(text, target_lang)

	async def get_localized_complaint(self, reason: int, country_code: str) -> str:
		base = self.complaint_texts.get(reason, "Complaint")
		lang = self.get_language_from_country(country_code)
		return await self.translate_complaint(base, lang)

	async def generate_multilingual_complaint(self, target: str, reason: int, country_codes: list) -> Dict[str, str]:
		result = {}
		tasks = []
		for cc in country_codes:
			lang = self.get_language_from_country(cc)
			tasks.append(self.translate_complaint(self.complaint_texts.get(reason, ""), lang))
		translations = await asyncio.gather(*tasks, return_exceptions=True)
		for cc, tr in zip(country_codes, translations):
			result[cc] = tr if not isinstance(tr, Exception) else self.complaint_texts.get(reason, "")
		return result

	async def validate_language_support(self, lang_code: str) -> bool:
		# Проверяем по списку кодов
		lang_code = lang_code.lower()
		return lang_code in {v.lower() for v in self.language_map.values()} or lang_code in [v['code'] for v in Config.SUPPORTED_LANGUAGES.values()]

	async def get_supported_languages(self) -> list:
		return list({v['code'] for v in Config.SUPPORTED_LANGUAGES.values()})

	async def batch_translate(self, texts: list, target_lang: str, source_lang: str = 'auto') -> list:
		tasks = [self.translate_text(t, target_lang, source_lang) for t in texts]
		return await asyncio.gather(*tasks, return_exceptions=False)

	async def detect_language(self, text: str) -> str:
		# Простейшая детекция: проверка на кириллицу
		if any('\u0400' <= ch <= '\u04FF' for ch in text):
			return 'ru'
		return 'en'

# Глобальный экземпляр для использования
_translation_service_instance = None

def get_translation_service() -> TranslationService:
	"""Получить экземпляр TranslationService (синглтон)"""
	global _translation_service_instance
	if _translation_service_instance is None:
		_translation_service_instance = TranslationService()
	return _translation_service_instance

async def initialize_translation_service() -> bool:
	"""Инициализировать сервис переводов"""
	global _translation_service_instance
	try:
		_translation_service_instance = TranslationService()
		# быстрая проверка
		ok = await _translation_service_instance.validate_language_support('en')
		return True if ok else False
	except Exception as e:
		logger.error(f"Ошибка инициализации TranslationService: {e}")
		return False