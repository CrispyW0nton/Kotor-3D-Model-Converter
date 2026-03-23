using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Geometry;
using Kotor.NET.Extensions;

namespace Kotor.NET.Formats.KotorMDL
{
    public class MDLBinaryStructure
    {
        public class FileRoot
        {
            public ModelHeader ModelHeader { get; set; }
            public List<int> NameOffsets { get; set; } = new();
            public List<string> Names { get; set; } = new();
            public List<int> AnimationOffsets = new();
            public List<AnimationRoot> Animations { get; set; } = new();
            public NodeRoot RootNode { get; set; }

            public FileRoot()
            {
                ModelHeader = new();
            }

            public FileRoot(BinaryReader reader)
            {
                ModelHeader = new ModelHeader(reader);

                reader.BaseStream.Position = ModelHeader.OffsetToNameOffsetArray;
                for (int i = 0; i < ModelHeader.NamesArrayCount; i++)
                {
                    NameOffsets.Add(reader.ReadInt32());
                }
                foreach (var nameOffset in NameOffsets)
                {
                    reader.BaseStream.Position = nameOffset;
                    Names.Add(reader.ReadTerminatedString('\0'));
                }

                reader.BaseStream.Position = ModelHeader.AnimationOffsetArrayOffset;
                for (int i = 0; i < ModelHeader.AnimationCount; i ++)
                {
                    AnimationOffsets.Add(reader.ReadInt32());
                }
                foreach (var animationOffset in AnimationOffsets)
                {
                    reader.BaseStream.Position = animationOffset;
                    Animations.Add(new AnimationRoot(reader));
                }

                reader.BaseStream.Position = ModelHeader.GeometryHeader.RootNodeOffset;
                RootNode = new NodeRoot(reader);
            }

            public void Write(BinaryWriter writer)
            {
                ModelHeader.Write(writer);

                writer.BaseStream.Position = ModelHeader.OffsetToNameOffsetArray;
                for (int i = 0; i < NameOffsets.Count; i ++)
                {
                    var nameOffset = NameOffsets[i];
                    writer.Write(nameOffset);
                }
                for (int i = 0; i < NameOffsets.Count; i++)
                {
                    var nameOffset = NameOffsets[i];
                    var name = Names[i];
                    writer.BaseStream.Position = nameOffset;
                    writer.Write(name, 0);
                    writer.Write('\0');
                }

                writer.BaseStream.Position = ModelHeader.AnimationOffsetArrayOffset;
                for (int i = 0; i < AnimationOffsets.Count; i ++)
                {
                    var animationOffset = AnimationOffsets[i];
                    writer.Write(animationOffset);
                }
                for (int i = 0; i < AnimationOffsets.Count; i++)
                {
                    var animationOffset = AnimationOffsets[i];
                    var animation = Animations[i];
                    writer.BaseStream.Position = animationOffset;
                    animation.Write(writer);
                }

                writer.BaseStream.Position = ModelHeader.OffsetToRootNode;
                RootNode.Write(writer);
            }
        }

        public class ModelHeader
        {
            public static readonly int SIZE = GeometryHeader.SIZE + 116;

            public GeometryHeader GeometryHeader { get; set; } = new();
            public Byte ModelType { get; set; }
            public Byte Unknown1 { get; set; }
            public Byte Padding1 { get; set; }
            public Byte Fog { get; set;}
            public Int32 ChildModelCount { get; set; }
            public Int32 AnimationOffsetArrayOffset { get; set; }
            public Int32 AnimationCount { get; set; }
            public Int32 AnimationCount2 { get; set; }
            public Int32 Unknown2 { get; set; }
            public Vector3 BoundingBoxMin { get; set; } = new();
            public Vector3 BoundingBoxMax { get; set; } = new();
            public Single Radius { get; set; }
            public Single AnimationScale { get; set; }
            public String SupermodelName { get; set; } = "";
            public Int32 OffsetToRootNode { get; set; }
            public Int32 Unused1 { get; set; }
            public Int32 MDXSize { get; set; }
            public Int32 MDXOffset { get; set; }
            public Int32 OffsetToNameOffsetArray { get; set; }
            public Int32 NamesArrayCount { get; set; }
            public Int32 NamesArrayCount2 { get; set; }

            public ModelHeader()
            {

            }

            public ModelHeader(BinaryReader reader)
            {
                GeometryHeader = new(reader);
                ModelType = reader.ReadByte();
                Unknown1 = reader.ReadByte();
                Padding1 = reader.ReadByte();
                Fog = reader.ReadByte();
                ChildModelCount = reader.ReadInt32();
                AnimationOffsetArrayOffset = reader.ReadInt32();
                AnimationCount = reader.ReadInt32();
                AnimationCount2 = reader.ReadInt32();
                Unknown2 = reader.ReadInt32();
                BoundingBoxMin = reader.ReadVector3();
                BoundingBoxMax = reader.ReadVector3();
                Radius = reader.ReadSingle();
                AnimationScale = reader.ReadSingle();
                SupermodelName = reader.ReadString(32);
                OffsetToRootNode = reader.ReadInt32();
                Unused1 = reader.ReadInt32();
                MDXSize = reader.ReadInt32();
                MDXOffset = reader.ReadInt32();
                OffsetToNameOffsetArray = reader.ReadInt32();
                NamesArrayCount = reader.ReadInt32();
                NamesArrayCount2 = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                GeometryHeader.Write(writer);
                writer.Write(ModelType);
                writer.Write(Unknown1);
                writer.Write(Padding1);
                writer.Write(Fog);
                writer.Write(ChildModelCount);
                writer.Write(AnimationOffsetArrayOffset);
                writer.Write(AnimationCount);
                writer.Write(AnimationCount2);
                writer.Write(Unknown2);
                writer.Write(BoundingBoxMin);
                writer.Write(BoundingBoxMax);
                writer.Write(Radius);
                writer.Write(AnimationScale);
                writer.Write(SupermodelName.Resize(32), 0);
                writer.Write(OffsetToRootNode);
                writer.Write(Unused1);
                writer.Write(MDXSize);
                writer.Write(MDXOffset);
                writer.Write(OffsetToNameOffsetArray);
                writer.Write(NamesArrayCount);
                writer.Write(NamesArrayCount2);
            }
        }

