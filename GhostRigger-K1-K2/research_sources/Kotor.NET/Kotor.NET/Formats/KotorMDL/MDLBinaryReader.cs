using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
using Kotor.NET.Common.Geometry;
using static Kotor.NET.Formats.KotorMDL.MDLBinaryStructure;

namespace Kotor.NET.Formats.KotorMDL
{
    public class MDLBinaryReader : IReader<MDL>
    {
        private BinaryReader _reader;
        private BinaryReader _mdxReader;
        private MDL? _mdl;
        private FileRoot _bin;

        public MDLBinaryReader(string filepath, string mdxFilepath)
        {
            var data = File.ReadAllBytes(filepath);
            data = data.TakeLast(data.Length - 12).ToArray();
            _reader = new BinaryReader(new MemoryStream(data));

            var mdxData = File.ReadAllBytes(mdxFilepath);
            _mdxReader = new BinaryReader(new MemoryStream(mdxData));
        }
        public MDLBinaryReader(byte[] data, byte[] mdxData)
        {
            data = data.TakeLast(data.Length - 12).ToArray();
            _reader = new BinaryReader(new MemoryStream(data));

            _mdxReader = new BinaryReader(new MemoryStream(mdxData));
        }
        public MDLBinaryReader(Stream stream, Stream mdxStream)
        {
            _reader = new BinaryReader(stream);
            var length = (int)(stream.Length - stream.Length);
            var data = _reader.ReadBytes(length).TakeLast(length - 12).ToArray();
            _reader = new BinaryReader(new MemoryStream(data));

            _mdxReader = new BinaryReader(mdxStream);
        }

        public MDL Read()
        {
            _mdl = new MDL();

            _bin = new FileRoot(_reader);

            _mdl.Fog = _bin.ModelHeader.Fog != 0;
            _mdl.AnimationScale = _bin.ModelHeader.AnimationScale;
            _mdl.Supermodel = _bin.ModelHeader.SupermodelName;
            _mdl.ModelType = _bin.ModelHeader.ModelType;
            _mdl.ModelName = _bin.ModelHeader.GeometryHeader.Name;
            _mdl.Root = BuildNode(_bin.RootNode);
            _mdl.Animations = _bin.Animations.Select(x => new Animation
            {
                Name = x.Header.GeometryHeader.Name,
                AnimationLength = x.Header.AnimationLength,
                TransitionTime = x.Header.TransitionTime,
                AnimationRoot = x.Header.AnimationRoot,
                GeometryType = x.Header.GeometryHeader.GeometryType,
                RootNode = BuildNode(x.RootNode),
                Events = x.Events.Select(x => new Event
                {
                    ActivationTime = x.ActivationTime,
                    Name = x.Name,
                }).ToList(),
            }).ToList();

            return _mdl;
        }

