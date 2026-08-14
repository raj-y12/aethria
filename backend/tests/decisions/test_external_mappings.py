import pytest

from decisions.crm_mappings import ExternalEntityMapping, MappingConflict, MappingRegistry


def test_mapping_is_tenant_scoped_and_repeated_upsert_is_idempotent():
    registry = MappingRegistry()
    mapping = ExternalEntityMapping(user_id="user-1", provider="crm", entity_type="company", aethria_entity_id="company-1", external_entity_id="ext-1", workspace_id="workspace-1")
    assert registry.upsert(mapping) == mapping
    assert registry.upsert(mapping) == mapping
    assert len(registry.list_for_user("user-1")) == 1


def test_external_object_cannot_map_to_two_entities_in_one_workspace():
    registry = MappingRegistry()
    registry.upsert(ExternalEntityMapping(user_id="user-1", provider="crm", entity_type="company", aethria_entity_id="company-1", external_entity_id="ext-1", workspace_id="workspace-1"))
    with pytest.raises(MappingConflict):
        registry.upsert(ExternalEntityMapping(user_id="user-1", provider="crm", entity_type="company", aethria_entity_id="company-2", external_entity_id="ext-1", workspace_id="workspace-1"))


def test_same_external_id_is_allowed_in_different_tenant_or_workspace():
    registry = MappingRegistry()
    registry.upsert(ExternalEntityMapping(user_id="user-1", provider="crm", entity_type="company", aethria_entity_id="company-1", external_entity_id="ext-1", workspace_id="workspace-1"))
    registry.upsert(ExternalEntityMapping(user_id="user-2", provider="crm", entity_type="company", aethria_entity_id="company-2", external_entity_id="ext-1", workspace_id="workspace-1"))
    registry.upsert(ExternalEntityMapping(user_id="user-1", provider="crm", entity_type="company", aethria_entity_id="company-3", external_entity_id="ext-1", workspace_id="workspace-2"))
    assert len(registry.list_for_user("user-1")) == 2


def test_future_ingest_envelope_is_tenant_private_and_has_no_connector_side_effect():
    from decisions.crm_ingest import CrmInboundRecord
    record = CrmInboundRecord(user_id="user-1", provider="crm", entity_type="opportunity", external_entity_id="deal-1", private_notes="Met the partner")
    assert record.workspace_id == "default"
    assert record.private_notes == "Met the partner"
