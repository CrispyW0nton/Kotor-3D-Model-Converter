using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Resources.KotorARE
{
    public class ARE
    {
        public Single AlphaTest { get; set; }
        public Int32 CameraStyle { get; set; }
        public Int32 ChanceLightning { get; set; }
        public Int32 ChanceRain { get; set; }
        public Int32 ChanceSnow { get; set; }
        public String Comments { get; set; } = "";
        public Int32 Creator_ID { get; set; }
        public Byte DayNightCycle { get; set; }
        public ResRef DefaultEnvMap { get; set; } = "";
        public Int32 DirtyARGBOne { get; set; }
        public Int32 DirtyARGBThree { get; set; }
        public Int32 DirtyARGBTwo { get; set; }
        public Int32 DirtyFormulaOne { get; set; }
        public Int32 DirtyFormulaThre { get; set; }
        public Int32 DirtyFormulaTwo { get; set; }
        public Int32 DirtyFuncOne { get; set; }
        public Int32 DirtyFuncThree { get; set; }
        public Int32 DirtyFuncTwo { get; set; }
        public Int32 DirtySizeOne { get; set; }
        public Int32 DirtySizeThree { get; set; }
        public Int32 DirtySizeTwo { get; set; }
        public Byte DisableTransit { get; set; }
        public UInt32 DynAmbientColor { get; set; }
        public UInt32 Flags { get; set; }
        public UInt32 Grass_Ambient { get; set; }
        public Single Grass_Density { get; set; }
        public UInt32 Grass_Diffuse { get; set; }
        public UInt32 Grass_Emissive { get; set; }
        public Single Grass_Prob_LL { get; set; }
        public Single Grass_Prob_LR { get; set; }
        public Single Grass_Prob_UL { get; set; }
        public Single Grass_Prob_UR { get; set; }
        public Single Grass_QuadSize { get; set; }
        public ResRef Grass_TexName { get; set; } = "";
        public Int32 ID { get; set; }
        public Byte IsNight { get; set; }
        public Byte LightingScheme { get; set; }
        public UInt16 LoadScreenID { get; set; }
        public Int32 ModListenCheck { get; set; }
        public Int32 ModSpotCheck { get; set; }
        public UInt32 MoonAmbientColor { get; set; }
        public UInt32 MoonDiffuseColor { get; set; }
        public UInt32 MoonFogColor { get; set; }
        public Single MoonFogFar { get; set; }
        public Single MoonFogNear { get; set; }
        public Byte MoonFogOn { get; set; }
        public Byte MoonShadows { get; set; }
        public LocalizedString Name { get; set; } = -1;
        public Byte NoHangBack { get; set; }
        public Byte NoRest { get; set; }
        public ResRef OnEnter { get; set; } = "";
        public ResRef OnExit { get; set; } = "";
        public ResRef OnHeartbeat { get; set; } = "";
        public ResRef OnUserDefined { get; set; } = "";
        public Byte PlayerOnly { get; set; }
        public Byte PlayerVsPlayer { get; set; }
        public Byte ShadowOpacity { get; set; }
        public Byte StealthXPEnabled { get; set; }
        public UInt32 StealthXPLoss { get; set; }
        public UInt32 StealthXPMax { get; set; }
        public UInt32 SunAmbientColor { get; set; }
        public UInt32 SunDiffuseColor { get; set; }
        public UInt32 SunFogColor { get; set; }
        public Single SunFogFar { get; set; }
        public Single SunFogNear { get; set; }
        public Byte SunFogOn { get; set; }
        public Byte SunShadows { get; set; }
        public String Tag { get; set; }
        public Byte Unescapable { get; set; }
        public UInt32 Version { get; set; }
        public Int32 WindPower { get; set; }
        public Single MapPt1X { get; set; }
        public Single MapPt1Y { get; set; }
        public Single MapPt2X { get; set; }
        public Single MapPt2Y { get; set; }
        public Int32 MapResX { get; set; }
        public Int32 MapZoom { get; set; }
        public Int32 NorthAxis { get; set; }
        public Single WorldPt1X { get; set; }
        public Single WorldPt1Y { get; set; }
        public Single WorldPt2X { get; set; }
        public Single WorldPt2Y { get; set; }

        public List<ARERoom> Rooms { get; set; } = new();
    }

    public class ARERoom
    {
        public Single AmbientScale { get; set; }
        public Byte DisableWeather { get; set; }
        public Int32 EnvAudio { get; set; }
        public Int32 ForceRating { get; set; }
        public String RoomName { get; set; } = "";
    }
}
