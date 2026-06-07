#include "GhostRiggerDeviceResources.h"

namespace ghostrigger::runtime::device_resources {

bool ensure_handle(std::uint64_t& handle, std::uint64_t& next_handle) {
    if (handle != 0) {
        return false;
    }

    handle = next_handle;
    next_handle += 1;
    return true;
}

bool generation_matches(std::uint64_t stored_generation, std::uint64_t generation) {
    return stored_generation == generation;
}

bool upload_matches(std::uint64_t handle, std::uint64_t uploaded_generation, std::uint64_t generation) {
    return handle != 0 && uploaded_generation == generation;
}

void mark_uploaded(std::uint64_t generation, std::uint64_t& uploaded_generation, std::uint32_t& state) {
    uploaded_generation = generation;
    state = kResourceStateUpload;
}

TransitionResult transition_uploaded_resource(
    std::uint64_t handle,
    std::uint64_t uploaded_generation,
    std::uint64_t generation,
    std::uint32_t desired_state,
    std::uint32_t& current_state
) {
    TransitionResult result{};
    result.before_state = current_state;
    result.after_state = desired_state;

    if (!upload_matches(handle, uploaded_generation, generation)) {
        result.before_state = kResourceStateMissing;
        result.after_state = kResourceStateMissing;
        result.status = kStatusMissing;
        result.missing_upload = true;
        return result;
    }

    result.missing_upload = false;
    if (current_state == desired_state) {
        result.status = kStatusReused;
        result.already_ready = true;
        return result;
    }

    current_state = desired_state;
    result.status = kStatusReady;
    result.transitioned = true;
    return result;
}

} // namespace ghostrigger::runtime::device_resources
