import random
from typing import Dict

def generate_captcha() -> Dict[str, any]:
    """
    Генерирует простую математическую капчу
    """
    operations = [
        ('+', lambda a, b: a + b),
        ('-', lambda a, b: a - b),
        ('*', lambda a, b: a * b)
    ]
    
    a = random.randint(1, 15)
    b = random.randint(1, 15)
    op_symbol, op_func = random.choice(operations)
    
    # Для вычитания убедимся, что результат положительный
    if op_symbol == '-' and a < b:
        a, b = b, a
    
    answer = op_func(a, b)
    
    # Форматируем вопрос
    if op_symbol == '*':
        question = f"{a} × {b}"
    else:
        question = f"{a} {op_symbol} {b}"
    
    return {
        'question': question,
        'answer': answer,
        'expression': f"{a} {op_symbol} {b} = ?"
    }

def generate_text_captcha() -> Dict[str, str]:
    """
    Генерирует текстовую капчу
    """
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    captcha_text = ''.join(random.choices(chars, k=6))
    
    return {
        'text': captcha_text,
        'answer': captcha_text.lower()
    }

def generate_image_captcha() -> Dict[str, any]:
    """
    Генерирует капчу с изображением (заглушка)
    """
    # В реальности можно использовать библиотеку captcha
    text = ''.join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=5))
    
    return {
        'image_path': None,  # Путь к сгенерированному изображению
        'text': text,
        'answer': text.lower()
    }