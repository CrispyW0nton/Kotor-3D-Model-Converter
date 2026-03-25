using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTW
{
    public class UTWCompiler : IGFFDecompiler<UTW>
    {
        private GFF _gff;

        public UTWCompiler(GFF gff)
        {
            _gff = gff;
        }

        public UTW Decompile()
        {
            var utw = new UTW
            {
                Appearance = _gff.Root.GetUInt8("Appearance", 0),
                LinkedTo = _gff.Root.GetString("LinkedTo", ""),
                TemplateResRef = _gff.Root.GetResRef("TemplateResRef", new ResRef()),
                Tag = _gff.Root.GetString("Tag", ""),
                LocalizedName = _gff.Root.GetLocalizedString("LocalizedName", new LocalizedString()),
                Description = _gff.Root.GetLocalizedString("Description", new LocalizedString()),
                HasMapNote = _gff.Root.GetUInt8("HasMapNote", 0),
                MapNote = _gff.Root.GetLocalizedString("MapNote", new LocalizedString()),
                MapNoteEnabled = _gff.Root.GetUInt8("MapNoteEnabled", 0),
                PaletteID = _gff.Root.GetUInt8("PaletteID", 0),
                Comment = _gff.Root.GetString("Comment", ""),
                LinkedToModule = _gff.Root.GetResRef("LinkedToModule", new ResRef())
            };

            return utw;
        }
    }

}
