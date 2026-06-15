#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::lighting {

#ifndef GHOSTRIGGER_TOOLS_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_TOOLS_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& labelenum_label_line_10_42314437_native();
const NativeFunctionImplementation& lightmapbakeresult_ok_line_60_9ef51b3b_native();
const NativeFunctionImplementation& uvvalidationresult_severity_line_21_423b2cfe_native();
const NativeFunctionImplementation& emitterparticle_alive_line_128_a4b27223_native();
const NativeFunctionImplementation& emitterparticle_normalized_age_line_133_0012faed_native();
const NativeFunctionImplementation& particleemitter_particle_count_line_433_b4429143_native();
const NativeFunctionImplementation& particleemitter_particles_line_438_9d155a19_native();
const NativeFunctionImplementation& particleemitter_elapsed_time_line_443_31e08c77_native();
const NativeFunctionImplementation& lightningemitter_bolt_points_line_562_7e1c2546_native();
const NativeFunctionImplementation& emittermanager_emitter_count_line_615_0ec80333_native();
const NativeFunctionImplementation& emittermanager_total_particles_line_619_28ad1d33_native();
const NativeFunctionImplementation& scenelightingrenderdata_enabled_lights_line_70_6ce78c48_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::lighting
