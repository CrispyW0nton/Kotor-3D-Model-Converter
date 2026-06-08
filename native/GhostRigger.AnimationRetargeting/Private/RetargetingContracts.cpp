#include "RetargetingContracts.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cctype>
#include <sstream>
#include <string_view>

namespace ghostrigger::animationretargeting::core::animation_retargeting::retargeter {
namespace {

constexpr double kQuatEpsilon = 1.0e-8;

struct AliasRow {
    std::string_view source;
    std::array<std::string_view, 3> aliases;
    std::size_t alias_count;
};

constexpr AliasRow kAliases[] = {
    {"rootdummy", {"root", "root_g", "dummyroot"}, 3},
    {"pelvis_g", {"pelvis", "hips", "hip_g"}, 3},
    {"torso_g", {"spine", "spine_g", "chest_g"}, 3},
    {"torsoupr_g", {"spine1", "spine_01", "chest"}, 3},
    {"neck_g", {"neck", "necklwr_g", ""}, 2},
    {"rhand", {"r_hand", "rhand_g", "hand_r"}, 3},
    {"lhand", {"l_hand", "lhand_g", "hand_l"}, 3},
    {"rfoot_g", {"rfoot", "foot_r", "r_foot"}, 3},
    {"lfoot_g", {"lfoot", "foot_l", "l_foot"}, 3},
};

std::string lower_ascii(std::string_view value) {
    std::string lowered;
    lowered.reserve(value.size());
    for (const unsigned char ch : value) {
        lowered.push_back(static_cast<char>(std::tolower(ch)));
    }
    return lowered;
}

double finite_or_zero(double value) {
    return std::isfinite(value) ? value : 0.0;
}

} // namespace

std::vector<std::string> candidate_names(const std::string& source_name) {
    const std::string key = lower_ascii(source_name);
    std::vector<std::string> candidates;
    candidates.push_back(key);

    for (const AliasRow& row : kAliases) {
        if (key == row.source) {
            for (std::size_t index = 0; index < row.alias_count; ++index) {
                candidates.push_back(lower_ascii(row.aliases[index]));
            }
            break;
        }
    }

    for (const AliasRow& row : kAliases) {
        const bool key_is_alias = std::any_of(
            row.aliases.begin(),
            row.aliases.begin() + static_cast<std::ptrdiff_t>(row.alias_count),
            [&key](std::string_view alias) { return key == alias; }
        );
        if (!key_is_alias) {
            continue;
        }
        candidates.push_back(lower_ascii(row.source));
        for (std::size_t index = 0; index < row.alias_count; ++index) {
            candidates.push_back(lower_ascii(row.aliases[index]));
        }
    }

    return candidates;
}

Vec3 sub3(Vec3 a, Vec3 b) {
    return {
        finite_or_zero(a.x) - finite_or_zero(b.x),
        finite_or_zero(a.y) - finite_or_zero(b.y),
        finite_or_zero(a.z) - finite_or_zero(b.z),
    };
}

Vec3 add3(Vec3 a, Vec3 b, double scale) {
    const double safe_scale = finite_or_zero(scale);
    return {
        finite_or_zero(a.x) + finite_or_zero(b.x) * safe_scale,
        finite_or_zero(a.y) + finite_or_zero(b.y) * safe_scale,
        finite_or_zero(a.z) + finite_or_zero(b.z) * safe_scale,
    };
}

Vec3 mul3(Vec3 a, double scale) {
    const double safe_scale = finite_or_zero(scale);
    return {
        finite_or_zero(a.x) * safe_scale,
        finite_or_zero(a.y) * safe_scale,
        finite_or_zero(a.z) * safe_scale,
    };
}

Quat normal_quat(Quat q) {
    const double x = finite_or_zero(q.x);
    const double y = finite_or_zero(q.y);
    const double z = finite_or_zero(q.z);
    const double w = finite_or_zero(q.w);
    const double length = std::sqrt(x * x + y * y + z * z + w * w);
    if (length <= kQuatEpsilon || !std::isfinite(length)) {
        return {0.0, 0.0, 0.0, 1.0};
    }
    return {x / length, y / length, z / length, w / length};
}

Quat quat_conjugate(Quat q) {
    const Quat normalized = normal_quat(q);
    return {-normalized.x, -normalized.y, -normalized.z, normalized.w};
}

Quat quat_mul(Quat a, Quat b) {
    const Quat left = normal_quat(a);
    const Quat right = normal_quat(b);
    return normal_quat({
        left.w * right.x + left.x * right.w + left.y * right.z - left.z * right.y,
        left.w * right.y - left.x * right.z + left.y * right.w + left.z * right.x,
        left.w * right.z + left.x * right.y - left.y * right.x + left.z * right.w,
        left.w * right.w - left.x * right.x - left.y * right.y - left.z * right.z,
    });
}

Quat retarget_rotation(Quat src_pose_rot, Quat src_bind_rot, Quat dst_bind_rot) {
    const Quat src_delta = quat_mul(src_pose_rot, quat_conjugate(src_bind_rot));
    return quat_mul(src_delta, dst_bind_rot);
}

double height_from_positions(const double* xyz_values, std::size_t point_count) {
    if (xyz_values == nullptr || point_count == 0) {
        return 0.0;
    }
    double min_z = finite_or_zero(xyz_values[2]);
    double max_z = min_z;
    for (std::size_t index = 0; index < point_count; ++index) {
        const double z = finite_or_zero(xyz_values[index * 3 + 2]);
        min_z = std::min(min_z, z);
        max_z = std::max(max_z, z);
    }
    return max_z - min_z;
}

} // namespace ghostrigger::animationretargeting::core::animation_retargeting::retargeter

