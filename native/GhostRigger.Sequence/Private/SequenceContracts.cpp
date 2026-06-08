#include "SequenceContracts.h"

#include <algorithm>
#include <cmath>
#include <string>

namespace ghostrigger::sequence::core::sequence::contracts {
namespace {

std::string clean(const char* value) {
    return value == nullptr ? std::string() : std::string(value);
}

double safe_frame_rate(double value) noexcept {
    if (!std::isfinite(value) || value <= 0.0) {
        return 24.0;
    }
    return value;
}

} // namespace

const char* normalize_interpolation_mode(const char* mode) noexcept {
    const std::string value = clean(mode);
    if (value == "Constant" || value == "Linear" || value == "Ease In" || value == "Ease Out" ||
        value == "Ease In Out" || value == "Cubic") {
        if (value == "Constant") {
            return "Constant";
        }
        if (value == "Ease In") {
            return "Ease In";
        }
        if (value == "Ease Out") {
            return "Ease Out";
        }
        if (value == "Ease In Out") {
            return "Ease In Out";
        }
        if (value == "Cubic") {
            return "Cubic";
        }
    }
    return "Linear";
}

double ease(double t, const char* mode) noexcept {
    t = std::clamp(t, 0.0, 1.0);
    const std::string interp = normalize_interpolation_mode(mode);
    if (interp == "Ease In") {
        return t * t;
    }
    if (interp == "Ease Out") {
        return 1.0 - (1.0 - t) * (1.0 - t);
    }
    if (interp == "Ease In Out" || interp == "Cubic") {
        return t * t * (3.0 - 2.0 * t);
    }
    return t;
}

double lerp_number(double a, double b, double t) noexcept {
    return a + (b - a) * t;
}

double interpolate_number(double a, double b, double t, const char* mode) noexcept {
    const std::string interp = normalize_interpolation_mode(mode);
    if (interp == "Constant") {
        return a;
    }
    return lerp_number(a, b, ease(t, interp.c_str()));
}

int interpolate_bool(int a, int b, double t, const char* mode) noexcept {
    const std::string interp = normalize_interpolation_mode(mode);
    if (interp == "Constant") {
        return a ? 1 : 0;
    }
    return ease(t, interp.c_str()) < 1.0 ? (a ? 1 : 0) : (b ? 1 : 0);
}

int clamp_frame(int frame, int start_frame, int end_frame) noexcept {
    return std::max(start_frame, std::min(end_frame, static_cast<int>(std::nearbyint(static_cast<double>(frame)))));
}

double frame_to_seconds(int frame, int start_frame, double frame_rate) noexcept {
    return static_cast<double>(frame - start_frame) / safe_frame_rate(frame_rate);
}

int seconds_to_frame(double seconds, int start_frame, int end_frame, double frame_rate) noexcept {
    const int frame = static_cast<int>(std::nearbyint(seconds * safe_frame_rate(frame_rate))) + start_frame;
    return clamp_frame(frame, start_frame, end_frame);
}

int duration_frames(int start_frame, int end_frame) noexcept {
    return std::max(0, end_frame - start_frame);
}

double duration_seconds(int start_frame, int end_frame, double frame_rate) noexcept {
    return static_cast<double>(duration_frames(start_frame, end_frame)) / safe_frame_rate(frame_rate);
}

const char* sequence_contracts_schema_json() noexcept {
    return R"({"schema":"sequence_contracts_native.v1",)"
           R"("source":["src/sequence/sequence_interpolation.py","src/sequence/sequence_model.py","src/sequence/sequence_keyframe.py"],)"
           R"("native_scope":["interpolation mode normalization","easing curves","numeric interpolation","boolean interpolation","sequence frame-time conversion","sequence duration math"],)"
           R"("python_fallback":["mapping/list recursive interpolation","keyframe object sorting/evaluation","track mutation","sequence serialization","asset file IO","viewport/object evaluator application","render output"],)"
           R"("reason_python_fallback":"Recursive Python value interpolation and runtime sequence objects stay Python-owned until track and evaluator objects are ported together"})";
}

} // namespace ghostrigger::sequence::core::sequence::contracts

extern "C" {

__declspec(dllexport) const char* gr_sequence_interpolation_mode(const char* mode) {
    return ghostrigger::sequence::core::sequence::contracts::normalize_interpolation_mode(mode);
}

__declspec(dllexport) double gr_sequence_ease(double t, const char* mode) {
    return ghostrigger::sequence::core::sequence::contracts::ease(t, mode);
}

__declspec(dllexport) double gr_sequence_lerp_number(double a, double b, double t) {
    return ghostrigger::sequence::core::sequence::contracts::lerp_number(a, b, t);
}

__declspec(dllexport) double gr_sequence_interpolate_number(double a, double b, double t, const char* mode) {
    return ghostrigger::sequence::core::sequence::contracts::interpolate_number(a, b, t, mode);
}

__declspec(dllexport) int gr_sequence_interpolate_bool(int a, int b, double t, const char* mode) {
    return ghostrigger::sequence::core::sequence::contracts::interpolate_bool(a, b, t, mode);
}

__declspec(dllexport) int gr_sequence_clamp_frame(int frame, int start_frame, int end_frame) {
    return ghostrigger::sequence::core::sequence::contracts::clamp_frame(frame, start_frame, end_frame);
}

__declspec(dllexport) double gr_sequence_frame_to_seconds(int frame, int start_frame, double frame_rate) {
    return ghostrigger::sequence::core::sequence::contracts::frame_to_seconds(frame, start_frame, frame_rate);
}

__declspec(dllexport) int gr_sequence_seconds_to_frame(double seconds, int start_frame, int end_frame, double frame_rate) {
    return ghostrigger::sequence::core::sequence::contracts::seconds_to_frame(seconds, start_frame, end_frame, frame_rate);
}

__declspec(dllexport) int gr_sequence_duration_frames(int start_frame, int end_frame) {
    return ghostrigger::sequence::core::sequence::contracts::duration_frames(start_frame, end_frame);
}

__declspec(dllexport) double gr_sequence_duration_seconds(int start_frame, int end_frame, double frame_rate) {
    return ghostrigger::sequence::core::sequence::contracts::duration_seconds(start_frame, end_frame, frame_rate);
}

__declspec(dllexport) const char* gr_sequence_contracts_schema_json() {
    return ghostrigger::sequence::core::sequence::contracts::sequence_contracts_schema_json();
}

}
