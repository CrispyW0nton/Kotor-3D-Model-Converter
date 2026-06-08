#include "WalkmeshSurface.h"

#include <cstdio>

namespace ghostrigger::walkmesh::core::walkmesh::surface {
namespace {

struct SurfaceRow {
    int id;
    const char* name;
    Rgba color;
    const char* fbx_name;
    Rgb diffuse;
    bool walkable;
    bool non_walkable;
};

constexpr SurfaceRow kRows[] = {
    {0, "INVALID", {0.5, 0.5, 0.5, 0.30}, "WOK_Invalid", {0.5, 0.5, 0.5}, false, false},
    {1, "DIRT", {0.60, 0.40, 0.20, 0.55}, "WOK_Dirt", {0.60, 0.40, 0.20}, true, false},
    {2, "OBSCURING", {0.30, 0.30, 0.30, 0.55}, "WOK_Obscuring", {0.30, 0.30, 0.30}, false, false},
    {3, "GRASS", {0.20, 0.70, 0.20, 0.55}, "WOK_Grass", {0.20, 0.70, 0.20}, true, false},
    {4, "STONE", {0.50, 0.50, 0.50, 0.55}, "WOK_Stone", {0.50, 0.50, 0.50}, true, false},
    {5, "WOOD", {0.50, 0.30, 0.10, 0.55}, "WOK_Wood", {0.50, 0.30, 0.10}, true, false},
    {6, "WATER", {0.20, 0.45, 0.80, 0.55}, "WOK_Water", {0.20, 0.45, 0.80}, false, false},
    {7, "NON_WALK", {0.80, 0.10, 0.10, 0.75}, "WOK_NonWalk", {0.80, 0.10, 0.10}, false, true},
    {8, "TRANSPARENT", {0.90, 0.90, 0.90, 0.15}, "WOK_Transparent", {0.90, 0.90, 0.90}, false, false},
    {9, "CARPET", {0.70, 0.30, 0.70, 0.55}, "WOK_Carpet", {0.70, 0.30, 0.70}, true, false},
    {10, "METAL", {0.65, 0.65, 0.75, 0.55}, "WOK_Metal", {0.65, 0.65, 0.75}, true, false},
    {11, "PUDDLES", {0.30, 0.50, 0.70, 0.55}, "WOK_Puddles", {0.30, 0.50, 0.70}, true, false},
    {12, "SWAMP", {0.30, 0.50, 0.10, 0.55}, "WOK_Swamp", {0.30, 0.50, 0.10}, true, false},
    {13, "MUD", {0.45, 0.30, 0.10, 0.55}, "WOK_Mud", {0.45, 0.30, 0.10}, true, false},
    {14, "LEAVES", {0.20, 0.60, 0.20, 0.55}, "WOK_Leaves", {0.20, 0.60, 0.20}, true, false},
    {15, "LAVA", {0.90, 0.30, 0.05, 0.80}, "WOK_Lava", {0.90, 0.30, 0.05}, false, false},
    {16, "BOTTOMLESS", {0.00, 0.00, 0.00, 0.85}, "WOK_Bottomless", {0.00, 0.00, 0.00}, false, true},
    {17, "DEEP_WATER", {0.10, 0.20, 0.60, 0.80}, "WOK_DeepWater", {0.10, 0.20, 0.60}, false, false},
    {18, "DOOR", {0.80, 0.80, 0.20, 0.55}, "WOK_Door", {0.80, 0.80, 0.20}, true, false},
    {19, "NON_WALK_GRASS", {0.60, 0.20, 0.20, 0.75}, "WOK_NonWalkGrass", {0.60, 0.20, 0.20}, false, true},
    {20, "SNOW", {0.85, 0.90, 0.95, 0.55}, "WOK_Snow", {0.85, 0.90, 0.95}, true, false},
    {21, "SAND", {0.85, 0.75, 0.45, 0.55}, "WOK_Sand", {0.85, 0.75, 0.45}, true, false},
    {22, "BAREBONES", {0.55, 0.45, 0.35, 0.55}, "WOK_Barebones", {0.55, 0.45, 0.35}, true, false},
};

constexpr Rgba kDefaultColor = {0.60, 0.60, 0.60, 0.45};
constexpr Rgb kDefaultDiffuse = {0.60, 0.60, 0.60};

const SurfaceRow* find_row(int surface_id) noexcept {
    for (const auto& row : kRows) {
        if (row.id == surface_id) {
            return &row;
        }
    }
    return nullptr;
}

} // namespace

const char* surface_name(int surface_id) noexcept {
    if (const auto* row = find_row(surface_id)) {
        return row->name;
    }
    thread_local char buffer[32];
    std::snprintf(buffer, sizeof(buffer), "SURFACE_%d", surface_id);
    return buffer;
}

Rgba surface_color(int surface_id) noexcept {
    if (const auto* row = find_row(surface_id)) {
        return row->color;
    }
    return kDefaultColor;
}

bool is_walkable(int surface_id) noexcept {
    if (const auto* row = find_row(surface_id)) {
        return row->walkable;
    }
    return false;
}

bool is_non_walkable(int surface_id) noexcept {
    if (const auto* row = find_row(surface_id)) {
        return row->non_walkable;
    }
    return false;
}

const char* fbx_material_name(int surface_id) noexcept {
    if (const auto* row = find_row(surface_id)) {
        return row->fbx_name;
    }
    thread_local char buffer[32];
    std::snprintf(buffer, sizeof(buffer), "WOK_Surface%d", surface_id);
    return buffer;
}

Rgb fbx_material_diffuse(int surface_id) noexcept {
    if (const auto* row = find_row(surface_id)) {
        return row->diffuse;
    }
    return kDefaultDiffuse;
}

const char* walkmesh_surface_contracts_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"walkmesh_surface_native.v1",)"
        R"("source":["src/core/walkmesh/walkmesh_renderer.py","src/core/walkmesh/walkmesh_editor.py"],)"
        R"("native_scope":["surface material names","surface overlay colors","walkable classification","non-walkable classification","FBX material names and diffuse colors"],)"
        R"("python_fallback":["WOK object traversal","walkmesh face mutation","walkmesh validation","walkmesh roundtrip serialization","overlay draw-list generation","FBX face grouping"],)"
        R"("reason_python_fallback":"WOK parsing, mutation, validation, serialization, draw-list construction, and export grouping remain Python-owned until validated with game-file walkmesh fixtures"})";
    return kJson;
}

} // namespace ghostrigger::walkmesh::core::walkmesh::surface

