using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Geometry;

namespace Kotor.NET.Formats.KotorLYT
{
    public class LYT
    {
        public List<LYTRoom> Rooms { get; set; }
        public List<LYTDoorHook> DoorHooks { get; set; }
        public List<LYTTrack> Tracks { get; set; }
        public List<LYTObstacle> Obstacles { get; set; }
    }

    public class LYTRoom
    {
        public string Model { get; set; }
        public Vector3 Position { get; set; }
    }

    public class LYTDoorHook
    {
        public string Model { get; set; }
        public string Door { get; set; }
        public Vector3 Position { get; set; }
        public Vector4 Orientation { get; set; }
    }

    public class LYTTrack
    {
        public string Model { get; set; }
        public Vector3 Position { get; set; }
    }

    public class LYTObstacle
    {
        public string Model { get; set; }
        public Vector3 Position { get; set; }
    }
}
