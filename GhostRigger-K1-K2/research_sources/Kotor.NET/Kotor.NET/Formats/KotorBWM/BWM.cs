using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Geometry;
using Kotor.NET.Extensions;
using Vector3 = Kotor.NET.Common.Geometry.Vector3;

namespace Kotor.NET.Formats.KotorBWM
{
    public class BWM
    {
        public BWMType Type { get; set; }
        public Vector3 Position { get; set; }
        public List<BWMFace> Faces { get; set; }

        public IEnumerable<BWMFace> CalculateWalkableFaces()
        {
            return Faces.Where(x => x.Material.IsWalkable()).ToArray();
        }

        public IEnumerable<BWMFace> CalculateUnWalkableFaces()
        {
            return Faces.Where(x => !x.Material.IsWalkable()).ToArray();
        }

        public BWMAABB CalculateAABBs()
        {
            return CalculateAABBs(Faces.ToList());
        }
        private BWMAABB CalculateAABBs(List<BWMFace> faces)
        {
            var boundingBox = new BoundingBox(faces);
            var boundingBoxSize = boundingBox.CalculateSize();
            var boundingBoxCentre = boundingBox.CalculateCentre();

            if (faces.Count == 1)
            {
                var aabb = new BWMAABB(boundingBox, faces.Single());
                return aabb; //return new List<BWMAABB> { aabb }; 
            }

            var splitaxis = Axis.X;

            if (boundingBoxSize.Y > boundingBoxSize.X)
                splitaxis = Axis.Y;
            if (boundingBoxSize.Z > boundingBoxSize.Y)
                splitaxis = Axis.Z;

            var changeaxis = true;
            foreach (var face in faces)
            {
                changeaxis = changeaxis && face.CalculateCentre()[splitaxis] == boundingBoxCentre[splitaxis];
            }

            var testedAxis = 1;
            var rightFaces = new List<BWMFace>();
            var leftFaces = new List<BWMFace>();
            while (true)
            {
                foreach (var face in faces)
                {
                    var centre = face.CalculateCentre();
                    if (centre[splitaxis] < boundingBoxCentre[splitaxis])
                    {
                        leftFaces.Add(face);
                    }
                    else
                    {
                        rightFaces.Add(face);
                    }
                }

                if (rightFaces.Count > 0 && leftFaces.Count > 0)
                    break;

                splitaxis = (splitaxis == Axis.Z) ? 0 : (splitaxis + 1);

                testedAxis++;
                if (testedAxis == 3)
                {
                    throw new ArgumentException(); // TODO
                }
            }

            var lefts = CalculateAABBs(leftFaces);
            var rights = CalculateAABBs(rightFaces);
            return new BWMAABB(boundingBox, (int)splitaxis + 1, lefts, rights);
        }

        public IEnumerable<BWMEdge> CalculateEdges()
        {
            var walkable = CalculateWalkableFaces();


            // TODO
            return null;
        }

        public BoundingBox CalculateBoundingBox()
        {
            return new BoundingBox(Faces);
        }

        public IEnumerable<Vector3> GetAllVertices()
        {
            return Faces.SelectMany(x => x.Vertices).ToArray();
        }

        public IEnumerable<BWMFace> FindAdjacencies()
        {
            var adjacencies = new List<BWMAdjacency>();

            var list = Faces.ToList();
            while (list.Any())
            {
                var source = list.First();
                list.RemoveAt(0);

                foreach (var target in Faces)
                {
                    if (target == source)
                        continue;


                }
            }

            // TODO
            return null;
        }

        public IEnumerable<BWMFace> FindFace(bool walkableOnly)
        {
            // TODO
            return null;
        }

        public void PerformTranslation(float x, float y, float z)
        {
            // TODO
        }

        public void PerformRotation(float yaw)
        {
            // TODO
        }

        public void PerformReflection(bool X, bool Y)
        {
            // TODO
        }

        public void SwitchRoomLink(int oldIndex, int newIndex)
        {
            // TODO
        }
    }

    public enum BWMType
    {
        PlaceableOrDoor = 0,
        Area = 1,
    }

    public class BWMFace
    {
        public SurfaceMaterial Material { get; set; }
        public Vector3 Normal { get; set; } = new();
        public BWMFace[] Adjacencies { get; } = new BWMFace[3];
        public Vector3[] Vertices { get; } = new Vector3[3];

        public BWMFace(SurfaceMaterial material, Vector3 normal, BWMFace[] adjacencies, Vector3[] vertices)
        {
            Material = material;
            Normal = normal;
            Adjacencies = adjacencies;
            Vertices = vertices;
        }

        public Vector3 CalculateCentre()
        {
            return new(
                Vertices.Average(x => x.X),
                Vertices.Average(x => x.Y),
                Vertices.Average(x => x.Z)
            );
        }

        public BWMFace FindAdjacency(BWMFace target)
        {
            var sourceMatches = new HashSet<int>();
            var targetMatches = new HashSet<int>();

            foreach (var sourceVertex in Vertices)
            {
                foreach (var targetVertex in target.Vertices)
                {
                    if (sourceVertex.Equals(targetVertex, 0.01f))
                    {
                        sourceMatches.Add(Array.IndexOf(Vertices, sourceVertex));
                        targetMatches.Add(Array.IndexOf(target.Vertices, targetVertex));
                    }
                }
            }

            if (sourceMatches.Count == 2)
            {

            }
            return null;
        }
    }

    public class BWMAdjacency
    {
        public BWMFace Face1 { get; set; }
        public int EdgeIndex1 { get; set; }

        public BWMFace Face2 { get; set; }
        public int EdgeIndex2 { get; set; }

        public BWMAdjacency(BWMFace face1, int edgeIndex1, BWMFace face2, int edgeIndex2)
        {
            Face1 = face1;
            EdgeIndex1 = edgeIndex1;
            Face2 = face2;
            EdgeIndex2 = edgeIndex2;
        }
    }

    public class BWMEdge
    {
        public int Transition { get; set; } = -1;
    }

    public class BWMAABB
    {
        public BoundingBox BoundingBox { get; }
        public BWMFace Face { get; }
        public int SignificantPlane { get; }
        public BWMAABB? Left { get; }
        public BWMAABB? Right { get; }

        public BWMAABB(BoundingBox boundingBox, int significantPlane, BWMAABB left, BWMAABB right)
        {
            BoundingBox = boundingBox;
            SignificantPlane = significantPlane;
            Left = left;
            Right = right;
        }

        public BWMAABB(BoundingBox boundingBox, BWMFace face)
        {
            BoundingBox = boundingBox;
            Face = face;
        }
    }
}
