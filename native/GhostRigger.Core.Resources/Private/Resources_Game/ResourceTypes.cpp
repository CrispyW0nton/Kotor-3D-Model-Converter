#include "Resources_Game/ResourceTypes.h"

#include <cstdio>

namespace ghostrigger::core::game::core::game::resource_types {

const char* resource_type_name(int resource_type) noexcept {
    switch (resource_type) {
    case 0x0003:
        return "TGA Texture";
    case 0x0004:
        return "WAV Audio";
    case 0x07D0:
        return "Binary MDL";
    case 0x07D2:
        return "TPC Texture";
    case 0x07D9:
        return "Creature Template";
    case 0x07DA:
        return "Item Template";
    case 0x07DC:
        return "Sound Template";
    case 0x07DE:
        return "Door Template";
    case 0x07DF:
        return "Placeable Template";
    case 0x07E0:
        return "Dialog";
    case 0x07E1:
        return "2DA Table";
    case 0x07E4:
        return "Trigger";
    case 0x07E5:
        return "Merchant";
    case 0x07E6:
        return "Module Info";
    case 0x07E7:
        return "Area";
    case 0x07E9:
        return "Faction";
    case 0x07EB:
        return "Walkmesh";
    case 0x07ED:
        return "Talk Table";
    case 0x07EE:
        return "Journal";
    case 0x07F0:
        return "Random Encounter";
    case 0x07DD:
        return "Encounter";
    case 0x07DB:
        return "Waypoint";
    case 0x07F8:
        return "Compiled Script";
    case 0x07FF:
        return "Sound Set";
    case 0x0BC0:
        return "MDX Vertex Data";
    default:
        thread_local char buffer[16];
        std::snprintf(buffer, sizeof(buffer), "0x%04X", static_cast<unsigned int>(resource_type) & 0xFFFFu);
        return buffer;
    }
}

const char* resource_type_extension(int resource_type) noexcept {
    switch (resource_type) {
    case 0x0003:
        return ".tga";
    case 0x0004:
        return ".wav";
    case 0x0006:
        return ".plt";
    case 0x0007:
        return ".ini";
    case 0x000A:
        return ".txt";
    case 0x07D0:
        return ".mdl";
    case 0x07D2:
        return ".tpc";
    case 0x07D9:
        return ".utc";
    case 0x07DA:
        return ".uti";
    case 0x07DB:
        return ".utw";
    case 0x07DC:
        return ".uts";
    case 0x07DD:
        return ".ute";
    case 0x07DE:
        return ".utd";
    case 0x07DF:
        return ".utp";
    case 0x07E0:
        return ".dlg";
    case 0x07E1:
        return ".2da";
    case 0x07E4:
        return ".utt";
    case 0x07E5:
        return ".utm";
    case 0x07E6:
        return ".ifo";
    case 0x07E7:
        return ".are";
    case 0x07E9:
        return ".fac";
    case 0x07EB:
        return ".wok";
    case 0x07EC:
        return ".2da";
    case 0x07ED:
        return ".tlk";
    case 0x07EE:
        return ".jrl";
    case 0x07F0:
        return ".utr";
    case 0x07F8:
        return ".ncs";
    case 0x07FA:
        return ".ndb";
    case 0x07FB:
        return ".ptm";
    case 0x07FC:
        return ".ptt";
    case 0x07FF:
        return ".ssf";
    case 0x0BB8:
        return ".erf";
    case 0x0BB9:
        return ".are";
    case 0x0BC0:
        return ".mdx";
    default:
        thread_local char buffer[8];
        std::snprintf(buffer, sizeof(buffer), ".%04x", static_cast<unsigned int>(resource_type) & 0xFFFFu);
        return buffer;
    }
}

const char* resource_type_contracts_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"game_resource_types_native.v1",)"
        R"("source":"src/core/game/game_library_ext.py",)"
        R"("native_scope":["resource type id to extension lookup","resource type id to display name lookup","unknown type fallback formatting"],)"
        R"("python_fallback":["TLKReader binary parsing","GFFReader binary parsing","2DA library reads","KEY/BIF/ERF resource access","PyKotor loader bridge","stock model import normalisation"],)"
        R"("reason_python_fallback":"binary game-file parsing, archive access, PyKotor integration, and model import mutation need ground-truth validation before semantic native ports"})";
    return kJson;
}

} // namespace ghostrigger::core::game::core::game::resource_types