        public class GeometryHeader
        {
            public static readonly int SIZE = 80;

            public static readonly int K1_NORMAL_FP1 = 4273776;
            public static readonly int K1_NORMAL_FP2 = 4216096;
            public static readonly int K1_ANIM_FP1 = 4273392;
            public static readonly int K1_ANIM_FP2 = 4451552;

            public static readonly int K2_NORMAL_FP1 = 4285200;
            public static readonly int K2_NORMAL_FP2 = 4216320;
            public static readonly int K2_ANIM_FP1 = 4284816;
            public static readonly int K2_ANIM_FP2 = 4522928;

            public Int32 FunctionPointer1 { get; set; }
            public Int32 FunctionPointer2 { get; set; }
            public String Name { get; set; } = "";
            public Int32 RootNodeOffset { get; set; }
            public Int32 NodeCount { get; set; }
            public Int32 Unknown1 { get; set; }
            public Int32 Unknown2 { get; set; }
            public Int32 Unknown3 { get; set; }
            public Int32 Unknown4 { get; set; }
            public Int32 Unknown5 { get; set; }
            public Int32 Unknown6 { get; set; }
            public Int32 Unknown7 { get; set; }
            public Byte GeometryType { get; set; }
            public Byte Padding1 { get; set; }
            public Byte Padding2 { get; set; }
            public Byte Padding3 { get; set; }

            public GeometryHeader()
            {

            }

            public GeometryHeader(BinaryReader reader)
            {
                FunctionPointer1 = reader.ReadInt32();
                FunctionPointer2 = reader.ReadInt32();
                Name = reader.ReadString(32);
                RootNodeOffset = reader.ReadInt32();
                NodeCount = reader.ReadInt32();
                Unknown1 = reader.ReadInt32();
                Unknown2 = reader.ReadInt32();
                Unknown3 = reader.ReadInt32();
                Unknown4 = reader.ReadInt32();
                Unknown5 = reader.ReadInt32();
                Unknown6 = reader.ReadInt32();
                Unknown7 = reader.ReadInt32();
                GeometryType = reader.ReadByte();
                Padding1 = reader.ReadByte();
                Padding2 = reader.ReadByte();
                Padding3 = reader.ReadByte();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(FunctionPointer1);
                writer.Write(FunctionPointer2);
                writer.Write(Name.Resize(32), 0);
                writer.Write(RootNodeOffset);
                writer.Write(NodeCount);
                writer.Write(Unknown1);
                writer.Write(Unknown2);
                writer.Write(Unknown3);
                writer.Write(Unknown4);
                writer.Write(Unknown5);
                writer.Write(Unknown6);
                writer.Write(Unknown7);
                writer.Write(GeometryType);
                writer.Write(Padding1);
                writer.Write(Padding2);
                writer.Write(Padding3);
            }
        }

        public class AnimationRoot
        {
            public AnimationHeader Header { get; set; }
            public NodeRoot RootNode { get; set; }
            public List<EventRoot> Events { get; set; } = new();

            public AnimationRoot()
            {
                Header = new();
                RootNode = new();
            }

            public AnimationRoot(BinaryReader reader)
            {
                Header = new AnimationHeader(reader);

                reader.BaseStream.Position = Header.GeometryHeader.RootNodeOffset;
                RootNode = new NodeRoot(reader);

                reader.BaseStream.Position = Header.OffsetToEventArray;
                for (int i = 0; i < Header.EventCount1; i++)
                {
                    Events.Add(new EventRoot(reader));
                }
            }

            public void Write(BinaryWriter writer)
            {
                Header.Write(writer);
                RootNode.Write(writer);

                writer.BaseStream.Position = Header.GeometryHeader.RootNodeOffset;
                RootNode.Write(writer);

                writer.BaseStream.Position = Header.OffsetToEventArray;
                foreach (EventRoot e in Events)
                {
                    e.Write(writer);
                }
            }
        }

        public class AnimationHeader
        {
            public static readonly int SIZE = GeometryHeader.SIZE + 56;

            public GeometryHeader GeometryHeader { get; set; } = new GeometryHeader();
            public Single AnimationLength { get; set; }
            public Single TransitionTime { get; set; }
            public String AnimationRoot { get; set; } = "";
            public Int32 OffsetToEventArray { get; set; }
            public Int32 EventCount1 { get; set; }
            public Int32 EventCount2 { get; set; }
            public Int32 Unknown { get; set; }

            public AnimationHeader()
            {

            }

            public AnimationHeader(BinaryReader reader)
            {
                GeometryHeader = new GeometryHeader(reader);
                AnimationLength = reader.ReadSingle();
                TransitionTime = reader.ReadSingle();
                AnimationRoot = reader.ReadString(32);
                OffsetToEventArray = reader.ReadInt32();
                EventCount1 = reader.ReadInt32();
                EventCount2 = reader.ReadInt32();
                Unknown = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                GeometryHeader.Write(writer);
                writer.Write(AnimationLength);
                writer.Write(TransitionTime);
                writer.Write(AnimationRoot.Resize(32), 0);
                writer.Write(OffsetToEventArray);
                writer.Write(EventCount1);
                writer.Write(EventCount2);
                writer.Write(Unknown);
            }
        }

