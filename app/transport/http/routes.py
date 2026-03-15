from __future__ import annotations

import re
from re import Pattern

TICKET_DETAIL_RE: Pattern[str] = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)$")
TICKET_EVENTS_RE: Pattern[str] = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/events$")
TICKET_REPLY_EVENTS_RE: Pattern[str] = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/reply-events$"
)
TICKET_DUPLICATES_RE: Pattern[str] = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/duplicates$"
)
TICKET_ASSIST_RE: Pattern[str] = re.compile(r"^/api/tickets/(?P<ticket_id>[^/]+)/assist$")
TICKET_SIMILAR_RE: Pattern[str] = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/similar-cases$"
)
TICKET_GROUNDING_RE: Pattern[str] = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/grounding-sources$"
)
TICKET_PENDING_ACTIONS_RE: Pattern[str] = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/pending-actions$"
)
TICKET_MERGE_SUGGESTION_RE: Pattern[str] = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/merge-suggestion/(?P<decision>accept|reject)$"
)
TICKET_SWITCH_ACTIVE_RE: Pattern[str] = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/switch-active$"
)
TICKET_ACTION_RE: Pattern[str] = re.compile(
    r"^/api/tickets/(?P<ticket_id>[^/]+)/(claim|reassign|escalate|resolve|close)$"
)
TICKET_ACTION_V2_RE: Pattern[str] = re.compile(
    r"^/api/v2/tickets/(?P<ticket_id>[^/]+)/(resolve|customer-confirm|operator-close)$"
)
TICKET_INVESTIGATE_V2_RE: Pattern[str] = re.compile(
    r"^/api/v2/tickets/(?P<ticket_id>[^/]+)/investigate$"
)
APPROVAL_ACTION_RE: Pattern[str] = re.compile(
    r"^/api/approvals/(?P<approval_id>[^/]+)/(approve|reject)$"
)
COPILOT_TICKET_QUERY_RE: Pattern[str] = re.compile(
    r"^/api/copilot/ticket/(?P<ticket_id>[^/]+)/query$"
)
TRACE_DETAIL_RE: Pattern[str] = re.compile(r"^/api/traces/(?P<trace_id>[^/]+)$")
KB_DOC_RE: Pattern[str] = re.compile(r"^/api/kb/(?P<doc_id>[^/]+)$")
SESSION_DETAIL_RE: Pattern[str] = re.compile(r"^/api/sessions/(?P<session_id>[^/]+)$")
SESSION_TICKETS_RE: Pattern[str] = re.compile(r"^/api/sessions/(?P<session_id>[^/]+)/tickets$")
SESSION_REPLY_EVENTS_RE: Pattern[str] = re.compile(
    r"^/api/sessions/(?P<session_id>[^/]+)/reply-events$"
)
SESSION_RESET_RE: Pattern[str] = re.compile(r"^/api/sessions/(?P<session_id>[^/]+)/reset$")
SESSION_NEW_ISSUE_RE: Pattern[str] = re.compile(
    r"^/api/sessions/(?P<session_id>[^/]+)/new-issue$"
)
SESSION_END_V2_RE: Pattern[str] = re.compile(r"^/api/v2/sessions/(?P<session_id>[^/]+)/end$")

COPILOT_DISAMBIGUATE_PATH = "/api/copilot/disambiguate"
INTAKE_GRAPH_RUN_V2_PATH = "/api/v2/intake/run"
