from pydantic import BaseModel


class NotificationPreferencesOut(BaseModel):
    email: bool = True
    in_app: bool = True
    email_info_level: bool = False


class NotificationPreferencesUpdate(BaseModel):
    email: bool | None = None
    in_app: bool | None = None
    email_info_level: bool | None = None
