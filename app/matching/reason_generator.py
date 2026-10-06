"""Generates simple, clear, and natural match reasons (Kazakh & Russian)."""

from typing import Optional


def generate_human_match_reason(
    user_occ: Optional[str] = "student",
    user_age: Optional[int] = 21,
    cand_name: str = "Көрші",
    cand_occ: Optional[str] = "student",
    cand_age: Optional[int] = 22,
    cand_budget: Optional[int] = 100000,
    lang: str = "ru",
    criteria: Optional[dict] = None,
) -> str:
    """Generate a clear, warm explanation on 'ты' / 'сен' (1-2 sentences)."""
    c = criteria or {}

    if lang == "kz":
        if user_occ == cand_occ and user_occ in ("student", "учусь"):
            occ = "Екеуің де студентсіңдер — күн тәртіптерің сәйкес келеді."
        elif user_occ == cand_occ and user_occ in ("working", "работает"):
            occ = "Екеуің де жұмыс істейсіңдер — кешке үйде тыныштықты бағалайсыңдар."
        else:
            occ = "Күн тәртібі мен өмір ырғағы бір-біріңе жақсы үйлеседі."

        if c.get("lifestyle") == "quiet" or c.get("parties") == "undesirable":
            habit = "Үйде тыныштық пен тазалықты жақсы көресіңдер."
        else:
            habit = "Бюджеттерің мен тазалыққа көзқарастарың толық сай келеді."

        return f"💡 **Неге саған сәйкес келеді:**\n{occ} {habit}"
    else:
        if user_occ == cand_occ and user_occ in ("student", "учусь"):
            occ = "Вы оба учитесь — схожий график и ритм жизни."
        elif user_occ == cand_occ and user_occ in ("working", "работает"):
            occ = "Вы оба работаете — цените спокойствие и тишину по вечерам."
        else:
            occ = "Ваши графики жизни комфортно дополняют друг друга."

        if c.get("lifestyle") == "quiet" or c.get("parties") == "undesirable":
            habit = "Оба любите порядок и спокойную атмосферу дома."
        else:
            habit = "Бюджеты и взгляды на уют в квартире полностью совпадают."

        return f"💡 **Почему подходит тебе:**\n{occ} {habit}"

