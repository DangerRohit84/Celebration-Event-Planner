"""Pure serializers: domain objects -> JSON-ready dictionaries.

The HTTP layer stays a thin Interface Adapter: handlers parse the request,
call the domain, and hand the domain result to a serializer. No handler
builds response payloads with inline dict comprehensions.

The event serializers live in :mod:`backend.app.event_serializers`, the
answer serializers (citations, idea strings) in
:mod:`backend.app.answer_serializers`, and the export serializer in
:mod:`backend.app.export_serializers`; all are re-exported here so the
historical import path keeps working.
"""

from __future__ import annotations

from .answer_serializers import citation_dict as citation_dict
from .answer_serializers import citation_dicts as citation_dicts
from .answer_serializers import idea_texts as idea_texts
from .event_serializers import budget_line_dict as budget_line_dict
from .event_serializers import event_detail as event_detail
from .event_serializers import event_summary as event_summary
from .event_serializers import milestone_dict as milestone_dict
from .event_serializers import vendor_dict as vendor_dict
from .export_serializers import event_plan_dict as event_plan_dict
