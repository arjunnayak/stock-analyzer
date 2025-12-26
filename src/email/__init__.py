"""Email delivery system for Material Changes alerts."""

from src.email.sender import EmailConfig, EmailSender
from src.email.templates import EmailTemplates

__all__ = ["EmailConfig", "EmailSender", "EmailTemplates"]
