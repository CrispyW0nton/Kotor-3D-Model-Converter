using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTE
{
    public class UTECompiler : IGFFDecompiler<UTE>
    {
        private GFF _gff;

        public UTECompiler(GFF gff)
        {
            _gff = gff;
        }

        public UTE Decompile()
        {
            var ute = new UTE
            {
                Tag = _gff.Root.GetString("Tag", ""),
                LocalizedName = _gff.Root.GetLocalizedString("LocalizedName", new LocalizedString()),
                TemplateResRef = _gff.Root.GetResRef("TemplateResRef", new ResRef()),
                Active = _gff.Root.GetUInt8("Active", 0),
                Difficulty = _gff.Root.GetInt32("Difficulty", 0),
                DifficultyIndex = _gff.Root.GetInt32("DifficultyIndex", 0),
                Faction = _gff.Root.GetUInt32("Faction", 0),
                MaxCreatures = _gff.Root.GetInt32("MaxCreatures", 0),
                PlayerOnly = _gff.Root.GetUInt8("PlayerOnly", 0),
                RecCreatures = _gff.Root.GetInt32("RecCreatures", 0),
                Reset = _gff.Root.GetUInt8("Reset", 0),
                ResetTime = _gff.Root.GetInt32("ResetTime", 0),
                Respawns = _gff.Root.GetInt32("Respawns", 0),
                SpawnOption = _gff.Root.GetInt32("SpawnOption", 0),
                OnEntered = _gff.Root.GetResRef("OnEntered", new ResRef()),
                OnExit = _gff.Root.GetResRef("OnExit", new ResRef()),
                OnExhausted = _gff.Root.GetResRef("OnExhausted", new ResRef()),
                OnHeartbeat = _gff.Root.GetResRef("OnHeartbeat", new ResRef()),
                OnUserDefined = _gff.Root.GetResRef("OnUserDefined", new ResRef()),
                PaletteID = _gff.Root.GetUInt8("PaletteID", 0),
                Comment = _gff.Root.GetString("Comment", ""),

                Creatures = _gff.Root.GetList("CreatureList").Select(gffCreature => new UTECreature
                {
                    GuaranteedCount = gffCreature.GetInt32("GuaranteedCount", 0),
                    Appearance = gffCreature.GetInt32("Appearance", 0),
                    CR = gffCreature.GetSingle("CR", 0),
                    ResRef = gffCreature.GetResRef("ResRef", new ResRef()),
                    SingleSpawn = gffCreature.GetUInt8("SingleSpawn", 0),
                }).ToList(),
            };

            return ute;
        }
    }
}
