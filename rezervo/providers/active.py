from rezervo.providers.brpsystems.provider import get_brp_provider
from rezervo.providers.ibooking.provider import get_ibooking_provider
from rezervo.schemas.config.user import ProviderIdentifier

ACTIVE_PROVIDERS = {
    ProviderIdentifier.BRP: get_brp_provider,
    ProviderIdentifier.IBOOKING: get_ibooking_provider,
}


def get_provider(provider: ProviderIdentifier):
    if provider not in ACTIVE_PROVIDERS:
        raise ValueError(f"Provider {provider} is not active.")
    return ACTIVE_PROVIDERS[provider]
