using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Graphics.SceneObjects;

namespace MapBuilder.Data
{
    public abstract class Placement
    {
        public string Label { get; set; } = "";

        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }

        public float Pitch { get; set; }
        public float Yaw { get; set; }
        public float Roll { get; set; }

        public bool CarveWalkmesh { get; set; }
    }
}
