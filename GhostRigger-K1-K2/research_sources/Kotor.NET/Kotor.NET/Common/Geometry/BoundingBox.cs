using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorBWM;

namespace Kotor.NET.Common.Geometry
{
    public class BoundingBox
    {
        public Vector3 Minimum { get; set; }
        public Vector3 Maximum { get; set; }
        // TODO
        // plus getters for all 8 points of bounding box

        public BoundingBox(Vector3 minimum, Vector3 maximum)
        {
            Minimum = minimum;
            Maximum = maximum;
        }

        public BoundingBox(List<BWMFace> faces)
        {
            Maximum = new Vector3(-9999999, -9999999, -9999999);
            Minimum = new Vector3(9999999, 9999999, 9999999);

            foreach (var face in faces)
            {
                foreach (var vertex in face.Vertices)
                {
                    Maximum.X = MathF.Max(Maximum.X, vertex.X);
                    Maximum.Y = MathF.Max(Maximum.Y, vertex.Y);
                    Maximum.Z = MathF.Max(Maximum.Z, vertex.Z);

                    Minimum.X = MathF.Min(Minimum.X, vertex.X);
                    Minimum.Y = MathF.Min(Minimum.Y, vertex.Y);
                    Minimum.Z = MathF.Min(Minimum.Z, vertex.Z);
                }
            }
        }

        public bool Contains(Vector3 vector3, bool includeEdges = true)
        {
            // TODO
            throw new NotImplementedException();
        }

        public Vector3 CalculateCentre()
        {
            return new(
                (Maximum.X - Minimum.X) / 2,
                (Maximum.Y - Minimum.Y) / 2,
                (Maximum.Z - Minimum.Z) / 2
            );
        }

        public Vector3 CalculateSize()
        {
            return Maximum - Minimum;
        }
    }
}