namespace {

using ghostrigger::animationretargeting::core::animation_retargeting::retargeter::Quat;
using ghostrigger::animationretargeting::core::animation_retargeting::retargeter::Vec3;

Vec3 read_vec3(const double* values) {
    if (values == nullptr) {
        return {0.0, 0.0, 0.0};
    }
    return {values[0], values[1], values[2]};
}

Quat read_quat(const double* values) {
    if (values == nullptr) {
        return {0.0, 0.0, 0.0, 1.0};
    }
    return {values[0], values[1], values[2], values[3]};
}

int write_vec3(Vec3 value, double* out_xyz) {
    if (out_xyz == nullptr) {
        return 0;
    }
    out_xyz[0] = value.x;
    out_xyz[1] = value.y;
    out_xyz[2] = value.z;
    return 1;
}

int write_quat(Quat value, double* out_xyzw) {
    if (out_xyzw == nullptr) {
        return 0;
    }
    out_xyzw[0] = value.x;
    out_xyzw[1] = value.y;
    out_xyzw[2] = value.z;
    out_xyzw[3] = value.w;
    return 1;
}

std::string json_string_array(const std::vector<std::string>& values) {
    std::ostringstream out;
    out << '[';
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) {
            out << ',';
        }
        out << '"';
        for (const char ch : values[index]) {
            if (ch == '"' || ch == '\\') {
                out << '\\';
            }
            out << ch;
        }
        out << '"';
    }
    out << ']';
    return out.str();
}

} // namespace

extern "C" {

GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_candidate_names_json(
    const char* source_name
) {
    static thread_local std::string json;
    json = json_string_array(
        ghostrigger::animationretargeting::core::animation_retargeting::retargeter::candidate_names(
            source_name == nullptr ? "" : source_name
        )
    );
    return json.c_str();
}

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_sub3(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
) {
    if (a_xyz == nullptr || b_xyz == nullptr) {
        return 0;
    }
    return write_vec3(ghostrigger::animationretargeting::core::animation_retargeting::retargeter::sub3(read_vec3(a_xyz), read_vec3(b_xyz)), out_xyz);
}

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_add3(
    const double* a_xyz,
    const double* b_xyz,
    double scale,
    double* out_xyz
) {
    if (a_xyz == nullptr || b_xyz == nullptr) {
        return 0;
    }
    return write_vec3(ghostrigger::animationretargeting::core::animation_retargeting::retargeter::add3(read_vec3(a_xyz), read_vec3(b_xyz), scale), out_xyz);
}

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_mul3(
    const double* a_xyz,
    double scale,
    double* out_xyz
) {
    if (a_xyz == nullptr) {
        return 0;
    }
    return write_vec3(ghostrigger::animationretargeting::core::animation_retargeting::retargeter::mul3(read_vec3(a_xyz), scale), out_xyz);
}

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_normal_quat(
    const double* q_xyzw,
    double* out_xyzw
) {
    if (q_xyzw == nullptr) {
        return 0;
    }
    return write_quat(ghostrigger::animationretargeting::core::animation_retargeting::retargeter::normal_quat(read_quat(q_xyzw)), out_xyzw);
}

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_quat_conjugate(
    const double* q_xyzw,
    double* out_xyzw
) {
    if (q_xyzw == nullptr) {
        return 0;
    }
    return write_quat(ghostrigger::animationretargeting::core::animation_retargeting::retargeter::quat_conjugate(read_quat(q_xyzw)), out_xyzw);
}

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_quat_mul(
    const double* a_xyzw,
    const double* b_xyzw,
    double* out_xyzw
) {
    if (a_xyzw == nullptr || b_xyzw == nullptr) {
        return 0;
    }
    return write_quat(ghostrigger::animationretargeting::core::animation_retargeting::retargeter::quat_mul(read_quat(a_xyzw), read_quat(b_xyzw)), out_xyzw);
}

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_retarget_rotation(
    const double* src_pose_xyzw,
    const double* src_bind_xyzw,
    const double* dst_bind_xyzw,
    double* out_xyzw
) {
    if (src_pose_xyzw == nullptr || src_bind_xyzw == nullptr || dst_bind_xyzw == nullptr) {
        return 0;
    }
    return write_quat(
        ghostrigger::animationretargeting::core::animation_retargeting::retargeter::retarget_rotation(
            read_quat(src_pose_xyzw),
            read_quat(src_bind_xyzw),
            read_quat(dst_bind_xyzw)
        ),
        out_xyzw
    );
}

GHOSTRIGGER_ANIMATION_RETARGETING_API double gr_animation_retargeting_height_from_positions(
    const double* xyz_values,
    std::size_t point_count
) {
    return ghostrigger::animationretargeting::core::animation_retargeting::retargeter::height_from_positions(
        xyz_values,
        point_count
    );
}

}
