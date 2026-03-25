using System;
using System.Collections.Generic;
using System.Diagnostics.Metrics;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorGIT
{
    public class GITDecompiler : IGFFCompiler
    {
        private GIT _git;

        public GITDecompiler(GIT git)
        {
            _git = git;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetUInt8("UseTemplates", _git.UseTemplates);

            var areaPropertiesNode = gff.Root.SetStruct("AreaProperties", new());
            areaPropertiesNode.SetInt32("AmbientSndDay", _git.AreaProperties.AmbientSndDay);
            areaPropertiesNode.SetInt32("AmbientSndNight", _git.AreaProperties.AmbientSndNight);
            areaPropertiesNode.SetInt32("AmbientSndDayVol", _git.AreaProperties.AmbientSndDayVol);
            areaPropertiesNode.SetInt32("AmbientSndNitVol", _git.AreaProperties.AmbientSndNitVol);
            areaPropertiesNode.SetInt32("EnvAudio", _git.AreaProperties.EnvAudio);
            areaPropertiesNode.SetInt32("MusicBattle", _git.AreaProperties.MusicBattle);
            areaPropertiesNode.SetInt32("MusicDay", _git.AreaProperties.MusicDay);
            areaPropertiesNode.SetInt32("MusicNight", _git.AreaProperties.MusicNight);
            areaPropertiesNode.SetInt32("MusicDelay", _git.AreaProperties.MusicDelay);

            var gffCameras = gff.Root.SetList("CameraList", new());
            foreach (var camera in _git.CameraList)
            {
                var gffCamera = gffCameras.Add();
                gffCamera.SetInt32("CameraID", camera.CameraID);
                gffCamera.SetVector3("Position", camera.Position);
                gffCamera.SetSingle("Pitch", camera.Pitch);
                gffCamera.SetSingle("MicRange", camera.MicRange);
                gffCamera.SetVector4("Orientation", camera.Orientation);
                gffCamera.SetSingle("Height", camera.Height);
                gffCamera.SetSingle("FieldOfView", camera.FieldOfView);
            }

            var gffCreatures = gff.Root.SetList("CreatureList", new());
            foreach (var creature in _git.CreatureList)
            {
                var gffCreature = gffCreatures.Add();
                gffCreature.SetSingle("XPosition", creature.XPosition);
                gffCreature.SetSingle("YPosition", creature.YPosition);
                gffCreature.SetSingle("ZPosition", creature.ZPosition);
                gffCreature.SetSingle("XOrientation", creature.XOrientation);
                gffCreature.SetSingle("YOrientation", creature.YOrientation);
                gffCreature.SetResRef("TemplateResRef", creature.TemplateResRef);
            }

            var gffDoors = gff.Root.SetList("DoorList", new());
            foreach (var door in _git.DoorList)
            {
                var gffDoor = gffDoors.Add();
                gffDoor.SetResRef("TemplateResRef", door.TemplateResRef);
                gffDoor.SetString("Tag", door.Tag);
                gffDoor.SetResRef("LinkedToModule", door.LinkedToModule);
                gffDoor.SetString("LinkedTo", door.LinkedTo);
                gffDoor.SetUInt8("LinkedToFlags", door.LinkedToFlags);
                gffDoor.SetLocalizedString("TransitionDestin", door.TransitionDestin);
                gffDoor.SetSingle("X", door.X);
                gffDoor.SetSingle("Y", door.Y);
                gffDoor.SetSingle("Z", door.Z);
                gffDoor.SetSingle("Bearing", door.Bearing);
                gffDoor.SetUInt8("UseTweakColor", door.UseTweakColor);
                gffDoor.SetUInt32("TweakColor", door.TweakColor);
            }

            var gffEncounters = gff.Root.SetList("EncounterList", new());
            foreach (var encounter in _git.EncounterList)
            {
                var gffEncounter = gffEncounters.Add();
                gffEncounter.SetResRef("TemplateResRef", encounter.TemplateResRef);
                gffEncounter.SetSingle("XPosition", encounter.XPosition);
                gffEncounter.SetSingle("YPosition", encounter.YPosition);
                gffEncounter.SetSingle("ZPosition", encounter.ZPosition);

                var gffPoints = gff.Root.SetList("EncounterList", new());
                foreach (var point in encounter.Geometry)
                {
                    var gffPoint = gffPoints.Add();
                    gffEncounter.SetSingle("X", point.X);
                    gffEncounter.SetSingle("Y", point.Y);
                    gffEncounter.SetSingle("Z", point.Z);
                }

                var gffSpawnPoints = gff.Root.SetList("EncounterList", new());
                foreach (var spawnPoint in encounter.SpawnPointList)
                {
                    var gffSpawnPoint = gffSpawnPoints.Add();
                    gffSpawnPoint.SetSingle("X", spawnPoint.X);
                    gffSpawnPoint.SetSingle("Y", spawnPoint.Y);
                    gffSpawnPoint.SetSingle("Z", spawnPoint.Z);
                    gffSpawnPoint.SetSingle("Orientation", spawnPoint.Orientation);
                }
            }

            var gffSounds = gff.Root.SetList("SoundList", new());
            foreach (var sound in _git.SoundList)
            {
                var gffSound = gffSounds.Add();
                gffSound.SetSingle("XPosition", sound.XPosition);
                gffSound.SetSingle("YPosition", sound.YPosition);
                gffSound.SetSingle("ZPosition", sound.ZPosition);
                gffSound.SetUInt32("GeneratedType", sound.GeneratedType);
                gffSound.SetResRef("TemplateResRef", sound.TemplateResRef);
            }

            var gffStores = gff.Root.SetList("StoreList", new());
            foreach (var store in _git.StoreList)
            {
                var gffStore = gffStores.Add();
                gffStore.SetSingle("XPosition", store.XPosition);
                gffStore.SetSingle("YPosition", store.YPosition);
                gffStore.SetSingle("ZPosition", store.ZPosition);
                gffStore.SetSingle("XOrientation", store.XOrientation);
                gffStore.SetSingle("YOrientation", store.YOrientation);
                gffStore.SetResRef("ResRef", store.ResRef);
            }

            var gffTriggers = gff.Root.SetList("TriggerList", new());
            foreach (var trigger in _git.TriggerList)
            {
                var gffTrigger = gffTriggers.Add();
                gffTrigger.SetSingle("XPosition", trigger.XPosition);
                gffTrigger.SetSingle("YPosition", trigger.YPosition);
                gffTrigger.SetSingle("ZPosition", trigger.ZPosition);
                gffTrigger.SetSingle("XOrientation", trigger.XOrientation);
                gffTrigger.SetSingle("YOrientation", trigger.YOrientation);
                gffTrigger.SetSingle("ZOrientation", trigger.ZOrientation);
                gffTrigger.SetResRef("TemplateResRef", trigger.TemplateResRef);
                gffTrigger.SetResRef("Tag", trigger.Tag);
                gffTrigger.SetLocalizedString("TransitionDestin", trigger.TransitionDestin);
                gffTrigger.SetUInt8("LinkedToFlags", trigger.LinkedToFlags);
                gffTrigger.SetString("LinkedTo", trigger.LinkedTo);
                gffTrigger.SetResRef("LinkedToModules", trigger.LinkedToModule);

                var gffPoints = gff.Root.SetList("EncounterList", new());
                foreach (var point in trigger.Geometry)
                {
                    var gffPoint = gffPoints.Add();
                    gffPoint.SetSingle("PointX", point.X);
                    gffPoint.SetSingle("PointY", point.Y);
                    gffPoint.SetSingle("PointZ", point.Z);
                }
            }

            var gffWaypoints = gff.Root.SetList("WaypointList", new());
            foreach (var waypoint in _git.WaypointList)
            {
                var gffWaypoint = gffWaypoints.Add();
                gffWaypoint.SetUInt8("Appearance", waypoint.Appearance);
                gffWaypoint.SetString("LinkedTo", waypoint.LinkedTo);
                gffWaypoint.SetResRef("TemplateResRef", waypoint.TemplateResRef);
                gffWaypoint.SetLocalizedString("LocalizedName", waypoint.LocalizedName);
                gffWaypoint.SetLocalizedString("Description", waypoint.Description);
                gffWaypoint.SetUInt8("HasMapNote", waypoint.HasMapNote);
                gffWaypoint.SetLocalizedString("MapNote", waypoint.MapNote);
                gffWaypoint.SetUInt8("MapNoteEnabled", waypoint.MapNoteEnabled);
                gffWaypoint.SetSingle("XPosition", waypoint.XPosition);
                gffWaypoint.SetSingle("YPosition", waypoint.YPosition);
                gffWaypoint.SetSingle("ZPosition", waypoint.ZPosition);
                gffWaypoint.SetSingle("XOrientation", waypoint.XOrientation);
                gffWaypoint.SetSingle("YOrientation", waypoint.YOrientation);
                gffWaypoint.SetResRef("TemplateResRef", waypoint.TemplateResRef);
            }

            var gffList = gff.Root.SetList("List", new());
            foreach (var item in _git.List)
            {
                var gffItem = gffList.Add();
                gffItem.SetSingle("XPosition", item.XPosition);
                gffItem.SetSingle("YPosition", item.YPosition);
                gffItem.SetSingle("ZPosition", item.ZPosition);
                gffItem.SetSingle("XOrientation", item.XOrientation);
                gffItem.SetSingle("YOrientation", item.YOrientation);
                gffItem.SetResRef("TemplateResRef", item.TemplateResRef);
            }

            return gff;
        }
    }
}
