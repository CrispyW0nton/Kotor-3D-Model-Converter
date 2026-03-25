using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Data;

namespace Kotor.NET.Common.Item
{
    public class StoredItem
    {
        public ResRef ResRef { get; set; } = "";
        public bool Droppable { get; set; }
    }
}