        public class EventRoot
        {
            public static readonly int SIZE = 36;

            public Single ActivationTime { get; set; }
            public String Name { get; set; } = "";

            public EventRoot()
            {

            }

            public EventRoot(BinaryReader reader)
            {
                ActivationTime = reader.ReadSingle();
                Name = reader.ReadString(32);
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(ActivationTime);
                writer.Write(Name.Resize(32), 0);
            }
        }

        public class ControllerHeader
        {
            public static readonly int SIZE = 16;

            public UInt32 ControllerType { get; set; }
            public UInt16 Unknown { get; set; } = 0xFFFF;
            public Int16 DataRowCount { get; set; }
            public Int16 FirstKeyOffset { get; set; }
            public Int16 FirstDataOffset { get; set; }
            public Byte ColumnCount { get; set; }
            public Byte Padding1 { get; set; }
            public Byte Padding2 { get; set; }
            public Byte Padding3 { get; set; }

            public ControllerHeader()
            {

            }

            public ControllerHeader(BinaryReader reader)
            {
                ControllerType = reader.ReadUInt32();
                Unknown = reader.ReadUInt16();
                DataRowCount = reader.ReadInt16();
                FirstKeyOffset = reader.ReadInt16();
                FirstDataOffset = reader.ReadInt16();
                ColumnCount = reader.ReadByte();
                Padding1 = reader.ReadByte();
                Padding2 = reader.ReadByte();
                Padding3 = reader.ReadByte();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(ControllerType);
                writer.Write(Unknown);
                writer.Write(DataRowCount);
                writer.Write(FirstKeyOffset);
                writer.Write(FirstDataOffset);
                writer.Write(ColumnCount);
                writer.Write(Padding1);
                writer.Write(Padding2);
                writer.Write(Padding3);
            }
        }

        public class NodeRoot
        {
            public static readonly ushort NodeFlag = 0x00000001;
            public static readonly ushort LightFlag = 0x00000002;
            public static readonly ushort EmitterFlag = 0x00000004;
            public static readonly ushort CameraFlag = 0x00000008;
            public static readonly ushort ReferenceFlag = 0x00000010;
            public static readonly ushort TrimeshFlag = 0x00000020;
            public static readonly ushort SkinFlag = 0x00000040;
            public static readonly ushort AnimationFlag = 0x00000080;
            public static readonly ushort DanglyFlag = 0x00000100;
            public static readonly ushort AABBFlag = 0x00000200;
            public static readonly ushort SaberFlag = 0x00000800;

            public static readonly uint VertexFlag = 0x00000001;
            public static readonly uint UV1Flag = 0x00000002;
            public static readonly uint UV2Flag = 0x00000004;
            public static readonly uint UV3Flag = 0x00000008;
            public static readonly uint UV4Flag = 0x00000010;
            public static readonly uint NormalFlag = 0x00000020;
            public static readonly uint ColorsFlag = 0x00000040;
            public static readonly uint Tangent1Flag = 0x00000080;
            public static readonly uint Tangent2Flag = 0x00000100;
            public static readonly uint Tangent3Flag = 0x00000200;
            public static readonly uint Tangent4Flag = 0x00000400;

            public NodeHeader? NodeHeader { get; set; } = new();
            public LightHeader? LightHeader { get; set; }
            public EmitterHeader? EmitterHeader { get; set; }
            //public CameraFlag NodeHeader { get; set; }
            public ReferenceHeader? ReferenceHeader { get; set; }
            public TrimeshHeader? TrimeshHeader { get; set; }
            public SkinmeshHeader? SkinmeshHeader { get; set; }
            //public NodeHeader NodeHeader { get; set; }
            public DanglymeshHeader? DanglymeshHeader { get; set; }
            //public WalkmeshHeader NodeHeader { get; set; }
            public SabermeshHeader? SabermeshHeader { get; set; }

            public List<int> ChildrenOffsets { get; set; } = new();
            public List<NodeRoot> Children { get; set; } = new();
            public List<ControllerHeader> Controllers { get; set; } = new();
            public List<byte[]> ControllerData { get; set; } = new();

            public List<float> FlareSizes { get; set; } = new();
            public List<string> FlareTextures { get; set; } = new();
            public List<float> FlarePositions { get; set; } = new();
            public List<Common.Geometry.Color> FlareColorShifts { get; set; } = new();

            public List<FaceRoot> TrimeshFaces { get; set; } = new();
            public List<Vector3> TrimeshVertices { get; set; } = new();

            public NodeRoot()
            {

            }

