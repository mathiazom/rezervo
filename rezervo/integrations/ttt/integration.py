from rezervo.integrations.integration import Integration
from rezervo.providers.active import get_provider
from rezervo.schemas.config.user import IntegrationIdentifier, ProviderIdentifier

brp_provider = get_provider(ProviderIdentifier.BRP)(IntegrationIdentifier.TTT, 1)

integration = Integration(
    find_authed_class_by_id=brp_provider.find_authed_class_by_id,
    find_class=brp_provider.find_class,
    book_class=brp_provider.book_class,
    cancel_booking=brp_provider.cancel_booking,
    fetch_sessions=brp_provider.fetch_sessions,
    rezervo_class_from_class_data=brp_provider.rezervo_class_from_class_data,
)
