class APIError(Exception):
    def __init__(self, code, message, status=422, **extra):
        self.code, self.message, self.status, self.extra = code, message, status, extra

