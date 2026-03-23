using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Common.Geometry;

namespace Kotor.NET.Resources.KotorGIT
{
    public class GIT
    {
        public byte UseTemplates { get; set; }
        public AreaProperties AreaProperties { get; set; } = new();
        public List<CameraInfo> CameraList { get; set; } = new();
        public List<CreatureInfo> CreatureList { get; set; } = new();
        public List<DoorInfo> DoorList { get; set; } = new();
        public List<EncounterInfo> EncounterList { get; set; } = new();
        public List<StructureInfo> List { get; set; } = new();
        public List<SoundInfo> SoundList { get; set; } = new();
        public List<StoreInfo> StoreList { get; set; } = new();
        public List<TriggerInfo> TriggerList { get; set; } = new();
        public List<WaypointInfo> WaypointList { get; set; } = new();
    }

    public class AreaProperties
    {
        public int AmbientSndDay { get; set; }
        public int AmbientSndNight { get; set; }
        public int AmbientSndDayVol { get; set; }
        public int AmbientSndNitVol { get; set; }
        public int EnvAudio { get; set; }
        public int MusicBattle { get; set; }
        public int MusicDay { get; set; }
        public int MusicNight { get; set; }
        public int MusicDelay { get; set; }
    }

    public class CameraInfo
    {
        public int CameraID { get; set; }
        public Vector3 Position { get; set; } = new();
        public float Pitch { get; set; }
        public float MicRange { get; set; }
        public Vector4 Orientation { get; set; } = new();
        public float Height { get; set; }
        public float FieldOfView { get; set; }
    }

    public class CreatureInfo
    {
        public float XPosition { get; set; }
        public float YPosition { get; set; }
        public float ZPosition { get; set; }
        public float XOrientation { get; set; }
        public float YOrientation { get; set; }
        public ResRef TemplateResRef { get; set; } = "";
    }

    public class DoorInfo
    {
        public ResRef TemplateResRef { get; set; } = "";
        public string Tag { get; set; } = "";
        public ResRef LinkedToModule { get; set; } = "";
        public string LinkedTo { get; set; } = "";
        public byte LinkedToFlags { get; set; }
        public LocalizedString TransitionDestin { get; set; } = new();
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }
        public float Bearing { get; set; }
        public byte UseTweakColor { get; set; }
        public uint TweakColor { get; set; }
    }

    public class EncounterInfo
    {
        public ResRef TemplateResRef { get; set; } = "";
        public float XPosition { get; set; }
        public float YPosition { get; set; }
        public float ZPosition { get; set; }
        public List<Vector3> Geometry { get; set; } = new();
        public List<SpawnPoint> SpawnPointList { get; set; } = new();
    }

    public class SpawnPoint
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }
        public float Orientation { get; set; }
    }

    public class StructureInfo
    {
        public float XPosition { get; set; }
        public float YPosition { get; set; }
        public float ZPosition { get; set; }
        public float XOrientation { get; set; }
        public float YOrientation { get; set; }
        public ResRef TemplateResRef { get; set; } = "";
    }

    public class SoundInfo
    {
        public ResRef TemplateResRef { get; set; } = "";
        public uint GeneratedType { get; set; }
        public float XPosition { get; set; }
        public float YPosition { get; set; }
        public float ZPosition { get; set; }
    }

    public class StoreInfo
    {
        public float XPosition { get; set; }
        public float YPosition { get; set; }
        public float ZPosition { get; set; }
        public float XOrientation { get; set; }
        public float YOrientation { get; set; }
        public ResRef ResRef { get; set; } = "";
    }

    public class TriggerInfo
    {
        public ResRef TemplateResRef { get; set; } = "";
        public float XPosition { get; set; }
        public float YPosition { get; set; }
        public float ZPosition { get; set; }
        public float XOrientation { get; set; }
        public float YOrientation { get; set; }
        public float ZOrientation { get; set; }
        public List<Vector3> Geometry { get; set; } = new();
        public string Tag { get; set; } = "";
        public LocalizedString TransitionDestin { get; set; } = -1;
        public ResRef LinkedToModule { get; set; } = "";
        public string LinkedTo { get; set; } = "";
        public byte LinkedToFlags { get; set; }
    }

    public class WaypointInfo
    {
        public byte Appearance { get; set; }
        public string LinkedTo { get; set; } = "";
        public ResRef TemplateResRef { get; set; } = "";
        public string Tag { get; set; } = "";
        public LocalizedString LocalizedName { get; set; } = -1;
        public LocalizedString Description { get; set; } = -1;
        public byte HasMapNote { get; set; }
        public LocalizedString MapNote { get; set; } = -1;
        public byte MapNoteEnabled { get; set; }
        public float XPosition { get; set; }
        public float YPosition { get; set; }
        public float ZPosition { get; set; }
        public float XOrientation { get; set; }
        public float YOrientation { get; set; }
    }
}
