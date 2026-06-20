#pragma once

namespace ghostrigger::core::diagnostics::core::diagnostics::contracts {

const char* normalize_resref(const char* value) noexcept;
const char* normalize_restype(const char* value) noexcept;
int is_script_field(const char* field_name) noexcept;
int is_dialog_field(const char* field_name) noexcept;
const char* missing_reference_issue_json(
    const char* kind,
    const char* resref,
    const char* restype,
    const char* owner_type,
    int owner_index,
    const char* field,
    const char* source_label) noexcept;
const char* diagnostics_contracts_schema_json() noexcept;

} // namespace ghostrigger::core::diagnostics::core::diagnostics::contracts
