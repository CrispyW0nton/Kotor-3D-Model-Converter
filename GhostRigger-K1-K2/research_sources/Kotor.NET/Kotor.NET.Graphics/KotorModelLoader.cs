using Kotor.NET.Common.Geometry;
using Kotor.NET.Extensions;
using Kotor.NET.Graphics.SceneObjects;

namespace Kotor.NET.Graphics
{
    public class KotorModelLoader
    {
        private BinaryReader mdlReader;
        private BinaryReader mdxReader;
        private string _name;

        public KotorModelLoader(byte[] mdlData, byte[] mdxData)
        {
            mdlReader = new BinaryReader(new MemoryStream(mdlData.Skip(12).ToArray()));
            mdxReader = new BinaryReader(new MemoryStream(mdxData));
        }

        public KotorObject Read(Graphics graphics, string name = "mesh")
        {
            _name = name;

            mdlReader.BaseStream.Position = 40;
            var offsets = new List<int> { mdlReader.ReadInt32() };
            var rootNode = ReadNode(graphics, mdlReader, mdxReader, offsets[0]);

            return rootNode;
        }

        private KotorObject ReadNode(Graphics graphics, BinaryReader mdlReader, BinaryReader mdxReader, int offset)
        {
            mdlReader.BaseStream.Position = offset;
            var node = new Node();
            string vao = null;

            node.Type = mdlReader.ReadInt16();
            node.NameIndex = mdlReader.ReadInt16();
            node.NodeIndex = mdlReader.ReadInt16();
            node.Padding = mdlReader.ReadInt16();
            node.RootOffset = mdlReader.ReadInt32();
            node.ParentOffset = mdlReader.ReadInt32();
            node.Position = mdlReader.ReadVector3();
            node.Orientation = mdlReader.ReadVector4();
            node.ChildArrayOffset = mdlReader.ReadInt32();
            node.ChildrenCount = mdlReader.ReadInt32();
            if (node.HasTrimesh)
            {
                mdlReader.BaseStream.Position += 28;
                node.FunctionPointer0 = mdlReader.ReadInt32();
                node.FunctionPointer1 = mdlReader.ReadInt32();
                node.FacesCount = mdlReader.ReadInt32();
                node.FacesOffset = mdlReader.ReadInt32();
                mdlReader.BaseStream.Position += 4;
                node.BoundingBoxMin = mdlReader.ReadVector3();
                node.BoundingBoxMax = mdlReader.ReadVector3();
                node.Radius = mdlReader.ReadSingle();
                node.AveragePoint = mdlReader.ReadVector3();
                mdlReader.BaseStream.Position += 3*4*2;
                //node.Diffuse = mdlReader.ReadColour();
                //node.Ambient = mdlReader.ReadColour();
                node.TransparencyHint = mdlReader.ReadInt32();
                node.Texture = mdlReader.ReadString(32);
                node.Lightmap = mdlReader.ReadString(32);
                mdlReader.BaseStream.Position += 24;

                node.VertexCountOffset = mdlReader.ReadInt32();
                mdlReader.BaseStream.Position += 8;
                node.VertexIndicesOffset = mdlReader.ReadInt32();
                mdlReader.BaseStream.Position += 60;
                node.MDXDataSize = mdlReader.ReadUInt32();
                node.MDXDataBitmap = mdlReader.ReadInt32();
                node.MDXVertexPosition = mdlReader.ReadUInt32();
                node.MDXVertexNormal = mdlReader.ReadUInt32();
                node.MDXVertexColor = mdlReader.ReadUInt32();
                node.MDXVertexUV1 = mdlReader.ReadUInt32();
                node.MDXVertexUV2 = mdlReader.ReadUInt32();
                node.MDXVertexUV3 = mdlReader.ReadUInt32();
                node.MDXVertexUV4 = mdlReader.ReadUInt32();
                node.MDXUnknown1 = mdlReader.ReadInt32();
                node.MDXUnknown2 = mdlReader.ReadInt32();
                node.MDXUnknown3 = mdlReader.ReadInt32();
                node.MDXUnknown4 = mdlReader.ReadInt32();
                node.VertexCount = mdlReader.ReadInt16();
                node.TextureCount = mdlReader.ReadInt16();
                node.HasLightmap = mdlReader.ReadByte();
                node.RotateTexture = mdlReader.ReadByte();
                node.IsBackgroundGeometry = mdlReader.ReadByte();
                node.HasShadow = mdlReader.ReadByte();
                node.Beaming = mdlReader.ReadByte();
                node.DoesRender = mdlReader.ReadByte();
                mdlReader.BaseStream.Position += 10;
                if (node.IsTSL)
                    mdlReader.BaseStream.Position += 8;
                node.MDXDataOffset = mdlReader.ReadInt32();
                node.VertexOffset = mdlReader.ReadInt32();
            }

            if (node.HasTrimesh)
            {
                mdlReader.BaseStream.Position = node.VertexIndicesOffset;
                var indicesOffset = mdlReader.ReadInt32();
                mdlReader.BaseStream.Position = node.VertexCountOffset;
                var indicesCount = mdlReader.ReadInt32();
                mdlReader.BaseStream.Position = indicesOffset;
                node.Indices = mdlReader.ReadBytes(indicesCount * 2);

                mdxReader.BaseStream.Position = node.MDXDataOffset;
                var data = mdxReader.ReadBytes((int)node.MDXDataSize * node.VertexCount);

                vao = _name + ":" + node.NodeIndex;
                var vertexArray = new VertexArray(graphics.GL, data, node.Indices, node.MDXVertexPosition, node.MDXVertexNormal, node.MDXVertexUV1, node.MDXVertexUV2, node.MDXDataSize, node.MDXDataBitmap);
                graphics.SetVAO(vao, vertexArray);
            }

            var childrenOffsets = new int[node.ChildrenCount];
            mdlReader.BaseStream.Position = node.ChildArrayOffset;
            for (int i = 0; i < node.ChildrenCount; i++)
            {
                childrenOffsets[i] = mdlReader.ReadInt32();
            }

            var kotorObject = new KotorObject(vao, node.Texture);
            for (int i = 0; (i < childrenOffsets.Length); i++)
            {
                kotorObject.Children.Add(ReadNode(graphics, mdlReader, mdxReader, childrenOffsets[i]));
            }

            return kotorObject;
        }

