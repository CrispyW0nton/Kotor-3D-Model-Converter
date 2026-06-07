#pragma once

#include <string_view>

namespace ghostrigger::validation::core::validation::validation_bus {

enum class ValidationSeverity {
    Info,
    Warning,
    Error,
    Blocking,
    Invalid,
};

enum class ValidationSubsystem {
    Project,
    Character,
    Retarget,
    Module,
    Map,
    Scenario,
    Script,
    Export,
    Resource,
    Viewport,
    Invalid,
};

ValidationSeverity coerce_severity(std::string_view value) noexcept;
ValidationSubsystem coerce_subsystem(std::string_view value) noexcept;
const char* severity_to_string(ValidationSeverity severity) noexcept;
const char* subsystem_to_string(ValidationSubsystem subsystem) noexcept;
int severity_rank(ValidationSeverity severity) noexcept;
int severity_rank(std::string_view severity) noexcept;
bool is_valid_severity(std::string_view value) noexcept;
bool is_valid_subsystem(std::string_view value) noexcept;
const char* severity_values_json() noexcept;
const char* subsystem_values_json() noexcept;
const char* validation_bus_schema_json() noexcept;

} // namespace ghostrigger::validation::core::validation::validation_bus
