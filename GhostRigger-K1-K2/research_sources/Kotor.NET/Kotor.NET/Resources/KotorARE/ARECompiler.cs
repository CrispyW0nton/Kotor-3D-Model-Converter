using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorARE
{
    public class ARECompiler : IGFFDecompiler<ARE>
    {
        private GFF _gff;

        public ARECompiler(GFF gff)
        {
            _gff = gff;
        }

        public ARE Decompile()
        {
            var are = new ARE
            {
                AlphaTest = _gff.Root.GetSingle("AlphaTest", 0),
                CameraStyle = _gff.Root.GetInt32("CameraStyle", 0),
                ChanceLightning = _gff.Root.GetInt32("ChanceLightning", 0),
                ChanceRain = _gff.Root.GetInt32("ChanceRain", 0),
                ChanceSnow = _gff.Root.GetInt32("ChanceSnow", 0),
                Comments = _gff.Root.GetString("Comments", ""),
                Creator_ID = _gff.Root.GetInt32("Creator_ID", 0),
                DayNightCycle = _gff.Root.GetUInt8("DayNightCycle", 0),
                DefaultEnvMap = _gff.Root.GetResRef("DefaultEnvMap", new ResRef()),
                DirtyARGBOne = _gff.Root.GetInt32("DirtyARGBOne", 0),
                DirtyARGBThree = _gff.Root.GetInt32("DirtyARGBThree", 0),
                DirtyARGBTwo = _gff.Root.GetInt32("DirtyARGBTwo", 0),
                DirtyFormulaOne = _gff.Root.GetInt32("DirtyFormulaOne", 0),
                DirtyFormulaThre = _gff.Root.GetInt32("DirtyFormulaThre", 0),
                DirtyFormulaTwo = _gff.Root.GetInt32("DirtyFormulaTwo", 0),
                DirtyFuncOne = _gff.Root.GetInt32("DirtyFuncOne", 0),
                DirtyFuncThree = _gff.Root.GetInt32("DirtyFuncThree", 0),
                DirtyFuncTwo = _gff.Root.GetInt32("DirtyFuncTwo", 0),
                DirtySizeOne = _gff.Root.GetInt32("DirtySizeOne", 0),
                DirtySizeThree = _gff.Root.GetInt32("DirtySizeThree", 0),
                DirtySizeTwo = _gff.Root.GetInt32("DirtySizeTwo", 0),
                DisableTransit = _gff.Root.GetUInt8("DisableTransit", 0),
                DynAmbientColor = _gff.Root.GetUInt32("DynAmbientColor", 0),
                Flags = _gff.Root.GetUInt32("Flags", 0),
                Grass_Ambient = _gff.Root.GetUInt32("Grass_Ambient", 0),
                Grass_Density = _gff.Root.GetSingle("Grass_Density", 0),
                Grass_Diffuse = _gff.Root.GetUInt32("Grass_Diffuse", 0),
                Grass_Emissive = _gff.Root.GetUInt32("Grass_Emissive", 0),
                Grass_Prob_LL = _gff.Root.GetSingle("Grass_Prob_LL", 0),
                Grass_Prob_LR = _gff.Root.GetSingle("Grass_Prob_LR", 0),
                Grass_Prob_UL = _gff.Root.GetSingle("Grass_Prob_UL", 0),
                Grass_Prob_UR = _gff.Root.GetSingle("Grass_Prob_UR", 0),
                Grass_QuadSize = _gff.Root.GetSingle("Grass_QuadSize", 0),
                Grass_TexName = _gff.Root.GetResRef("Grass_TexName", new ResRef()),
                ID = _gff.Root.GetInt32("ID", 0),
                IsNight = _gff.Root.GetUInt8("IsNight", 0),
                LightingScheme = _gff.Root.GetUInt8("LightingScheme", 0),
                LoadScreenID = _gff.Root.GetUInt16("LoadScreenID", 0),
                ModListenCheck = _gff.Root.GetInt32("ModListenCheck", 0),
                ModSpotCheck = _gff.Root.GetInt32("ModSpotCheck", 0),
                MoonAmbientColor = _gff.Root.GetUInt32("MoonAmbientColor", 0),
                MoonDiffuseColor = _gff.Root.GetUInt32("MoonDiffuseColor", 0),
                MoonFogColor = _gff.Root.GetUInt32("MoonFogColor", 0),
                MoonFogFar = _gff.Root.GetSingle("MoonFogFar", 0),
                MoonFogNear = _gff.Root.GetSingle("MoonFogNear", 0),
                MoonFogOn = _gff.Root.GetUInt8("MoonFogOn", 0),
                MoonShadows = _gff.Root.GetUInt8("MoonShadows", 0),
                Name = _gff.Root.GetLocalizedString("Name", new LocalizedString()),
                NoHangBack = _gff.Root.GetUInt8("NoHangBack", 0),
                NoRest = _gff.Root.GetUInt8("NoRest", 0),
                OnEnter = _gff.Root.GetResRef("OnEnter", new ResRef()),
                OnExit = _gff.Root.GetResRef("OnExit", new ResRef()),
                OnHeartbeat = _gff.Root.GetResRef("OnHeartbeat", new ResRef()),
                OnUserDefined = _gff.Root.GetResRef("OnUserDefined", new ResRef()),
                PlayerOnly = _gff.Root.GetUInt8("PlayerOnly", 0),
                PlayerVsPlayer = _gff.Root.GetUInt8("PlayerVsPlayer", 0),
                ShadowOpacity = _gff.Root.GetUInt8("ShadowOpacity", 0),
                StealthXPEnabled = _gff.Root.GetUInt8("StealthXPEnabled", 0),
                StealthXPLoss = _gff.Root.GetUInt32("StealthXPLoss", 0),
                StealthXPMax = _gff.Root.GetUInt32("StealthXPMax", 0),
                SunAmbientColor = _gff.Root.GetUInt32("SunAmbientColor", 0),
                SunDiffuseColor = _gff.Root.GetUInt32("SunDiffuseColor", 0),
                SunFogColor = _gff.Root.GetUInt32("SunFogColor", 0),
                SunFogFar = _gff.Root.GetSingle("SunFogFar", 0),
                SunFogNear = _gff.Root.GetSingle("SunFogNear", 0),
                SunFogOn = _gff.Root.GetUInt8("SunFogOn", 0),
                SunShadows = _gff.Root.GetUInt8("SunShadows", 0),
                Tag = _gff.Root.GetString("Tag", ""),
                Unescapable = _gff.Root.GetUInt8("Unescapable", 0),
                Version = _gff.Root.GetUInt32("Version", 0),
                WindPower = _gff.Root.GetInt32("WindPower", 0),
                MapPt1X = _gff.Root.GetStruct("Map").GetSingle("MapPt1X", 0),
                MapPt1Y = _gff.Root.GetStruct("Map").GetSingle("MapPt1Y", 0),
                MapPt2X = _gff.Root.GetStruct("Map").GetSingle("MapPt2X", 0),
                MapPt2Y = _gff.Root.GetSingle("MapPt2Y", 0),
                MapResX = _gff.Root.GetStruct("Map").GetInt32("MapResX", 0),
                MapZoom = _gff.Root.GetStruct("Map").GetInt32("MapZoom", 0),
                NorthAxis = _gff.Root.GetStruct("Map").GetInt32("NorthAxis", 0),
                WorldPt1X = _gff.Root.GetStruct("Map").GetSingle("WorldPt1X", 0),
                WorldPt1Y = _gff.Root.GetStruct("Map").GetSingle("WorldPt1Y", 0),
                WorldPt2X = _gff.Root.GetStruct("Map").GetSingle("WorldPt2X", 0),
                WorldPt2Y = _gff.Root.GetStruct("Map").GetSingle("WorldPt2Y", 0),

                Rooms = _gff.Root.GetList("Rooms", new()).Select(gffRoom => new ARERoom
                {
                    AmbientScale = _gff.Root.GetSingle("AmbientScale", 0),
                    DisableWeather = _gff.Root.GetUInt8("DisableWeather", 0),
                    EnvAudio = _gff.Root.GetInt32("EnvAudio", 0),
                    ForceRating = _gff.Root.GetInt32("ForceRating", 0),
                    RoomName = _gff.Root.GetString("RoomName", "")
                }).ToList(),
            };
            
            return are;
        }
    }
}
