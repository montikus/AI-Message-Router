import logging
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from uuid import UUID

# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
from app.config import Settings
from app.errors import MailDeliveryError
from app.schemas import MessageRequest, MessageResponse, SendEmailArguments

logger = logging.getLogger(__name__)


class EmailTool:
    """The agent's terminal tool; only validated arguments reach SMTP."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def send_email(
        self, arguments: SendEmailArguments, original: MessageRequest, request_id: UUID
    ) -> MessageResponse:
        message = EmailMessage()
        message["From"] = str(self.settings.mail_from)
        message["To"] = arguments.recipient.value
        message["Reply-To"] = str(original.email)
        message["Subject"] = f"Zgloszenie / Ticket {request_id}"
        message["Date"] = formatdate(localtime=False)
        message["Message-ID"] = make_msgid(domain="router.example.com")
        message["X-Request-ID"] = str(request_id)
        message.set_content(original.message, charset="utf-8")

        try:
            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                local_hostname="router.local",
                timeout=self.settings.smtp_timeout,
            ) as smtp:
                refused = smtp.send_message(
                    message,
                    from_addr=str(self.settings.mail_from),
                    to_addrs=[arguments.recipient.value],
                )
                if refused:
                    raise MailDeliveryError()
        except (OSError, smtplib.SMTPException) as exc:
            # Do not retry SMTP: acceptance may precede a lost acknowledgement.
            raise MailDeliveryError() from exc

        logger.info("email_sent request_id=%s recipient=%s", request_id, arguments.recipient)
        return MessageResponse(
            request_id=request_id,
            recipient=arguments.recipient,
            message_id=str(message["Message-ID"]),
        )

    def check_connection(self) -> None:
        with smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            local_hostname="router.local",
            timeout=self.settings.smtp_timeout,
        ) as smtp:
            code, _ = smtp.noop()
            if code != 250:
                raise OSError("SMTP readiness check failed")