        private Node BuildNode(NodeRoot binaryNode)
        {
            Node node = new Node();

            node.Name = _bin.Names[binaryNode.NodeHeader!.NodeNumber];

            if (binaryNode.LightHeader is not null)
            {
                node.Light = new();

                node.Light.FlareRadius = binaryNode.LightHeader.FlareRadius;
                node.Light.AmbientOnly = binaryNode.LightHeader.AmbientOnly;
                node.Light.DynamicType = binaryNode.LightHeader.DynamicType;
                node.Light.AffectDynamic = binaryNode.LightHeader.AffectDynamic;
                node.Light.Shadow = binaryNode.LightHeader.Shadow;
                node.Light.Flare = binaryNode.LightHeader.Flare;
                node.Light.LightPriority = binaryNode.LightHeader.LightPriority;

                for (int i = 0; i < binaryNode.FlareSizes.Count; i++)
                {
                    var flare = new LightLensFlare();
                    node.Light.LensFlare.Add(flare);

                    flare.Size = binaryNode.FlareSizes[i];
                    flare.Texture = binaryNode.FlareTextures[i];
                    flare.Position = binaryNode.FlarePositions[i];
                    flare.ColorShift = binaryNode.FlareColorShifts[i];
                }
            }

            if (binaryNode.TrimeshHeader is not null)
            {
                node.Trimesh = new();
                node.Trimesh.DiffuseColor = binaryNode.TrimeshHeader.Diffuse;
                node.Trimesh.AmbientColor = binaryNode.TrimeshHeader.Ambient;
                node.Trimesh.TransperencyHint = binaryNode.TrimeshHeader.TransparencyHint;
                node.Trimesh.DiffuseTexture = binaryNode.TrimeshHeader.Texture;
                node.Trimesh.LightmapTexture = binaryNode.TrimeshHeader.Lightmap;
                // node.Trimesh.SaberValue1;
                // node.Trimesh.SaberValue2;
                node.Trimesh.Render = binaryNode.TrimeshHeader.DoesRender != 0;
                node.Trimesh.Shadow = binaryNode.TrimeshHeader.HasShadow != 0;
                node.Trimesh.Beaming = binaryNode.TrimeshHeader.Beaming != 0;
                node.Trimesh.Lightmap = binaryNode.TrimeshHeader.HasLightmap != 0;
                node.Trimesh.RotateTexture = binaryNode.TrimeshHeader.RotateTexture != 0;
                node.Trimesh.BackgroundGeometry = binaryNode.TrimeshHeader.BackgroundGeometry != 0;
                node.Trimesh.AnimateUV = binaryNode.TrimeshHeader.AnimateUV != 0;

                node.Trimesh.UVDirection = binaryNode.TrimeshHeader.UVDirection;
                node.Trimesh.UVSpeed = binaryNode.TrimeshHeader.UVSpeed;
                node.Trimesh.UVJitter = binaryNode.TrimeshHeader.UVJitterSpeed;

                var vertices = new List<Vertex>();
                for (int i = 0; i < binaryNode.TrimeshHeader.VertexCount; i++)
                {
                    var vertex = new Vertex();
                    vertices.Add(vertex);

                    if ((binaryNode.TrimeshHeader.MDXDataBitmap & NodeRoot.VertexFlag) != 0)
                    {
                        _mdxReader.BaseStream.Position = binaryNode.TrimeshHeader.MDXOffsetToData + binaryNode.TrimeshHeader.MDXPositionStride + (i * binaryNode.TrimeshHeader.MDXDataSize);
                        vertex.Position = new Vector3(_mdxReader.ReadSingle(), _mdxReader.ReadSingle(), _mdxReader.ReadSingle());
                    }

                    if ((binaryNode.TrimeshHeader.MDXDataBitmap & NodeRoot.NormalFlag) != 0)
                    {
                        _mdxReader.BaseStream.Position = binaryNode.TrimeshHeader.MDXOffsetToData + binaryNode.TrimeshHeader.MDXNormalStride + (i * binaryNode.TrimeshHeader.MDXDataSize);
                        vertex.Normal = new Vector3(_mdxReader.ReadSingle(), _mdxReader.ReadSingle(), _mdxReader.ReadSingle());
                    }

                    if ((binaryNode.TrimeshHeader.MDXDataBitmap & NodeRoot.UV1Flag) != 0)
                    {
                        _mdxReader.BaseStream.Position = binaryNode.TrimeshHeader.MDXOffsetToData + binaryNode.TrimeshHeader.MDXTexture1Stride + (i * binaryNode.TrimeshHeader.MDXDataSize);
                        vertex.DiffuseUV = new Vector2(_mdxReader.ReadSingle(), _mdxReader.ReadSingle());
                    }

                    if ((binaryNode.TrimeshHeader.MDXDataBitmap & NodeRoot.UV2Flag) != 0)
                    {
                        _mdxReader.BaseStream.Position = binaryNode.TrimeshHeader.MDXOffsetToData + binaryNode.TrimeshHeader.MDXTexture2Stride + (i * binaryNode.TrimeshHeader.MDXDataSize);
                        vertex.LightmapUV = new Vector2(_mdxReader.ReadSingle(), _mdxReader.ReadSingle());
                    }
                }

                binaryNode.TrimeshFaces.ForEach(x => node.Trimesh.Faces.Add(new Face()));
                for (int i = 0; i < binaryNode.TrimeshFaces.Count; i++)
                {
                    var binaryFace = binaryNode.TrimeshFaces[i];
                    var face = node.Trimesh.Faces[i];
                    face.FaceNormal = binaryFace.Normal;
                    face.PlaneDistance = binaryFace.PlaneCoefficient;
                    face.MaterialID = binaryFace.Material;
                    face.Vertex1 = vertices[binaryFace.Vertex1];
                    face.Vertex2 = vertices[binaryFace.Vertex2];
                    face.Vertex3 = vertices[binaryFace.Vertex3];
                    face.Adjacent1 = (binaryFace.FaceAdjacency1 == 0xFFFF) ? null : node.Trimesh.Faces[binaryFace.FaceAdjacency1];
                    face.Adjacent2 = (binaryFace.FaceAdjacency2 == 0xFFFF) ? null : node.Trimesh.Faces[binaryFace.FaceAdjacency2];
                    face.Adjacent3 = (binaryFace.FaceAdjacency3 == 0xFFFF) ? null : node.Trimesh.Faces[binaryFace.FaceAdjacency3];
                }
            }

            foreach (var binNodeChild in binaryNode.Children)
            {
                node.Children.Add(BuildNode(binNodeChild));
            }

            foreach (var binController in binaryNode.Controllers)
            {
                var controller = new Controller();
                controller.ControllerType = binController.ControllerType;
                controller.Bezier = binController.Padding1;
                for (int i = 0; i < binController.DataRowCount; i++)
                {
                    var row = new ControllerRow();
                    controller.Rows.Add(row);

                    row.TimeKey = BitConverter.ToSingle(binaryNode.ControllerData.ElementAt(binController.FirstKeyOffset));

                    if (controller.ControllerType == 20 && binController.ColumnCount == 2)
                    {
                        row.Data = binaryNode.ControllerData.GetRange(binController.FirstDataOffset, 1).ToList();
                    }
                    else if ((binController.ColumnCount & 0x10) != 0)
                    {
                        row.Data = binaryNode.ControllerData.GetRange(binController.FirstDataOffset, (binController.ColumnCount & 0x0F) * 3).ToList();
                    }
                    else
                    {
                        row.Data = binaryNode.ControllerData.GetRange(binController.FirstDataOffset, binController.ColumnCount).ToList();
                    }

                    
                }
                node.Controllers.Add(controller);
            }

            return node;
        }
    }
}