            public NodeRoot(BinaryReader reader)
            {
                NodeHeader = new NodeHeader(reader);

                if ((NodeHeader.NodeType & LightFlag) != 0) LightHeader = new LightHeader(reader);
                if ((NodeHeader.NodeType & EmitterFlag) != 0) EmitterHeader = new EmitterHeader(reader);
                if ((NodeHeader.NodeType & ReferenceFlag) != 0) ReferenceHeader = new ReferenceHeader(reader);
                if ((NodeHeader.NodeType & TrimeshFlag) != 0) TrimeshHeader = new TrimeshHeader(reader);
                if ((NodeHeader.NodeType & SkinFlag) != 0) SkinmeshHeader = new SkinmeshHeader(reader);
                if ((NodeHeader.NodeType & DanglyFlag) != 0) DanglymeshHeader = new DanglymeshHeader(reader);
                if ((NodeHeader.NodeType & SaberFlag) != 0) SabermeshHeader = new SabermeshHeader(reader);

                

                if (TrimeshHeader is not null)
                {
                    reader.BaseStream.Position = TrimeshHeader.OffsetToFaceArray;
                    for (int i = 0; i < TrimeshHeader.FaceArrayCount; i++)
                    {
                        TrimeshFaces.Add(new FaceRoot(reader));
                    }
                }

                reader.BaseStream.Position = NodeHeader.OffsetToChildArray;
                for (int i = 0; i < NodeHeader.ChildArrayCount; i++)
                {
                    ChildrenOffsets.Add(reader.ReadInt32());
                }

                reader.BaseStream.Position = NodeHeader.OffsetToControllerArray;
                for (int i = 0; i < NodeHeader.ControllerArrayCount; i++)
                {
                    Controllers.Add(new ControllerHeader(reader));
                }

                reader.BaseStream.Position = NodeHeader.OffsetToControllerData;
                for (int i = 0; i < NodeHeader.ControllerDataCount; i ++)
                {
                    ControllerData.Add(reader.ReadBytes(4));
                }

                foreach (var childOffset in ChildrenOffsets)
                {
                    reader.BaseStream.Position = childOffset;
                    Children.Add(new NodeRoot(reader));
                }
            }

            public void Write(BinaryWriter writer)
            {
                if (NodeHeader is not null) NodeHeader.Write(writer);
                if (LightHeader is not null) LightHeader.Write(writer);
                if (EmitterHeader is not null) EmitterHeader.Write(writer);
                if (ReferenceHeader is not null) ReferenceHeader.Write(writer);
                if (TrimeshHeader is not null) TrimeshHeader.Write(writer);
                if (SkinmeshHeader is not null) SkinmeshHeader.Write(writer);
                if (DanglymeshHeader is not null) DanglymeshHeader.Write(writer);
                if (SabermeshHeader is not null) SabermeshHeader.Write(writer);

                if (LightHeader is not null)
                {
                    writer.BaseStream.Position = LightHeader.OffsetTosFlareSizeArray;
                    foreach (var size in FlareSizes)
                    {
                        writer.Write(size);
                    }

                    writer.BaseStream.Position = LightHeader.OffsetToFlarePositionArray;
                    foreach (var position in FlarePositions)
                    {
                        writer.Write(position);
                    }

                    writer.BaseStream.Position = LightHeader.OffsetToFlareColorShiftArray;
                    foreach (var shift in FlareColorShifts)
                    {
                        writer.Write(shift);
                    }

                    writer.BaseStream.Position = LightHeader.OffsetToFlareTextureNameArray;
                    foreach (var texture in FlareTextures)
                    {
                        writer.Write(texture.PadRight(12, '\0'), 0);
                    }
                }

                if (TrimeshHeader is not null)
                {
                    writer.BaseStream.Position = TrimeshHeader.OffsetToVertexArray;
                    foreach (var vertex in TrimeshVertices)
                    {
                        writer.Write(vertex);
                    }

                    writer.BaseStream.Position = TrimeshHeader.OffsetToFaceArray;
                    foreach (var face in TrimeshFaces)
                    {
                        face.Write(writer);
                    }
                }

                writer.BaseStream.Position = NodeHeader.OffsetToChildArray;
                foreach (var childOffset in ChildrenOffsets)
                {
                    writer.Write(childOffset);
                }

                writer.BaseStream.Position = NodeHeader.OffsetToControllerArray;
                foreach (var controller in Controllers)
                {
                    controller.Write(writer);
                }

                writer.BaseStream.Position = NodeHeader.OffsetToControllerData;
                foreach (var data in ControllerData)
                {
                    writer.Write(data);
                }

                for (int i = 0; i < Children.Count; i ++)
                {
                    var child = Children[i];
                    var offset = ChildrenOffsets[i];
                    writer.BaseStream.Position = offset;
                    child.Write(writer);
                }
            }
        }

        public class NodeHeader
        {
            public static readonly int SIZE = 80;

            public UInt16 NodeType { get; set; }
            public UInt16 IndexNumber { get; set; }
            public UInt16 NodeNumber { get; set; }
            public UInt16 Padding { get; set; }
            public Int32 OffsetToRootNode { get; set; }
            public Int32 OffsetToParentNode { get; set; }
            public Vector3 Position { get; set; } = new();
            public Vector4 Rotation { get; set; } = new();
            public Int32 OffsetToChildArray { get; set; }
            public Int32 ChildArrayCount { get; set; }
            public Int32 ChildArrayCount2 { get; set; }
            public Int32 OffsetToControllerArray { get; set; }
            public Int32 ControllerArrayCount { get; set; }
            public Int32 ControllerArrayCount2 { get; set; }
            public Int32 OffsetToControllerData { get; set; }
            public Int32 ControllerDataCount { get; set; }
            public Int32 ControllerDataCount2 { get; set; }

            public NodeHeader()
            {

            }

