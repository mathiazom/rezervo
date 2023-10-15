from rezervo.providers.active import get_provider
from rezervo.providers.brpsystems.schema import BrpSubdomain
from rezervo.providers.ibooking.schema import IBookingDomain
from rezervo.schemas.config.user import IntegrationIdentifier, ProviderIdentifier

ACTIVE_INTEGRATIONS = {
    IntegrationIdentifier.SIT: get_provider(ProviderIdentifier.IBOOKING)(
        IBookingDomain.SIT
    ),
    IntegrationIdentifier.FSC: get_provider(ProviderIdentifier.BRP)(
        BrpSubdomain.FSC, 8
    ),
    IntegrationIdentifier.TTT: get_provider(ProviderIdentifier.BRP)(
        BrpSubdomain.TTT, 1
    ),
}


def get_integration(integration: IntegrationIdentifier):
    if integration not in ACTIVE_INTEGRATIONS:
        raise ValueError(f"Integration {integration} is not active.")
    return ACTIVE_INTEGRATIONS[integration]
