using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Data;
using Kotor.NET.Common.Geometry;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorGIT
{
    public class GITCompiler : IGFFDecompiler<GIT>
    {
        private GFF _gff;

        public GITCompiler(GFF gff)
        {
            _gff = gff;
        }

        public GIT Decompile()
        {
            var git = new GIT
            {
                UseTemplates = _gff.Root.GetUInt8("UseTemplates", 0),
                AreaProperties = new AreaProperties
                {
                    AmbientSndDay = _gff.Root.GetInt32("AreaProperties_AmbientSndDay", 0),
                    AmbientSndNight = _gff.Root.GetInt32("AreaProperties_AmbientSndNight", 0),
                    AmbientSndDayVol = _gff.Root.GetInt32("AreaProperties_AmbientSndDayVol", 0),
                    AmbientSndNitVol = _gff.Root.GetInt32("AreaProperties_AmbientSndNitVol", 0),
                    EnvAudio = _gff.Root.GetInt32("AreaProperties_EnvAudio", 0),
                    MusicBattle = _gff.Root.GetInt32("AreaProperties_MusicBattle", 0),
                    MusicDay = _gff.Root.GetInt32("AreaProperties_MusicDay", 0),
                    MusicNight = _gff.Root.GetInt32("AreaProperties_MusicNight", 0),
                    MusicDelay = _gff.Root.GetInt32("AreaProperties_MusicDelay", 0)
                },
                CameraList = _gff.Root.GetList("CameraList").Select(gffCamera => new CameraInfo
                {
                    CameraID = gffCamera.GetInt32("CameraID", 0),
                    Position = gffCamera.GetVector3("Position", new Vector3()),
                    Pitch = gffCamera.GetSingle("Pitch", 0),
                    MicRange = gffCamera.GetSingle("MicRange", 0),
                    Orientation = gffCamera.GetVector4("Orientation", new Vector4()),
                    Height = gffCamera.GetSingle("Height", 0),
                    FieldOfView = gffCamera.GetSingle("FieldOfView", 0)
                }).ToList(),
                CreatureList = _gff.Root.GetList("CreatureList").Select(gffCreature => new CreatureInfo
                {
                    XPosition = gffCreature.GetSingle("XPosition", 0),
                    YPosition = gffCreature.GetSingle("YPosition", 0),
                    ZPosition = gffCreature.GetSingle("ZPosition", 0),
                    XOrientation = gffCreature.GetSingle("XOrientation", 0),
                    YOrientation = gffCreature.GetSingle("YOrientation", 0),
                    TemplateResRef = gffCreature.GetResRef("TemplateResRef", new ResRef())
                }).ToList(),
                DoorList = _gff.Root.GetList("DoorList").Select(gffDoor => new DoorInfo
                {
                    TemplateResRef = gffDoor.GetResRef("TemplateResRef", ""),
                    Tag = gffDoor.GetString("Tag", ""),
                    LinkedToModule = gffDoor.GetResRef("LinkedToModule", new()),
                    LinkedTo = gffDoor.GetString("LinkedTo", ""),
                    LinkedToFlags = gffDoor.GetUInt8("LinkedToFlags", new()),
                    TransitionDestin = gffDoor.GetLocalizedString("TransitionDestin", new()),
                    X = gffDoor.GetSingle("X", 0),
                    Y = gffDoor.GetSingle("Y", 0),
                    Z = gffDoor.GetSingle("Z", 0),
                    Bearing = gffDoor.GetSingle("Bearing", 0),
                    UseTweakColor = gffDoor.GetUInt8("YOrientation", 0),
                    TweakColor = gffDoor.GetUInt32("TemplateResRef", new())
                }).ToList(),
                EncounterList = _gff.Root.GetList("EncounterList").Select(gffEncounter => new EncounterInfo
                {
                    TemplateResRef = gffEncounter.GetResRef("TemplateResRef", ""),
                    XPosition = gffEncounter.GetSingle("XPosition", 0),
                    YPosition = gffEncounter.GetSingle("YPosition", 0),
                    ZPosition = gffEncounter.GetSingle("ZPosition", 0),

                    Geometry = gffEncounter.GetList("Geometry", new())
                        .Select(geometryNode => new Vector3
                        {
                            X = geometryNode.GetSingle("X", 0),
                            Y = geometryNode.GetSingle("Y", 0),
                            Z = geometryNode.GetSingle("Z", 0),
                        }).ToList(),

                    SpawnPointList = gffEncounter.GetList("SpawnPointList", new())
                        .Select(spawnPointNode => new SpawnPoint
                        {
                            X = spawnPointNode.GetSingle("X", 0),
                            Y = spawnPointNode.GetSingle("Y", 0),
                            Z = spawnPointNode.GetSingle("Z", 0),
                            Orientation = spawnPointNode.GetSingle("Orientation", 0),
                        }).ToList(),
                }).ToList(),
                SoundList = _gff.Root.GetList("SoundList").Select(gffSound => new SoundInfo
                {
                    TemplateResRef = gffSound.GetResRef("TemplateResRef", ""),
                    GeneratedType = gffSound.GetUInt32("GeneratedType", 0),
                    XPosition = gffSound.GetSingle("XPosition", 0),
                    YPosition = gffSound.GetSingle("YPosition", 0),
                    ZPosition = gffSound.GetSingle("ZPosition", 0),
                }).ToList(),
                StoreList = _gff.Root.GetList("StoreList").Select(gffStore => new StoreInfo
                {
                    ResRef = gffStore.GetResRef("ResRef", ""),
                    XPosition = gffStore.GetSingle("XPosition", 0),
                    YPosition = gffStore.GetSingle("YPosition", 0),
                    ZPosition = gffStore.GetSingle("ZPosition", 0),
                    XOrientation = gffStore.GetSingle("XOrientation", 0),
                    YOrientation = gffStore.GetSingle("YOrientation", 0),
                }).ToList(),
                TriggerList = _gff.Root.GetList("TriggerList").Select(gffTrigger => new TriggerInfo
                {
                    TemplateResRef = gffTrigger.GetResRef("TemplateResRef", ""),
                    XPosition = gffTrigger.GetSingle("XPosition", 0),
                    YPosition = gffTrigger.GetSingle("YPosition", 0),
                    ZPosition = gffTrigger.GetSingle("ZPosition", 0),
                    XOrientation = gffTrigger.GetSingle("XOrientation", 0),
                    YOrientation = gffTrigger.GetSingle("YOrientation", 0),
                    ZOrientation = gffTrigger.GetSingle("ZOrientation", 0),
                    Tag = gffTrigger.GetString("Tag", ""),
                    TransitionDestin = gffTrigger.GetLocalizedString("TransitionDestin", new()),
                    LinkedToModule = gffTrigger.GetString("LinkedToModule", ""),
                    LinkedTo = gffTrigger.GetString("LinkedTo", ""),
                    LinkedToFlags = gffTrigger.GetUInt8("LinkedToFlags", 0),

                    Geometry = gffTrigger.GetList("Geometry", new())
                        .Select(geometryNode => new Vector3
                        {
                            X = geometryNode.GetSingle("PointX", 0),
                            Y = geometryNode.GetSingle("PointY", 0),
                            Z = geometryNode.GetSingle("PointZ", 0),
                        }).ToList(),
                }).ToList(),
                WaypointList = _gff.Root.GetList("WaypointList").Select(gffWaypoint => new WaypointInfo
                {
                    Appearance = gffWaypoint.GetUInt8("Appearance", 0),
                    LinkedTo = gffWaypoint.GetString("LinkedTo", ""),
                    TemplateResRef = gffWaypoint.GetResRef("TemplateResRef", ""),
                    LocalizedName = gffWaypoint.GetLocalizedString("LocalizedName", -1),
                    Description = gffWaypoint.GetLocalizedString("Description", -1),
                    HasMapNote = gffWaypoint.GetUInt8("HasMapNote", 0),
                    MapNote = gffWaypoint.GetLocalizedString("MapNote", -1),
                    MapNoteEnabled = gffWaypoint.GetUInt8("MapNoteEnabled", 0),
                    XPosition = gffWaypoint.GetSingle("XPosition", 0),
                    YPosition = gffWaypoint.GetSingle("YPosition", 0),
                    ZPosition = gffWaypoint.GetSingle("ZPosition", 0),
                    XOrientation = gffWaypoint.GetSingle("XOrientation", 0),
                    YOrientation = gffWaypoint.GetSingle("YOrientation", 0),
                }).ToList(),
                List = _gff.Root.GetList("List").Select(gffItem => new StructureInfo
                {
                    XPosition = gffItem.GetSingle("XPosition", 0),
                    YPosition = gffItem.GetSingle("YPosition", 0),
                    ZPosition = gffItem.GetSingle("ZPosition", 0),
                    XOrientation = gffItem.GetSingle("XOrientation", 0),
                    YOrientation = gffItem.GetSingle("YOrientation", 0),
                    TemplateResRef = gffItem.GetResRef("TemplateResRef", ""),
                }).ToList(),
            };

            return git;
        }
    }
}