            public NodeHeader(BinaryReader reader)
            {
                NodeType = reader.ReadUInt16();
                IndexNumber = reader.ReadUInt16();
                NodeNumber = reader.ReadUInt16();
                Padding = reader.ReadUInt16();
                OffsetToRootNode = reader.ReadInt32();
                OffsetToParentNode = reader.ReadInt32();
                Position = reader.ReadVector3();
                Rotation = reader.ReadVector4();
                OffsetToChildArray = reader.ReadInt32();
                ChildArrayCount = reader.ReadInt32();
                ChildArrayCount2 = reader.ReadInt32();
                OffsetToControllerArray = reader.ReadInt32();
                ControllerArrayCount = reader.ReadInt32();
                ControllerArrayCount2 = reader.ReadInt32();
                OffsetToControllerData = reader.ReadInt32();
                ControllerDataCount = reader.ReadInt32();
                ControllerDataCount2 = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(NodeType);
                writer.Write(IndexNumber);
                writer.Write(NodeNumber);
                writer.Write(Padding);
                writer.Write(OffsetToRootNode);
                writer.Write(OffsetToParentNode);
                writer.Write(Position);
                writer.Write(Rotation);
                writer.Write(OffsetToChildArray);
                writer.Write(ChildArrayCount);
                writer.Write(ChildArrayCount2);
                writer.Write(OffsetToControllerArray);
                writer.Write(ControllerArrayCount);
                writer.Write(ControllerArrayCount2);
                writer.Write(OffsetToControllerData);
                writer.Write(ControllerDataCount);
                writer.Write(ControllerDataCount2);
            }
        }

        public class TrimeshHeader
        {
            public static readonly int K1_SIZE = 332;
            public static readonly int K2_SIZE = 340;

            public static readonly uint K1_NORMAL_FP1 = 4216656;
            public static readonly uint K1_NORMAL_FP2 = 4216672;
            public static readonly uint K1_SKIN_FP1 = 4216592;
            public static readonly uint K1_SKIN_FP2 = 4216608;
            public static readonly uint K1_DANGLY_FP1 = 4216640;
            public static readonly uint K1_DANGLY_FP2 = 4216624;

            public static readonly uint K2_NORMAL_FP1 = 4216880;
            public static readonly uint K2_NORMAL_FP2 = 4216896;
            public static readonly uint K2_SKIN_FP1 = 4216816;
            public static readonly uint K2_SKIN_FP2 = 4216832;
            public static readonly uint K2_DANGLY_FP1 = 4216848;
            public static readonly uint K2_DANGLY_FP2 = 4216864;

            public bool IsTSL => new List<uint> { K2_NORMAL_FP1, K2_SKIN_FP1, K2_DANGLY_FP1 }.Contains(FunctionPointer1);

            public UInt32 FunctionPointer1 { get; set; }
            public UInt32 FunctionPointer2 { get; set; }
            public Int32 OffsetToFaceArray { get; set; }
            public Int32 FaceArrayCount { get; set; }
            public Int32 FaceArrayCount2 { get; set; }
            public Vector3 BoundingBoxMin { get; set; } = new();
            public Vector3 BoundingBoxMax { get; set; } = new();
            public Single Radius { get; set; }
            public Vector3 AveragePoint { get; set; } = new();
            public Vector3 Diffuse { get; set; } = new();
            public Vector3 Ambient { get; set; } = new();
            public UInt32 TransparencyHint { get; set; }
            public String Texture { get; set; } = "";
            public String Lightmap { get; set; } = "";
            public String Unused1 { get; set; } = "";
            public String Unused2 { get; set; } = "";
            public Int32 OffsetToVertexIndicesCountArray { get; set; }
            public Int32 VertexIndicesCountArrayCount { get; set; }
            public Int32 VertexIndicesCountArrayCount2 { get; set; }
            public Int32 OffsetToVertexOffsetArray { get; set; }
            public Int32 VertexOffsetArrayCount { get; set; }
            public Int32 VertexOffsetArrayCount2 { get; set; }
            public Int32 OffsetToInvertedCounterArray { get; set; }
            public Int32 InvertedCounterArrayCount { get; set; }
            public Int32 InvertedCounterArrayCount2 { get; set; }
            public Int32 Unknown1 { get; set; } = -1;
            public Int32 Unknown2 { get; set; } = -1;
            public Int32 Unknown3 { get; set; } = 0;
            public Int32 Unknown4 { get; set; }
            public Int32 Unknown8 { get; set; }
            public Int32 AnimateUV { get; set; }
            public Vector2 UVDirection { get; set; } = new();
            public Single UVSpeed { get; set; }
            public Single UVJitterSpeed { get; set; }
            public Int32 MDXDataSize { get; set; }
            public UInt32 MDXDataBitmap { get; set; }
            public Int32 MDXPositionStride { get; set; }
            public Int32 MDXNormalStride { get; set; }
            public Int32 MDXColorStride { get; set; }
            public Int32 MDXTexture1Stride { get; set; }
            public Int32 MDXTexture2Stride { get; set; }
            public Int32 MDXTexture3Stride { get; set; }
            public Int32 MDXTexture4Stride { get; set; }
            public Int32 MDXUnknown1Stride { get; set; }
            public Int32 MDXUnknown2Stride { get; set; }
            public Int32 MDXUnknown3Stride { get; set; }
            public Int32 MDXUnknown4Stride { get; set; }
            public UInt16 VertexCount { get; set; }
            public UInt16 TextureCount { get; set; }
            public Byte HasLightmap { get; set; }
            public Byte RotateTexture { get; set; }
            public Byte BackgroundGeometry { get; set; }
            public Byte HasShadow { get; set; }
            public Byte Beaming { get; set; }
            public Byte DoesRender { get; set; }
            public Byte Unknown5 { get; set; }
            public Byte Unknown6 { get; set; }
            public Single TotalArea { get; set; }
            public UInt32 Unknown7 { get; set; }

