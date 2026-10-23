"""SQLite backend: vendor operations."""

from __future__ import annotations

from ..models import Vendor
from .sqlite_base import SQLiteBase


class SQLiteVendors(SQLiteBase):
    """Vendor persistence against the ``vendors`` table."""

    def add_vendor(self, v: Vendor) -> Vendor:
        """Append a vendor to an event.
        Args:
            v: Vendor to store against its event.
        Returns:
            The stored vendor.
        """
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO vendors (id,event_id,category,name,status,cost_estimate,contact,notes) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        v.id,
                        v.event_id,
                        v.category,
                        v.name,
                        v.status.value if hasattr(v.status, "value") else str(v.status),
                        v.cost_estimate,
                        v.contact,
                        v.notes,
                    ),
                )
                conn.commit()
            return v

    def list_vendors(self, event_id: str) -> list[Vendor]:
        """List the vendors of an event.
        Args:
            event_id: Identifier of the event whose vendors are requested.
        Returns:
            The vendors for the event, empty when it has none.
        """
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM vendors WHERE event_id=?", (event_id,)
                ).fetchall()
            return [self._row_to_vendor(r) for r in rows]
