using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Geometry
{
    public class Face
    {
        public Vertex Vertex1 { get; set; } = new();
        public Vertex Vertex2 { get; set; } = new();
        public Vertex Vertex3 { get; set; } = new();

        public Face? Adjacent1 { get; set; }
        public Face? Adjacent2 { get; set; }
        public Face? Adjacent3 { get; set; }

        public Vector3 FaceNormal { get; set;} = new();
        public float PlaneDistance { get; set; }
        public uint MaterialID { get; set; } = new();
    }

    public class Vertex
    {
        public Vector3? Position { get; set; }
        public Vector3? Normal { get; set; }
        public Vector3? Color { get; set; }
        public Vector2? DiffuseUV { get; set; }
        public Vector2? LightmapUV { get; set; }
    }
}