            public UInt32 TSLUnknown1 { get; set; }
            public UInt32 TSLUnknown2 { get; set; }
            public Int32 MDXOffsetToData { get; set; }
            public Int32 OffsetToVertexArray { get; set; }

            public TrimeshHeader()
            {

            }

            public TrimeshHeader(BinaryReader reader)
            {
                FunctionPointer1 = reader.ReadUInt32();
                FunctionPointer2 = reader.ReadUInt32();
                OffsetToFaceArray = reader.ReadInt32();
                FaceArrayCount = reader.ReadInt32();
                FaceArrayCount2 = reader.ReadInt32();
                BoundingBoxMin = reader.ReadVector3();
                BoundingBoxMax = reader.ReadVector3();
                Radius = reader.ReadSingle();
                AveragePoint = reader.ReadVector3();
                Diffuse = reader.ReadVector3();
                Ambient = reader.ReadVector3();
                TransparencyHint = reader.ReadUInt32();
                Texture = reader.ReadString(32);
                Lightmap = reader.ReadString(32);
                Unused1 = reader.ReadString(12);
                Unused2 = reader.ReadString(12);
                OffsetToVertexIndicesCountArray = reader.ReadInt32();
                VertexIndicesCountArrayCount = reader.ReadInt32();
                VertexIndicesCountArrayCount2 = reader.ReadInt32();
                OffsetToVertexOffsetArray = reader.ReadInt32();
                VertexOffsetArrayCount = reader.ReadInt32();
                VertexOffsetArrayCount2 = reader.ReadInt32();
                OffsetToInvertedCounterArray = reader.ReadInt32();
                InvertedCounterArrayCount = reader.ReadInt32();
                InvertedCounterArrayCount2 = reader.ReadInt32();
                Unknown1 = reader.ReadInt32();
                Unknown2 = reader.ReadInt32();
                Unknown3 = reader.ReadInt32();
                Unknown4 = reader.ReadInt32();
                Unknown8 = reader.ReadInt32();
                AnimateUV = reader.ReadInt32();
                UVDirection = reader.ReadVector2();
                UVSpeed = reader.ReadSingle();
                UVJitterSpeed = reader.ReadSingle();
                MDXDataSize = reader.ReadInt32();
                MDXDataBitmap = reader.ReadUInt32();
                MDXPositionStride = reader.ReadInt32();
                MDXNormalStride = reader.ReadInt32();
                MDXColorStride = reader.ReadInt32();
                MDXTexture1Stride = reader.ReadInt32();
                MDXTexture2Stride = reader.ReadInt32();
                MDXTexture3Stride = reader.ReadInt32();
                MDXTexture4Stride = reader.ReadInt32();
                MDXUnknown1Stride = reader.ReadInt32();
                MDXUnknown2Stride = reader.ReadInt32();
                MDXUnknown3Stride = reader.ReadInt32();
                MDXUnknown4Stride = reader.ReadInt32();
                VertexCount = reader.ReadUInt16();
                TextureCount = reader.ReadUInt16();
                HasLightmap = reader.ReadByte();
                RotateTexture = reader.ReadByte();
                BackgroundGeometry = reader.ReadByte();
                HasShadow = reader.ReadByte();
                Beaming = reader.ReadByte();
                DoesRender = reader.ReadByte();
                Unknown5 = reader.ReadByte();
                Unknown6 = reader.ReadByte();
                TotalArea = reader.ReadSingle();
                Unknown7 = reader.ReadUInt32();
                if (IsTSL)
                {
                    // 1 dirtenabled
                    // 1 padding
                    // 2 dirt tex
                    // 2 dirt coord space
                    // 1 hide in holograms
                    // 1 padding
                    TSLUnknown1 = reader.ReadUInt32();
                    TSLUnknown2 = reader.ReadUInt32();
                }
                MDXOffsetToData = reader.ReadInt32();
                OffsetToVertexArray = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(FunctionPointer1);
                writer.Write(FunctionPointer2);
                writer.Write(OffsetToFaceArray);
                writer.Write(FaceArrayCount);
                writer.Write(FaceArrayCount2);
                writer.Write(BoundingBoxMin);
                writer.Write(BoundingBoxMax);
                writer.Write(Radius);
                writer.Write(AveragePoint);
                writer.Write(Diffuse);
                writer.Write(Ambient);
                writer.Write(TransparencyHint);
                writer.Write(Texture.Resize(32), 0);
                writer.Write(Lightmap.Resize(32), 0);
                writer.Write(Unused1.Resize(12), 0);
                writer.Write(Unused2.Resize(12), 0);
                writer.Write(OffsetToVertexIndicesCountArray);
                writer.Write(VertexIndicesCountArrayCount);
                writer.Write(VertexIndicesCountArrayCount2);
                writer.Write(OffsetToVertexOffsetArray);
                writer.Write(VertexOffsetArrayCount);
                writer.Write(VertexOffsetArrayCount2);
                writer.Write(OffsetToInvertedCounterArray);
                writer.Write(InvertedCounterArrayCount);
                writer.Write(InvertedCounterArrayCount2);
                writer.Write(Unknown1);
                writer.Write(Unknown2);
                writer.Write(Unknown3);
                writer.Write(Unknown4);
                writer.Write(Unknown8);
                writer.Write(AnimateUV);
                writer.Write(UVDirection);
                writer.Write(UVSpeed);
                writer.Write(UVJitterSpeed);
                writer.Write(MDXDataSize);
                writer.Write(MDXDataBitmap);
                writer.Write(MDXPositionStride);
                writer.Write(MDXNormalStride);
                writer.Write(MDXColorStride);
                writer.Write(MDXTexture1Stride);
                writer.Write(MDXTexture2Stride);
                writer.Write(MDXTexture3Stride);
                writer.Write(MDXTexture4Stride);
                writer.Write(MDXUnknown1Stride);
                writer.Write(MDXUnknown2Stride);
                writer.Write(MDXUnknown3Stride);
                writer.Write(MDXUnknown4Stride);
                writer.Write(VertexCount);
                writer.Write(TextureCount);
                writer.Write(HasLightmap);
                writer.Write(RotateTexture);
                writer.Write(BackgroundGeometry);
                writer.Write(HasShadow);
                writer.Write(Beaming);
                writer.Write(DoesRender);
                writer.Write(Unknown5);
                writer.Write(Unknown6);
                writer.Write(TotalArea);
                writer.Write(Unknown7);
                if (IsTSL)
                {
                    writer.Write(TSLUnknown1);
                    writer.Write(TSLUnknown2);
                }
                writer.Write(MDXOffsetToData);
                writer.Write(OffsetToVertexArray);
            }
        }

