from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class Keyboards:
	def __init__(self):
		pass

	@staticmethod
	def main_menu(user_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
		k = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="🎯 Отправить жалобу", callback_data="send_report")],
			[InlineKeyboardButton(text="💰 Баланс", callback_data="my_balance")],
			[InlineKeyboardButton(text="📋 Помощь", callback_data="help")],
		])
		if is_admin:
			k.inline_keyboard.append([InlineKeyboardButton(text="👑 Админ панель", callback_data="admin_panel")])
		return k

	def back_to_admin(self) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]])

	@staticmethod
	def back_to_main() -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]])

	def back_to_balance(self) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="balance_menu")]])

	def report_reasons(self) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="📧 Спам", callback_data="report_reason_8")],
			[InlineKeyboardButton(text="🔞 Порнография", callback_data="report_reason_1")],
			[InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
		])

	def report_methods(self) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="📱 Сессии", callback_data="report_method_session")],
			[InlineKeyboardButton(text="📧 Почта", callback_data="report_method_email")],
			[InlineKeyboardButton(text="💥 Комбо", callback_data="report_method_combo")],
			[InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
		])

	def subscription_plans(self) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="🎫 BASIC", callback_data="show_basic")],
			[InlineKeyboardButton(text="⭐ PREMIUM", callback_data="show_premium")],
			[InlineKeyboardButton(text="💣 NUKE", callback_data="show_nuke")],
			[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
		])

	def payment_keyboard(self, invoice_id: str, pay_url: str) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="Оплатить", url=pay_url)],
			[InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}")],
			[InlineKeyboardButton(text="◀️ Назад", callback_data="balance_menu")]
		])

	# Админ клавиатуры (базовые)
	def admin_panel(self) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
			[InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
			[InlineKeyboardButton(text="🔐 Сессии", callback_data="admin_sessions")],
			[InlineKeyboardButton(text="📧 Почты", callback_data="admin_emails")],
			[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
		])

	def admin_manage_users(self) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="➕ Добавить баланс", callback_data="admin_add_balance")],
			[InlineKeyboardButton(text="🚫 Заблокировать", callback_data="admin_ban_user")],
			[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
		])

	def get_user_management_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="➕ Баланс", callback_data=f"admin_add_balance_{user_id}")],
			[InlineKeyboardButton(text="🎫 Выдать подписку", callback_data=f"admin_add_sub_{user_id}")],
			[InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"admin_ban_{user_id}")],
			[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_manage_users")]
		])

	def blacklist_types(self) -> InlineKeyboardMarkup:
		return InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="Пользователь", callback_data="blacklist_type_user")],
			[InlineKeyboardButton(text="Группа", callback_data="blacklist_type_group")],
			[InlineKeyboardButton(text="Канал", callback_data="blacklist_type_channel")],
			[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
		])