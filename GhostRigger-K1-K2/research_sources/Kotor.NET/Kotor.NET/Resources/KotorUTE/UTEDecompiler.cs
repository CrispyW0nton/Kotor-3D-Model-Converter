using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTE
{
    public class UTEDecompiler : IGFFCompiler
    {
        private UTE _ute;

        public UTEDecompiler(UTE ute)
        {
            _ute = ute;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetString("Tag", _ute.Tag);
            gff.Root.SetLocalizedString("LocalizedName", _ute.LocalizedName);
            gff.Root.SetResRef("TemplateResRef", _ute.TemplateResRef);
            gff.Root.SetUInt8("Active", _ute.Active);
            gff.Root.SetInt32("Difficulty", _ute.Difficulty);
            gff.Root.SetInt32("DifficultyIndex", _ute.DifficultyIndex);
            gff.Root.SetUInt32("Faction", _ute.Faction);
            gff.Root.SetInt32("MaxCreatures", _ute.MaxCreatures);
            gff.Root.SetUInt8("PlayerOnly", _ute.PlayerOnly);
            gff.Root.SetInt32("RecCreatures", _ute.RecCreatures);
            gff.Root.SetUInt8("Reset", _ute.Reset);
            gff.Root.SetInt32("ResetTime", _ute.ResetTime);
            gff.Root.SetInt32("Respawns", _ute.Respawns);
            gff.Root.SetInt32("SpawnOption", _ute.SpawnOption);
            gff.Root.SetResRef("OnEntered", _ute.OnEntered);
            gff.Root.SetResRef("OnExit", _ute.OnExit);
            gff.Root.SetResRef("OnExhausted", _ute.OnExhausted);
            gff.Root.SetResRef("OnHeartbeat", _ute.OnHeartbeat);
            gff.Root.SetResRef("OnUserDefined", _ute.OnUserDefined);
            gff.Root.SetUInt8("PaletteID", _ute.PaletteID);
            gff.Root.SetString("Comment", _ute.Comment);

            var creatureList = gff.Root.SetList("CreatureList", new());
            foreach (var creature in _ute.Creatures)
            {
                var creatureNode = creatureList.Add();
                creatureNode.SetInt32("GuaranteedCount", creature.GuaranteedCount);
                creatureNode.SetInt32("Appearance", creature.Appearance);
                creatureNode.SetSingle("CR", creature.CR);
                creatureNode.SetResRef("ResRef", creature.ResRef);
                creatureNode.SetUInt8("SingleSpawn", creature.SingleSpawn);
            }

            return gff;
        }
    }
}
