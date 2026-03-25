using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Resources.KotorUTP;
using static Kotor.NET.Formats.KotorNCS.NCSInstruction;

namespace Kotor.NET.Resources.KotorARE
{
    public class AREDecompiler : IGFFCompiler
    {
        public ARE _are;

        public AREDecompiler(ARE are)
        {
            _are = are;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetSingle("AlphaTest", _are.AlphaTest);
            gff.Root.SetInt32("CameraStyle", _are.CameraStyle);
            gff.Root.SetInt32("ChanceLightning", _are.ChanceLightning);
            gff.Root.SetInt32("ChanceRain", _are.ChanceRain);
            gff.Root.SetInt32("ChanceSnow", _are.ChanceSnow);
            gff.Root.SetString("Comments", _are.Comments);
            gff.Root.SetInt32("Creator_ID", _are.Creator_ID);
            gff.Root.SetUInt8("DayNightCycle", _are.DayNightCycle);
            gff.Root.SetResRef("DefaultEnvMap", _are.DefaultEnvMap);
            gff.Root.SetInt32("DirtyARGBOne", _are.DirtyARGBOne);
            gff.Root.SetInt32("DirtyARGBThree", _are.DirtyARGBThree);
            gff.Root.SetInt32("DirtyARGBTwo", _are.DirtyARGBTwo);
            gff.Root.SetInt32("DirtyFormulaOne", _are.DirtyFormulaOne);
            gff.Root.SetInt32("DirtyFormulaThre", _are.DirtyFormulaThre);
            gff.Root.SetInt32("DirtyFormulaTwo", _are.DirtyFormulaTwo);
            gff.Root.SetInt32("DirtyFuncOne", _are.DirtyFuncOne);
            gff.Root.SetInt32("DirtyFuncThree", _are.DirtyFuncThree);
            gff.Root.SetInt32("DirtyFuncTwo", _are.DirtyFuncTwo);
            gff.Root.SetInt32("DirtySizeOne", _are.DirtySizeOne);
            gff.Root.SetInt32("DirtySizeThree", _are.DirtySizeThree);
            gff.Root.SetInt32("DirtySizeTwo", _are.DirtySizeTwo);
            gff.Root.SetUInt8("DisableTransit", _are.DisableTransit);
            gff.Root.SetUInt32("DynAmbientColor", _are.DynAmbientColor);
            gff.Root.SetUInt32("Flags", _are.Flags);
            gff.Root.SetUInt32("Grass_Ambient", _are.Grass_Ambient);
            gff.Root.SetSingle("Grass_Density", _are.Grass_Density);
            gff.Root.SetUInt32("Grass_Diffuse", _are.Grass_Diffuse);
            gff.Root.SetUInt32("Grass_Emissive", _are.Grass_Emissive);
            gff.Root.SetSingle("Grass_Prob_LL", _are.Grass_Prob_LL);
            gff.Root.SetSingle("Grass_Prob_LR", _are.Grass_Prob_LR);
            gff.Root.SetSingle("Grass_Prob_UL", _are.Grass_Prob_UL);
            gff.Root.SetSingle("Grass_Prob_UR", _are.Grass_Prob_UR);
            gff.Root.SetSingle("Grass_QuadSize", _are.Grass_QuadSize);
            gff.Root.SetResRef("Grass_TexName", _are.Grass_TexName);
            gff.Root.SetInt32("ID", _are.ID);
            gff.Root.SetUInt8("IsNight", _are.IsNight);
            gff.Root.SetUInt8("LightingScheme", _are.LightingScheme);
            gff.Root.SetUInt16("LoadScreenID", _are.LoadScreenID);
            gff.Root.SetInt32("ModListenCheck", _are.ModListenCheck);
            gff.Root.SetInt32("ModSpotCheck", _are.ModSpotCheck);
            gff.Root.SetUInt32("MoonAmbientColor", _are.MoonAmbientColor);
            gff.Root.SetUInt32("MoonDiffuseColor", _are.MoonDiffuseColor);
            gff.Root.SetUInt32("MoonFogColor", _are.MoonFogColor);
            gff.Root.SetSingle("MoonFogFar", _are.MoonFogFar);
            gff.Root.SetSingle("MoonFogNear", _are.MoonFogNear);
            gff.Root.SetUInt8("MoonFogOn", _are.MoonFogOn);
            gff.Root.SetUInt8("MoonShadows", _are.MoonShadows);
            gff.Root.SetLocalizedString("Name", _are.Name);
            gff.Root.SetUInt8("NoHangBack", _are.NoHangBack);
            gff.Root.SetUInt8("NoRest", _are.NoRest);
            gff.Root.SetResRef("OnEnter", _are.OnEnter);
            gff.Root.SetResRef("OnExit", _are.OnExit);
            gff.Root.SetResRef("OnHeartbeat", _are.OnHeartbeat);
            gff.Root.SetResRef("OnUserDefined", _are.OnUserDefined);
            gff.Root.SetUInt8("PlayerOnly", _are.PlayerOnly);
            gff.Root.SetUInt8("PlayerVsPlayer", _are.PlayerVsPlayer);
            gff.Root.SetUInt8("ShadowOpacity", _are.ShadowOpacity);
            gff.Root.SetUInt8("StealthXPEnabled", _are.StealthXPEnabled);
            gff.Root.SetUInt32("StealthXPLoss", _are.StealthXPLoss);
            gff.Root.SetUInt32("StealthXPMax", _are.StealthXPMax);
            gff.Root.SetUInt32("SunAmbientColor", _are.SunAmbientColor);
            gff.Root.SetUInt32("SunDiffuseColor", _are.SunDiffuseColor);
            gff.Root.SetUInt32("SunFogColor", _are.SunFogColor);
            gff.Root.SetSingle("SunFogFar", _are.SunFogFar);
            gff.Root.SetSingle("SunFogNear", _are.SunFogNear);
            gff.Root.SetUInt8("SunFogOn", _are.SunFogOn);
            gff.Root.SetUInt8("SunShadows", _are.SunShadows);
            gff.Root.SetString("Tag", _are.Tag);
            gff.Root.SetUInt8("Unescapable", _are.Unescapable);
            gff.Root.SetUInt32("Version", _are.Version);
            gff.Root.SetInt32("WindPower", _are.WindPower);

            var mapStruct = gff.Root.SetStruct("Map", new());
            mapStruct.SetSingle("MapPt1X", _are.MapPt1X);
            mapStruct.SetSingle("MapPt1Y", _are.MapPt1Y);
            mapStruct.SetSingle("MapPt2X", _are.MapPt2X);
            mapStruct.SetSingle("MapPt2Y", _are.MapPt2Y);
            mapStruct.SetInt32("MapResX", _are.MapResX);
            mapStruct.SetInt32("MapZoom", _are.MapZoom);
            mapStruct.SetInt32("NorthAxis", _are.NorthAxis);
            mapStruct.SetSingle("WorldPt1X", _are.WorldPt1X);
            mapStruct.SetSingle("WorldPt1Y", _are.WorldPt1Y);
            mapStruct.SetSingle("WorldPt2X", _are.WorldPt2X);
            mapStruct.SetSingle("WorldPt2Y", _are.WorldPt2Y);

            var roomsList = gff.Root.SetList("Rooms", new());
            foreach (var room in _are.Rooms)
            {
                var roomStruct = roomsList.Add();
                roomStruct.SetSingle("AmbientScale", room.AmbientScale);
                roomStruct.SetUInt8("DisableWeather", room.DisableWeather);
                roomStruct.SetInt32("EnvAudio", room.EnvAudio);
                roomStruct.SetInt32("ForceRating", room.ForceRating);
                roomStruct.SetString("RoomName", room.RoomName);
            }

            return gff;
        }
    }
}
