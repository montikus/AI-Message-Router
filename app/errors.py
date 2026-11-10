class RouterError(Exception):
    status_code = 502
    detail = "Message routing failed."


class ModelUnavailable(RouterError):
    status_code = 503
    detail = "Ollama is unavailable or the model is not ready."


# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
class ModelTimeout(RouterError):
    status_code = 504
    detail = "Ollama timed out before email dispatch."


class InvalidToolCall(RouterError):
    detail = "The model did not produce one valid send_email tool call. No email was sent."


class MailDeliveryError(RouterError):
    detail = "SMTP did not confirm delivery. Check Mailpit before retrying."
