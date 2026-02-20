# handlers/nuke_handlers.py
from utils.keyboards import Keyboards
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.session_nuker import session_nuker

router = Router()

class NukeStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_username = State()
    waiting_for_template = State()
    waiting_for_method = State()

@router.callback_query(F.data == "user_nuke")
async def nuke_start(callback: CallbackQuery):
    """Начало сноса сессий"""
    text = """💣 <b>Система сноса сессий</b>

🎯 <b>Что делает:</b>
• Отправляет жалобы в поддержку Telegram
• Сообщает о взломанном аккаунте  
• Просит заблокировать все сессии

⚠️ <b>Используйте осторожно!</b>

Выберите метод:"""
    
    await callback.message.edit_text(text, reply_markup=Keyboards.nuke_methods())

@router.callback_query(F.data.startswith("nuke_"))
async def nuke_method_selected(callback: CallbackQuery, state: FSMContext):
    """Выбор метода сноса"""
    method = callback.data.replace("nuke_", "")
    await state.update_data(method=method)
    
    await callback.message.edit_text(
        "📱 <b>Введите номер телефона для сноса:</b>\n\n"
        "<code>+79991234567</code>\n\n"
        "⚠️ Номер должен быть в международном формате",
        reply_markup=Keyboards.user_nuke_cancel()
    )
    await state.set_state(NukeStates.waiting_for_phone)

@router.message(NukeStates.waiting_for_phone)
async def process_nuke_phone(message: Message, state: FSMContext):
    """Обработка номера телефона"""
    phone = message.text.strip()
    
    # Валидация номера
    if not await session_nuker.validate_phone_number(phone):
        await message.answer(
            "❌ <b>Неверный формат номера!</b>\n\n"
            "Используйте международный формат:\n"
            "<code>+79991234567</code>\n\n"
            "Попробуйте еще раз:",
            reply_markup=Keyboards.user_nuke_cancel()
        )
        return
    
    await state.update_data(phone=phone)
    
    await message.answer(
        "👤 <b>Введите username (опционально):</b>\n\n"
        "<code>@username</code>\n\n"
        "Или отправьте '-' чтобы пропустить",
        reply_markup=Keyboards.user_nuke_cancel()
    )
    await state.set_state(NukeStates.waiting_for_username)

@router.message(NukeStates.waiting_for_username)
async def process_nuke_username(message: Message, state: FSMContext):
    """Обработка username"""
    username = message.text.strip()
    if username == '-':
        username = ""
    
    await state.update_data(username=username)
    
    text = "📝 <b>Выберите язык жалобы:</b>"
    await message.answer(text, reply_markup=Keyboards.language_selection())

@router.callback_query(F.data.startswith("lang_"))
async def process_nuke_language(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора языка"""
    language = callback.data.replace("lang_", "")
    await state.update_data(language=language)
    
    data = await state.get_data()
    phone = data['phone']
    username = data.get('username', '')
    method = data.get('method', 'email')
    
    # Запускаем снос
    await callback.message.edit_text(
        "💣 <b>Запускаю снос сессий...</b>\n\n"
        f"🎯 Цель: <code>{phone}</code>\n"
        f"👤 Username: <code>{username if username else 'не указан'}</code>\n"
        f"🌐 Язык: {language}\n"
        f"⚡ Метод: {method}\n\n"
        "⏳ Ожидайте...",
        reply_markup=Keyboards.back_to_main()
    )
    
    # Выполняем снос
    if method == "email":
        result = await session_nuker.nuke_sessions_via_email(phone, username, language)
    else:
        result = await session_nuker.nuke_sessions_via_web(phone)
    
    # Отправляем результат
    if result:
        if method == "email":
            success_count = result.get("emails_sent", 0)
            total_emails = result.get("total_emails", 0)
            
            await callback.message.edit_text(
                f"✅ <b>Снос выполнен успешно!</b>\n\n"
                f"🎯 Цель: <code>{phone}</code>\n"
                f"📧 Отправлено писем: {success_count}/{total_emails}\n"
                f"🌐 Язык: {language}\n"
                f"💥 Статус: Сессии атакованы\n\n"
                f"⚠️ <i>Результаты появятся в течение 24 часов</i>",
                reply_markup=Keyboards.back_to_main()
            )
        else:
            await callback.message.edit_text(
                f"✅ <b>Веб-снос выполнен!</b>\n\n"
                f"🎯 Цель: <code>{phone}</code>\n"
                f"🌐 Метод: Веб-форма\n"
                f"💥 Статус: Запрос отправлен",
                reply_markup=Keyboards.back_to_main()
            )
    else:
        await callback.message.edit_text(
            f"❌ <b>Снос не удался</b>\n\n"
            f"🎯 Цель: <code>{phone}</code>\n"
            f"⚠️ Попробуйте позже или другим методом",
            reply_markup=Keyboards.back_to_main()
        )
    
    await state.clear()

@router.message(F.text == "❌ Отмена")
async def cancel_nuke(message: Message, state: FSMContext):
    """Отмена сноса"""
    await message.answer("❌ Снос отменен", reply_markup=Keyboards.back_to_main())
    await state.clear()