class DomainError(Exception):
    """Готовая ошибка. Проверяется code, а не текст traceback."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
