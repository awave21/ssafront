from __future__ import annotations

# Единственный источник "текстов для LLM" по SQNS тулам.
# Эти описания должны быть одинаковыми для:
# - Legacy tool definitions (schemas/agent.py)
# - FastMCP toolset (services/sqns_mcp_server.py)

SQNS_TOOL_DESCRIPTIONS: dict[str, str] = {
    "sqns_find_booking_options": (
        "FIRST STEP BEFORE BOOKING. Use this tool to search for available services and staff. "
        "IMPORTANT: If the knowledge base (search_knowledge_base) indicates that a service has subtypes, "
        "clarify the client's choice first, then call this tool with the specific name. "
        "Returns IDs needed for sqns_list_slots."
    ),
    "sqns_list_resources": (
        "Fallback: full list of staff members (resource_id, name, specialty). "
        "Use only if sqns_find_booking_options does not fit the task."
    ),
    "sqns_list_services": (
        "Fallback: full list of services (service_id, name, duration, price). "
        "Use only if sqns_find_booking_options does not fit the task."
    ),
    "sqns_find_client": (
        "Search for a client by phone number to retrieve their name and contact details. "
        "Use before creating a booking or when client data needs to be verified. "
        "Do NOT use to search for bookings — use sqns_client_visits (preferred) or sqns_list_visits instead. "
        "Returns an empty result if the client is not found."
    ),
    "sqns_list_slots": (
        "CHECK AVAILABILITY. Call ONLY after the client has confirmed their choice of service and staff member. "
        "Offer the client 2-3 time options from the returned list. Do not suggest times at random."
    ),
    "sqns_create_visit": (
        "FINALIZE BOOKING. Call only after the client has selected a specific slot and confirmed their details (name and phone). "
        "Before calling, make sure you have answered all clarifying questions from the client using the knowledge base."
    ),
    "sqns_update_visit": "Update a booking: reschedule, change comment, or update status.",
    "sqns_list_visits": (
        "List of a client's bookings for a period, looked up by phone number. "
        "This tool already verifies the client by phone, so sqns_find_client does NOT need to be called first. "
        "Do not use to browse the general schedule."
    ),
    "sqns_client_visits": (
        "PRIMARY tool for finding a client's booking by phone and date (or date range) in a compact format. "
        "Use when you need to find a booking to reschedule or cancel without extra data. "
        "sqns_find_client does NOT need to be called before this tool."
    ),
    "sqns_delete_visit": (
        "Delete (cancel) a booking by visit_id. "
        "Before deleting, verify that the booking belongs to the client (by phone number)."
    ),
}


def get_sqns_tool_description(tool_name: str) -> str:
    return SQNS_TOOL_DESCRIPTIONS.get(tool_name, "")

