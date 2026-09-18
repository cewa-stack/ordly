"""
Import wszystkich modeli ORM w jednym miejscu.

To jest krytyczne dla Alembic autogenerate - jeśli model nie
zostanie tu zaimportowany, Alembic go nie "zobaczy" i nie
wygeneruje dla niego migracji, mimo że dziedziczy po Base.
"""

from app.database.models.event_model import EventModel
from app.database.models.mail_message_model import MailMessageModel
from app.database.models.marketplace_offer_model import MarketplaceOfferModel
from app.database.models.offer_stock_movement_model import OfferStockMovementModel
from app.database.models.order_model import OrderModel
from app.database.models.ordlak_conversation_model import (
    OrdlakConversationModel,
    OrdlakMessageModel,
)
from app.database.models.product_model import ProductModel
from app.database.models.push_subscription_model import PushSubscriptionModel
from app.database.models.return_model import ReturnModel
from app.database.models.settings_model import SettingsModel
from app.database.models.shipment_model import ShipmentModel
from app.database.models.sms_message_model import SmsMessageModel
from app.database.models.telegram_message_model import TelegramMessageModel
from app.database.models.token_model import TokenModel

__all__ = [
    "EventModel",
    "MailMessageModel",
    "MarketplaceOfferModel",
    "OfferStockMovementModel",
    "OrdlakConversationModel",
    "OrdlakMessageModel",
    "OrderModel",
    "ProductModel",
    "PushSubscriptionModel",
    "ReturnModel",
    "SettingsModel",
    "ShipmentModel",
    "SmsMessageModel",
    "TelegramMessageModel",
    "TokenModel",
]
