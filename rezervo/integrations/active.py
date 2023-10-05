from rezervo.integrations.fsc.integration import integration as fsc_integration
from rezervo.integrations.sit.integration import integration as sit_integration
from rezervo.schemas.config.user import IntegrationIdentifier

ACTIVE_INTEGRATIONS = {
    IntegrationIdentifier.SIT: sit_integration,
    IntegrationIdentifier.FSC: fsc_integration,
}


def get_integration(integration: IntegrationIdentifier):
    if integration not in ACTIVE_INTEGRATIONS:
        raise ValueError(f"Integration {integration} is not active.")
    return ACTIVE_INTEGRATIONS[integration]
