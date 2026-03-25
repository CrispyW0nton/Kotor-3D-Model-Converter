using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace MapBuilder.Data
{
    public class MapData
    {
        public List<Placement> Placements { get; set; } = new();

        public MapData()
        {
            Placements = new()
            {
                new TerrainData(50, 50),
            };
        }
    }
}
