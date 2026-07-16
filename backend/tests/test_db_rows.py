from uuid import uuid4

from utils.db_rows import db_row, json_ready_db_value


def test_direct_postgres_uuid_values_are_normalized_recursively():
    root = uuid4()
    nested = uuid4()
    value = db_row({"id": root, "payload": {"ids": [nested]}})
    assert value == {"id": str(root), "payload": {"ids": [str(nested)]}}
    assert json_ready_db_value((root,)) == [str(root)]