extern "C" {

__declspec(dllexport) const char* gr_walkmesh_surface_name(int surface_id) {
    return ghostrigger::walkmesh::core::walkmesh::surface::surface_name(surface_id);
}

__declspec(dllexport) void gr_walkmesh_surface_color(
    int surface_id,
    double* r,
    double* g,
    double* b,
    double* a
) {
    const auto color = ghostrigger::walkmesh::core::walkmesh::surface::surface_color(surface_id);
    if (r != nullptr) {
        *r = color.r;
    }
    if (g != nullptr) {
        *g = color.g;
    }
    if (b != nullptr) {
        *b = color.b;
    }
    if (a != nullptr) {
        *a = color.a;
    }
}

__declspec(dllexport) int gr_walkmesh_surface_is_walkable(int surface_id) {
    return ghostrigger::walkmesh::core::walkmesh::surface::is_walkable(surface_id) ? 1 : 0;
}

__declspec(dllexport) int gr_walkmesh_surface_is_non_walkable(int surface_id) {
    return ghostrigger::walkmesh::core::walkmesh::surface::is_non_walkable(surface_id) ? 1 : 0;
}

__declspec(dllexport) const char* gr_walkmesh_fbx_material_name(int surface_id) {
    return ghostrigger::walkmesh::core::walkmesh::surface::fbx_material_name(surface_id);
}

__declspec(dllexport) void gr_walkmesh_fbx_material_diffuse(
    int surface_id,
    double* r,
    double* g,
    double* b
) {
    const auto color = ghostrigger::walkmesh::core::walkmesh::surface::fbx_material_diffuse(surface_id);
    if (r != nullptr) {
        *r = color.r;
    }
    if (g != nullptr) {
        *g = color.g;
    }
    if (b != nullptr) {
        *b = color.b;
    }
}

__declspec(dllexport) const char* gr_walkmesh_surface_contracts_schema_json() {
    return ghostrigger::walkmesh::core::walkmesh::surface::walkmesh_surface_contracts_schema_json();
}

}
