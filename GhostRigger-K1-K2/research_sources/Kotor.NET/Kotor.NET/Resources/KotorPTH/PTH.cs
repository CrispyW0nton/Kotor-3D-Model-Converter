using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Resources.KotorPTH
{
    public class PTH
    {
        public List<PathPoint> Points { get; set; }

        public PTH()
        {
            Points = new List<PathPoint>();
        }
    }

    public class PathPoint
    {
        public List<PathPoint> Connections { get; set; }
        public float X { get; set; }
        public float Y { get; set; }

        public PathPoint()
        {
            Connections = new List<PathPoint>();
        }
    }
}
