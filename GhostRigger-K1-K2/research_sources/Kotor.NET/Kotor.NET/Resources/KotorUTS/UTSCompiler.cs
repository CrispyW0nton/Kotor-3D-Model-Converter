using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTS
{
    public class UTSCompiler : IGFFDecompiler<UTS>
    {
        private GFF _gff;

        public UTSCompiler(GFF gff)
        {
            _gff = gff;
        }

        public UTS Decompile()
        {
            var uts = new UTS
            {
                Tag = _gff.Root.GetString("Tag", ""),
                LocName = _gff.Root.GetLocalizedString("LocName", new LocalizedString()),
                TemplateResRef = _gff.Root.GetResRef("TemplateResRef", new ResRef()),
                Active = _gff.Root.GetUInt8("Active", 0),
                Continuous = _gff.Root.GetUInt8("Continuous", 0),
                Looping = _gff.Root.GetUInt8("Looping", 0),
                Positional = _gff.Root.GetUInt8("Positional", 0),
                RandomPosition = _gff.Root.GetUInt8("RandomPosition", 0),
                Random = _gff.Root.GetUInt8("Random", 0),
                Elevation = _gff.Root.GetSingle("Elevation", 0),
                MaxDistance = _gff.Root.GetSingle("MaxDistance", 0),
                MinDistance = _gff.Root.GetSingle("MinDistance", 0),
                RandomRangeX = _gff.Root.GetSingle("RandomRangeX", 0),
                RandomRangeY = _gff.Root.GetSingle("RandomRangeY", 0),
                Interval = _gff.Root.GetUInt32("Interval", 0),
                IntervalVrtn = _gff.Root.GetUInt32("IntervalVrtn", 0),
                PitchVariation = _gff.Root.GetSingle("PitchVariation", 0),
                Priority = _gff.Root.GetUInt8("Priority", 0),
                Hours = _gff.Root.GetUInt32("Hours", 0),
                Times = _gff.Root.GetUInt8("Times", 0),
                Volume = _gff.Root.GetUInt8("Volume", 0),
                VolumeVrtn = _gff.Root.GetUInt8("VolumeVrtn", 0),
                PaletteID = _gff.Root.GetUInt8("PaletteID", 0),
                Comment = _gff.Root.GetString("Comment", ""),

                Sounds = _gff.Root.GetList("Sounds", new()).Select(gffSound => gffSound.GetResRef("Sound")).ToList(),
            };

            return uts;
        }
    }
}