        public class DanglymeshHeader
        {
            public Int32 OffsetToContraintArray { get; set; }
            public Int32 ContraintArrayCount { get; set; }
            public Int32 ContraintArrayCount1 { get; set; }
            public Single Displacement { get; set; }
            public Single Tightness { get; set; }
            public Single Period { get; set; }
            public Int32 Unknown1 { get; set; }

            public DanglymeshHeader()
            {

            }

            public DanglymeshHeader(BinaryReader reader)
            {
                OffsetToContraintArray = reader.ReadInt32();
                ContraintArrayCount = reader.ReadInt32();
                ContraintArrayCount1 = reader.ReadInt32();
                Displacement = reader.ReadSingle();
                Tightness = reader.ReadSingle();
                Period = reader.ReadSingle();
                Unknown1 = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(OffsetToContraintArray);
                writer.Write(ContraintArrayCount);
                writer.Write(ContraintArrayCount1);
                writer.Write(Displacement);
                writer.Write(Tightness);
                writer.Write(Period);
                writer.Write(Unknown1);
            }
        }

        public class SkinmeshHeader
        {


            public SkinmeshHeader()
            {

            }

            public SkinmeshHeader(BinaryReader reader)
            {

            }

            public void Write(BinaryWriter writer)
            {

            }
        }

        public class SabermeshHeader
        {
            public Int32 OffsetToVertexArray { get; set; }
            public Int32 OffsetToTexCoordArray { get; set; }
            public Int32 OffsetToNormalArray { get; set; }
            public Int32 Unknown1 { get; set; }
            public Int32 Unknown2 { get; set; }

            public SabermeshHeader()
            {

            }

            public SabermeshHeader(BinaryReader reader)
            {
                OffsetToVertexArray = reader.ReadInt32();
                OffsetToTexCoordArray = reader.ReadInt32();
                OffsetToNormalArray = reader.ReadInt32();
                Unknown1 = reader.ReadInt32();
                Unknown2 = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(OffsetToVertexArray);
                writer.Write(OffsetToTexCoordArray);
                writer.Write(OffsetToNormalArray);
                writer.Write(Unknown1);
                writer.Write(Unknown2);
            }
        }

        public class LightHeader
        {
            public static readonly int SIZE = 92;

            public Int32 OffsetToUnknownArray { get; set; }
            public Int32 UnknownArrayCount { get; set; }
            public Int32 UnknownArrayCount2 { get; set; }
            public Int32 OffsetTosFlareSizeArray { get; set; }
            public Int32 FlareSizeArrayCount { get; set; }
            public Int32 FlareSizeArrayCount2 { get; set; }
            public Int32 OffsetToFlarePositionArray { get; set; }
            public Int32 FlarePositionArrayCount { get; set; }
            public Int32 FlarePositionArrayCount2 { get; set; }
            public Int32 OffsetToFlareColorShiftArray { get; set; }
            public Int32 FlareColorShiftArrayCount { get; set; }
            public Int32 FlareColorShiftArrayCount2 { get; set; }
            public Int32 OffsetToFlareTextureNameArray { get; set; }
            public Int32 FlareTextureNameCount { get; set; }
            public Int32 FlareTextureNameCount2 { get; set; }
            public Single FlareRadius { get; set; }
            public UInt32 LightPriority { get; set; }
            public UInt32 AmbientOnly { get; set; }
            public UInt32 DynamicType { get; set; }
            public UInt32 AffectDynamic { get; set; }
            public UInt32 Shadow { get; set; }
            public UInt32 Flare { get; set; }
            public UInt32 FadingLight { get; set; }

            public LightHeader()
            {

            }

