#include "ValidationBus.h"

#include <cctype>
#include <string>

namespace ghostrigger::core::validation::core::validation::validation_bus {
namespace {

std::string normalized(std::string_view value) {
    std::string result;
    result.reserve(value.size());
    for (const unsigned char character : value) {
        result.push_back(static_cast<char>(std::tolower(character)));
    }
    return result;
}

} // namespace

ValidationSeverity coerce_severity(std::string_view value) noexcept {
    const std::string candidate = normalized(value.empty() ? "error" : value);
    if (candidate == "info") {
        return ValidationSeverity::Info;
    }
    if (candidate == "warning") {
        return ValidationSeverity::Warning;
    }
    if (candidate == "error") {
        return ValidationSeverity::Error;
    }
    if (candidate == "blocking") {
        return ValidationSeverity::Blocking;
    }
    return ValidationSeverity::Invalid;
}

ValidationSubsystem coerce_subsystem(std::string_view value) noexcept {
    const std::string candidate = normalized(value.empty() ? "project" : value);
    if (candidate == "project") {
        return ValidationSubsystem::Project;
    }
    if (candidate == "character") {
        return ValidationSubsystem::Character;
    }
    if (candidate == "retarget") {
        return ValidationSubsystem::Retarget;
    }
    if (candidate == "module") {
        return ValidationSubsystem::Module;
    }
    if (candidate == "map") {
        return ValidationSubsystem::Map;
    }
    if (candidate == "scenario") {
        return ValidationSubsystem::Scenario;
    }
    if (candidate == "script") {
        return ValidationSubsystem::Script;
    }
    if (candidate == "export") {
        return ValidationSubsystem::Export;
    }
    if (candidate == "resource") {
        return ValidationSubsystem::Resource;
    }
    if (candidate == "viewport") {
        return ValidationSubsystem::Viewport;
    }
    return ValidationSubsystem::Invalid;
}

const char* severity_to_string(ValidationSeverity severity) noexcept {
    switch (severity) {
    case ValidationSeverity::Info:
        return "info";
    case ValidationSeverity::Warning:
        return "warning";
    case ValidationSeverity::Error:
        return "error";
    case ValidationSeverity::Blocking:
        return "blocking";
    case ValidationSeverity::Invalid:
    default:
        return "";
    }
}

const char* subsystem_to_string(ValidationSubsystem subsystem) noexcept {
    switch (subsystem) {
    case ValidationSubsystem::Project:
        return "project";
    case ValidationSubsystem::Character:
        return "character";
    case ValidationSubsystem::Retarget:
        return "retarget";
    case ValidationSubsystem::Module:
        return "module";
    case ValidationSubsystem::Map:
        return "map";
    case ValidationSubsystem::Scenario:
        return "scenario";
    case ValidationSubsystem::Script:
        return "script";
    case ValidationSubsystem::Export:
        return "export";
    case ValidationSubsystem::Resource:
        return "resource";
    case ValidationSubsystem::Viewport:
        return "viewport";
    case ValidationSubsystem::Invalid:
    default:
        return "";
    }
}

int severity_rank(ValidationSeverity severity) noexcept {
    switch (severity) {
    case ValidationSeverity::Info:
        return 0;
    case ValidationSeverity::Warning:
        return 1;
    case ValidationSeverity::Error:
        return 2;
    case ValidationSeverity::Blocking:
        return 3;
    case ValidationSeverity::Invalid:
    default:
        return -1;
    }
}

int severity_rank(std::string_view severity) noexcept {
    return severity_rank(coerce_severity(severity));
}

bool is_valid_severity(std::string_view value) noexcept {
    return coerce_severity(value) != ValidationSeverity::Invalid;
}

bool is_valid_subsystem(std::string_view value) noexcept {
    return coerce_subsystem(value) != ValidationSubsystem::Invalid;
}

const char* severity_values_json() noexcept {
    static constexpr const char* kJson = R"(["info","warning","error","blocking"])";
    return kJson;
}

const char* subsystem_values_json() noexcept {
    static constexpr const char* kJson =
        R"(["project","character","retarget","module","map","scenario","script","export","resource","viewport"])";
    return kJson;
}

const char* validation_bus_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"validation_bus_native.v1",)"
        R"("source":"src/core/validation/validation_bus.py",)"
        R"("native_scope":["ValidationSeverity","ValidationSubsystem","severity_rank","severity_subsystem_coercion"],)"
        R"("python_fallback":["ValidationBus publish/subscribe lifecycle","ValidationReport object graph","ValidationIssue SHA1 issue ids","ResourceAddress object serialization"],)"
        R"("reason_python_fallback":"the remaining bus lifecycle still depends on Python callbacks, dataclass object graphs, and ResourceAddress Python objects until their callers are ported subsystem-by-subsystem"})";
    return kJson;
}

} // namespace ghostrigger::core::validation::core::validation::validation_bus
