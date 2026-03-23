using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTS
{
    public class UTSDecompiler : IGFFCompiler
    {
        private UTS _uts;

        public UTSDecompiler(UTS uts)
        {
            _uts = uts;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetString("Tag", _uts.Tag);
            gff.Root.SetLocalizedString("LocName", _uts.LocName);
            gff.Root.SetResRef("TemplateResRef", _uts.TemplateResRef);
            gff.Root.SetUInt8("Active", _uts.Active);
            gff.Root.SetUInt8("Continuous", _uts.Continuous);
            gff.Root.SetUInt8("Looping", _uts.Looping);
            gff.Root.SetUInt8("Positional", _uts.Positional);
            gff.Root.SetUInt8("RandomPosition", _uts.RandomPosition);
            gff.Root.SetUInt8("Random", _uts.Random);
            gff.Root.SetSingle("Elevation", _uts.Elevation);
            gff.Root.SetSingle("MaxDistance", _uts.MaxDistance);
            gff.Root.SetSingle("MinDistance", _uts.MinDistance);
            gff.Root.SetSingle("RandomRangeX", _uts.RandomRangeX);
            gff.Root.SetSingle("RandomRangeY", _uts.RandomRangeY);
            gff.Root.SetUInt32("Interval", _uts.Interval);
            gff.Root.SetUInt32("IntervalVrtn", _uts.IntervalVrtn);
            gff.Root.SetSingle("PitchVariation", _uts.PitchVariation);
            gff.Root.SetUInt8("Priority", _uts.Priority);
            gff.Root.SetUInt32("Hours", _uts.Hours);
            gff.Root.SetUInt8("Times", _uts.Times);
            gff.Root.SetUInt8("Volume", _uts.Volume);
            gff.Root.SetUInt8("VolumeVrtn", _uts.VolumeVrtn);
            gff.Root.SetUInt8("PaletteID", _uts.PaletteID);
            gff.Root.SetString("Comment", _uts.Comment);

            var soundsList = gff.Root.SetList("Sounds", new());
            foreach (var resref in _uts.Sounds)
            {
                var soundStruct = soundsList.Add();
                soundStruct.SetResRef("Sound", resref);
            }

            return gff;
        }
    }

}
