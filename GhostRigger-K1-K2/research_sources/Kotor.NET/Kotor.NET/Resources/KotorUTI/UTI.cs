using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Resources.KotorUTI
{
    public class UTI
    {
        public uint AddCost { get; set; }
        public int BaseItem { get; set; }
        public byte BodyVariation { get; set; }
        public byte Charges { get; set; }
        public string Comment { get; set; } = "";
        public uint Cost { get; set; }
        public LocalizedString DescIdentified { get; set; } = new();
        public LocalizedString Description { get; set; } = new();
        public LocalizedString LocalizedName { get; set; } = new();
        public byte ModelVariation { get; set; }
        public byte PaletteID { get; set; }
        public byte Plot { get; set; }
        public ushort StackSize { get; set; }
        public string Tag { get; set; } = "";
        public ResRef TemplateResRef { get; set; } = "";
        public byte TextureVar { get; set; }
        public byte UpgradeLevel { get; set; }
        public byte Stolen { get; set; }
        public byte Identified { get; set; }
        public List<UTIProperty> Properties { get; set; } = new();
    }

    public class UTIProperty
    {
        public byte CostTable { get; set; }
        public ushort CostValue { get; set; }
        public byte Param1 { get; set; }
        public byte Param1Value { get; set; }
        public ushort PropertyName { get; set; }
        public ushort Subtype { get; set; }
        public byte UpgradeType { get; set; }
        public byte ChanceAppear { get; set; }
    }
}
