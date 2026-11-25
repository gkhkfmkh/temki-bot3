from aiogram.fsm.state import State, StatesGroup


class ProfitFlow(StatesGroup):
    cost = State()
    sale = State()
    fee = State()


class ReverseFlow(StatesGroup):
    target = State()
    fee = State()


class TaxFlow(StatesGroup):
    amount = State()
    percent = State()


class ListingBuilder(StatesGroup):
    title = State()
    delivery = State()
    timing = State()
    requirements = State()
    extras = State()


class ScanFlow(StatesGroup):
    text = State()


class SubmissionFlow(StatesGroup):
    content = State()


class AdminReplyFlow(StatesGroup):
    text = State()


class BroadcastFlow(StatesGroup):
    segment = State()
    content = State()
    confirm = State()
