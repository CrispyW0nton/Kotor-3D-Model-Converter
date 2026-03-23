using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Resources.KotorUTM
{
    public class UTM
    {
        public ResRef ResRef { get; set; } = "";
        public LocalizedString LocName { get; set; } = -1;
        public string Tag { get; set; } = "";
        public int MarkUp { get; set; }
        public int MarkDown { get; set; }
        public ResRef OnOpenStore { get; set; } = "";
        public byte BuySellFlag { get; set; }
        public List<UTMItem> ItemList { get; set; } = new();
        public byte ID { get; set; }
        public string Comment { get; set; } = "";
    }

    public class UTMItem
    {
        public ResRef InventoryRes { get; set; } = "";
        public byte Infinite { get; set; }
    }
}
