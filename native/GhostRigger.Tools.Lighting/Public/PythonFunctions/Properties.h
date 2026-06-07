#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_lighting {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_lighting_light_types_labelenum_label_line_10_42314437_descriptor_json();
const char* src_core_lighting_lightmap_bake_job_lightmapbakeresult_ok_line_60_9ef51b3b_descriptor_json();
const char* src_core_lighting_lightmap_uv_validator_uvvalidationresult_severity_line_21_423b2cfe_descriptor_json();
const char* src_core_lighting_particle_emitter_emitterparticle_alive_line_128_a4b27223_descriptor_json();
const char* src_core_lighting_particle_emitter_emitterparticle_normalized_age_line_133_0012faed_descriptor_json();
const char* src_core_lighting_particle_emitter_particleemitter_particle_count_line_433_b4429143_descriptor_json();
const char* src_core_lighting_particle_emitter_particleemitter_particles_line_438_9d155a19_descriptor_json();
const char* src_core_lighting_particle_emitter_particleemitter_elapsed_time_line_443_31e08c77_descriptor_json();
const char* src_core_lighting_particle_emitter_lightningemitter_bolt_points_line_562_7e1c2546_descriptor_json();
const char* src_core_lighting_particle_emitter_emittermanager_emitter_count_line_615_0ec80333_descriptor_json();
const char* src_core_lighting_particle_emitter_emittermanager_total_particles_line_619_28ad1d33_descriptor_json();
const char* src_core_lighting_render_data_scenelightingrenderdata_enabled_lights_line_70_6ce78c48_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_lighting