            public LightHeader(BinaryReader reader)
            {
                FlareRadius = reader.ReadSingle();
                OffsetToUnknownArray = reader.ReadInt32();
                UnknownArrayCount = reader.ReadInt32();
                UnknownArrayCount2 = reader.ReadInt32();
                OffsetTosFlareSizeArray = reader.ReadInt32();
                FlareSizeArrayCount = reader.ReadInt32();
                FlareSizeArrayCount2 = reader.ReadInt32();
                OffsetToFlarePositionArray = reader.ReadInt32();
                FlarePositionArrayCount = reader.ReadInt32();
                FlarePositionArrayCount2 = reader.ReadInt32();
                OffsetToFlareColorShiftArray = reader.ReadInt32();
                FlareColorShiftArrayCount = reader.ReadInt32();
                FlareColorShiftArrayCount2 = reader.ReadInt32();
                OffsetToFlareTextureNameArray = reader.ReadInt32();
                FlareTextureNameCount = reader.ReadInt32();
                FlareTextureNameCount2 = reader.ReadInt32();
                LightPriority = reader.ReadUInt32();
                AmbientOnly = reader.ReadUInt32();
                DynamicType = reader.ReadUInt32();
                AffectDynamic = reader.ReadUInt32();
                Shadow = reader.ReadUInt32();
                Flare = reader.ReadUInt32();
                FadingLight = reader.ReadUInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(FlareRadius);
                writer.Write(OffsetToUnknownArray);
                writer.Write(UnknownArrayCount);
                writer.Write(UnknownArrayCount2);
                writer.Write(OffsetTosFlareSizeArray);
                writer.Write(FlareSizeArrayCount);
                writer.Write(FlareSizeArrayCount2);
                writer.Write(OffsetToFlarePositionArray);
                writer.Write(FlarePositionArrayCount);
                writer.Write(FlarePositionArrayCount2);
                writer.Write(OffsetToFlareColorShiftArray);
                writer.Write(FlareColorShiftArrayCount);
                writer.Write(FlareColorShiftArrayCount2);
                writer.Write(OffsetToFlareTextureNameArray);
                writer.Write(FlareTextureNameCount);
                writer.Write(FlareTextureNameCount2);
                writer.Write(LightPriority);
                writer.Write(AmbientOnly);
                writer.Write(DynamicType);
                writer.Write(AffectDynamic);
                writer.Write(Shadow);
                writer.Write(Flare);
                writer.Write(FadingLight);
            }
        }

        public class EmitterHeader
        {
            public Single DeadSpace { get; set; }
            public Single BlastRadius { get; set; }
            public Single BlastLength { get; set; }
            public UInt32 BranchCount { get; set; }
            public Single ControlPointSmoothing { get; set; }
            public Int32 XGrid { get; set; }
            public Int32 YGrid { get; set; }
            public String Update { get; set; } = "";
            public String Render { get; set; } = "";
            public String Blend { get; set; } = "";
            public String Texture { get; set; } = "";
            public String ChunkName { get; set; } = "";
            public UInt32 TwoSidedTexture { get; set; }
            public UInt32 Loop { get; set; }
            public UInt32 RenderOrder { get; set; }
            public String DepthTextureName { get; set; } = "";
            public UInt32 Flags { get; set; }

            public EmitterHeader()
            {

            }

            public EmitterHeader(BinaryReader reader)
            {
                DeadSpace = reader.ReadSingle();
                BlastRadius = reader.ReadSingle();
                BlastLength = reader.ReadSingle();
                BranchCount = reader.ReadUInt32();
                ControlPointSmoothing = reader.ReadSingle();
                XGrid = reader.ReadInt32();
                YGrid = reader.ReadInt32();
                Update = reader.ReadString(32);
                Render = reader.ReadString(32);
                Blend = reader.ReadString(32);
                Texture = reader.ReadString(32);
                ChunkName = reader.ReadString(32);
                TwoSidedTexture = reader.ReadUInt32();
                Loop = reader.ReadUInt32();
                RenderOrder = reader.ReadUInt32();
                DepthTextureName = reader.ReadString(32);
                Flags = reader.ReadUInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(DeadSpace);
                writer.Write(BlastRadius);
                writer.Write(BlastLength);
                writer.Write(BranchCount);
                writer.Write(ControlPointSmoothing);
                writer.Write(XGrid);
                writer.Write(YGrid);
                writer.Write(Update, 32);
                writer.Write(Render, 32);
                writer.Write(Blend, 32);
                writer.Write(Texture, 32);
                writer.Write(ChunkName, 32);
                writer.Write(TwoSidedTexture);
                writer.Write(Loop);
                writer.Write(RenderOrder);
                writer.Write(DepthTextureName, 32);
                writer.Write(Flags);
            }
        }

        public class ReferenceHeader
        {
            public String ModelResRef { get; set; }
            public UInt32 Reattachable { get; set; }

            public ReferenceHeader()
            {

            }

            public ReferenceHeader(BinaryReader reader)
            {

            }

            public void Write(BinaryWriter writer)
            {

            }
        }

        public class FaceRoot
        {
            public static readonly int SIZE = 32;

            public Vector3 Normal { get; set; }
            public Single PlaneCoefficient { get; set; }
            public UInt32 Material { get; set; }
            public UInt16 FaceAdjacency1 { get; set; }
            public UInt16 FaceAdjacency2 { get; set; }
            public UInt16 FaceAdjacency3 { get; set; }
            public UInt16 Vertex1 { get; set; }
            public UInt16 Vertex2 { get; set; }
            public UInt16 Vertex3 { get; set; }

            public FaceRoot()
            {

            }

            public FaceRoot(BinaryReader reader)
            {
                Normal = reader.ReadVector3();
                PlaneCoefficient = reader.ReadSingle();
                Material = reader.ReadUInt32();
                FaceAdjacency1 = reader.ReadUInt16();
                FaceAdjacency2 = reader.ReadUInt16();
                FaceAdjacency3 = reader.ReadUInt16();
                Vertex1 = reader.ReadUInt16();
                Vertex2 = reader.ReadUInt16();
                Vertex3 = reader.ReadUInt16();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(Normal);
                writer.Write(PlaneCoefficient);
                writer.Write(Material);
                writer.Write(FaceAdjacency1);
                writer.Write(FaceAdjacency2);
                writer.Write(FaceAdjacency3);
                writer.Write(Vertex1);
                writer.Write(Vertex2);
                writer.Write(Vertex3);
            }
        }
    }
}
