using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Resources.KotorUTW
{
    public class UTW
    {
        public byte Appearance { get; set; }
        public string LinkedTo { get; set; } = "";
        public ResRef TemplateResRef { get; set; } = "";
        public string Tag { get; set; } = "";
        public LocalizedString LocalizedName { get; set; } = new();
        public LocalizedString Description { get; set; } = new();
        public byte HasMapNote { get; set; }
        public LocalizedString MapNote { get; set; } = new();
        public byte MapNoteEnabled { get; set; }
        public byte PaletteID { get; set; }
        public string Comment { get; set; } = "";
        public ResRef LinkedToModule { get; set; } = "";
    }
}
