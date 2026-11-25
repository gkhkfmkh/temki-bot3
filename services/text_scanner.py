from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class ScanIssue:
    phrase: str
    level: str
    explanation: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class ScanResult:
    risk: str
    issues: tuple[ScanIssue, ...]
    advice: str


RULES = [
    (r"https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+", "HIGH",
     "Внешняя ссылка может уводить пользователя с площадки.",
     "Удалите внешнюю ссылку и оставьте покупателю информацию, необходимую для оформления заказа на площадке."),
    (r"\b(?:telegram|телеграм|телега|whatsapp|ватсап|discord|дискорд)\b", "HIGH",
     "Упоминание стороннего мессенджера может восприниматься как перенос общения за пределы площадки.",
     "Используйте предусмотренный площадкой канал коммуникации."),
    (r"\b(?:в обход площадки|мимо площадки|оплата напрямую|перевод на карту|вне площадки|уйти с площадки)\b", "HIGH",
     "Фраза может указывать на проведение оплаты или сделки вне площадки.",
     "Оставьте оплату и оформление заказа в предусмотренном площадкой процессе."),
    (r"\b(?:скидка за отзыв|положительный отзыв за бонус|накрутка отзывов)\b", "HIGH",
     "Вознаграждение за отзыв может противоречить правилам площадки.",
     "Не связывайте бонусы или скидки с оценкой и содержанием отзыва."),
    (r"\b(?:гарант|гарантия|дешево|слив|обход|личка|в лс)\b", "MEDIUM",
     "Неоднозначная формулировка. Риск зависит от контекста.",
     "Замените общие обещания конкретными условиями, сроком, комплектацией и ограничениями."),
    (r"\b(?:пароль|код из sms|код подтверждения|данные карты)\b", "MEDIUM",
     "Упоминание чувствительных данных требует осторожности.",
     "Не запрашивайте пароли, одноразовые коды и платёжные данные."),
]


def scan_text(text: str) -> ScanResult:
    issues: list[ScanIssue] = []
    seen: set[str] = set()
    for pattern, level, explanation, recommendation in RULES:
        for match in re.finditer(pattern, text or "", flags=re.IGNORECASE):
            phrase = match.group(0).strip()
            key = phrase.casefold()
            if key not in seen:
                seen.add(key)
                issues.append(ScanIssue(phrase, level, explanation, recommendation))
    if any(item.level == "HIGH" for item in issues):
        risk = "Высокий"
        advice = "Переработайте отмеченные места. Не предлагайте обходить правила, переводить оплату вне площадки или переносить сделку в сторонние каналы."
    elif issues:
        risk = "Средний"
        advice = "Проверьте контекст отмеченных фраз и сформулируйте условия товара нейтрально и конкретно."
    else:
        risk = "Безопасно по текущему словарю"
        advice = "Совпадений в текущем словаре нет. Это не гарантия модерации: проверьте текст и актуальные правила площадки."
    return ScanResult(risk, tuple(issues), advice)
