#pragma once

#ifdef RUNTIME_SHARED_CONTRACTS_EXPORTS
#define RUNTIME_SHARED_CONTRACTS_API __declspec(dllexport)
#else
#define RUNTIME_SHARED_CONTRACTS_API __declspec(dllimport)
#endif

extern "C" {

RUNTIME_SHARED_CONTRACTS_API const char* gr_runtime_shared_contracts_version();
RUNTIME_SHARED_CONTRACTS_API const char* gr_runtime_shared_contracts_capabilities_json();
RUNTIME_SHARED_CONTRACTS_API const char* gr_runtime_shared_contracts_renderer_descriptor_json();

}