        private class Node
        {
            public short Type { get; set; }
            public short NameIndex { get; set; }
            public short NodeIndex { get; set; }
            public short Padding { get; set; }
            public int RootOffset { get; set; }
            public int ParentOffset { get; set; }
            public Vector3 Position { get; set; }
            public Vector4 Orientation { get; set; }
            public int ChildArrayOffset { get; set; }
            public int ChildrenCount { get; set; }

            public int FunctionPointer0 { get; set; }
            public int FunctionPointer1 { get; set; }
            public int FacesOffset { get; set; }
            public int FacesCount { get; set; }
            public Vector3 BoundingBoxMin { get; set; }
            public Vector3 BoundingBoxMax { get; set; }
            public float Radius { get; set; }
            public Vector3 AveragePoint { get; set; }
            public Color Diffuse { get; set; }
            public Color Ambient { get; set; }
            public int TransparencyHint { get; set; }
            public string Texture { get; set; }
            public string Lightmap { get; set; }
            public int VertexCountOffset { get; set; }
            public int VertexIndicesOffset { get; set; }
            public uint MDXDataSize { get; set; }
            public int MDXDataBitmap { get; set; }
            public uint MDXVertexPosition { get; set; }
            public uint MDXVertexNormal { get; set; }
            public uint MDXVertexColor { get; set; }
            public uint MDXVertexUV1 { get; set; }
            public uint MDXVertexUV2 { get; set; }
            public uint MDXVertexUV3 { get; set; }
            public uint MDXVertexUV4 { get; set; }
            public int MDXUnknown1 { get; set; }
            public int MDXUnknown2 { get; set; }
            public int MDXUnknown3 { get; set; }
            public int MDXUnknown4 { get; set; }
            public short VertexCount { get; set; }
            public short TextureCount { get; set; }
            public byte HasLightmap { get; set; }
            public byte RotateTexture { get; set; }
            public byte IsBackgroundGeometry { get; set; }
            public byte HasShadow { get; set; }
            public byte Beaming { get; set; }
            public byte DoesRender { get; set; }
            public int MDXDataOffset { get; set; }
            public int VertexOffset { get; set; }

            public byte[] Indices { get; set; }
            public byte[] Vertices { get; set; }

            public bool HasTrimesh => (Type & 0x20) != 0;
            public bool IsTSL => FunctionPointer0 == 4216880 || FunctionPointer0 == 4216816 || FunctionPointer0 == 4216864;
        }
    }
}
