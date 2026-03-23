using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace MapBuilder.Data
{
    public class AssetData
    {
        public required byte[] MDL { get; init; }
        public required byte[] MDX { get; set; }
        public required byte[] WOK { get; set; }
        public required dynamic Metadata { get; set; }
        public Dictionary<string, byte[]> TPCs { get; set; } = new();
    }
}
