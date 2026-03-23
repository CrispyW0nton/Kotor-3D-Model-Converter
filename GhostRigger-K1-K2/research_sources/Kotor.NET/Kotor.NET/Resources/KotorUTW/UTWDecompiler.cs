using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorUTW
{
    public class UTWDecompiler : IGFFCompiler
    {
        private UTW _utw;

        public UTWDecompiler(UTW utw)
        {
            _utw = utw;
        }

        public GFF CompileGFF()
        {
            var gff = new GFF();

            gff.Root.SetUInt8("Appearance", _utw.Appearance);
            gff.Root.SetString("LinkedTo", _utw.LinkedTo);
            gff.Root.SetResRef("TemplateResRef", _utw.TemplateResRef);
            gff.Root.SetString("Tag", _utw.Tag);
            gff.Root.SetLocalizedString("LocalizedName", _utw.LocalizedName);
            gff.Root.SetLocalizedString("Description", _utw.Description);
            gff.Root.SetUInt8("HasMapNote", _utw.HasMapNote);
            gff.Root.SetLocalizedString("MapNote", _utw.MapNote);
            gff.Root.SetUInt8("MapNoteEnabled", _utw.MapNoteEnabled);
            gff.Root.SetUInt8("PaletteID", _utw.PaletteID);
            gff.Root.SetString("Comment", _utw.Comment);
            gff.Root.SetResRef("LinkedToModule", _utw.LinkedToModule);

            return gff;
        }
    }

}
