from rezervo.integrations.integration import Integration
from rezervo.providers.active import get_provider
from rezervo.schemas.config.user import IntegrationIdentifier, ProviderIdentifier

ibooking_provider = get_provider(ProviderIdentifier.IBOOKING)(IntegrationIdentifier.SIT)

integration = Integration(
    find_authed_class_by_id=ibooking_provider.find_authed_class_by_id,
    find_class=ibooking_provider.find_class,
    book_class=ibooking_provider.book_class,
    cancel_booking=ibooking_provider.cancel_booking,
    fetch_sessions=ibooking_provider.fetch_sessions,
    rezervo_class_from_class_data=ibooking_provider.rezervo_class_from_class_data,
)
