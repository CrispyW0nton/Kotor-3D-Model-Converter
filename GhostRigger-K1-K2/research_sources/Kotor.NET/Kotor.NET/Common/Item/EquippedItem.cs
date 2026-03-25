using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Common.Item
{
    public class EquippedItem
    {
        public ResRef ResRef { get; set; } = "";
        public EquipmentSlot Slot { get; set; }
        public bool Droppable { get; set; }
    }
}
