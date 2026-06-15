#pragma once

#ifdef GHOSTRIGGER_MATH_EXPORTS
#define GHOSTRIGGER_MATH_API __declspec(dllexport)
#else
#define GHOSTRIGGER_MATH_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_MATH_API const char* gr_math_version();
GHOSTRIGGER_MATH_API const char* gr_math_capabilities_json();
GHOSTRIGGER_MATH_API const char* gr_math_owner_boundary_json();
GHOSTRIGGER_MATH_API const char* gr_math_dependency_schema_json();
}