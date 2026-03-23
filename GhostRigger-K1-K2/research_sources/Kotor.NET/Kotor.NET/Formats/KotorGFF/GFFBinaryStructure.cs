using Kotor.NET.Extensions;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Formats.KotorGFF
{
    public class GFFBinaryStructure
    {
        public class FileRoot
        {
            public FileHeader FileHeader { get; set; }
            public Struct[] Structs { get; set; }
            public Field[] Fields { get; set; }
            public string[] Labels { get; set; }
            public byte[] FieldData { get; set; }
            public byte[] FieldIndices { get; set; }
            public byte[] ListIndices { get; set; }

            public FileRoot()
            {

            }

            public FileRoot(BinaryReader reader)
            {
                FileHeader = new FileHeader(reader);

                Structs = new Struct[FileHeader.StructCount];
                reader.BaseStream.Position = FileHeader.OffsetToStructs;
                for (int i = 0; i < Structs.Length; i++)
                {
                    Structs[i] = new Struct(reader);
                }

                Fields = new Field[FileHeader.FieldCount];
                reader.BaseStream.Position = FileHeader.OffsetToFields;
                for (int i = 0; i < Fields.Length; i++)
                {
                    Fields[i] = new Field(reader);
                }

                Labels = new string[FileHeader.LabelCount];
                reader.BaseStream.Position = FileHeader.OffsetToLabels;
                for (int i = 0; i < Labels.Length; i++)
                {
                    Labels[i] = reader.ReadString(16);
                }

                reader.BaseStream.Position = FileHeader.OffsetToFieldData;
                FieldData = reader.ReadBytes((int)FileHeader.OffsetToFieldData);

                reader.BaseStream.Position = FileHeader.OffsetToFieldIndices;
                FieldIndices = reader.ReadBytes((int)FileHeader.OffsetToFieldIndices);

                reader.BaseStream.Position = FileHeader.OffsetToListIndicies;
                ListIndices = reader.ReadBytes((int)FileHeader.OffsetToListIndicies);
            }

            public void Write(BinaryWriter writer)
            {
                FileHeader.Write(writer);

                foreach (var @struct in Structs)
                {
                    @struct.Write(writer);
                }

                foreach (var field in Fields)
                {
                    field.Write(writer);
                }

                foreach (var label in Labels)
                {
                    writer.Write(label, 0);
                }

                writer.Write(FieldData);
                writer.Write(FieldIndices);
                writer.Write(ListIndices);
            }
        }

        public class FileHeader
        {
            public const int SIZE = 56;

            public string FileType { get; set; }
            public string FileVersion { get; set; }
            public int OffsetToStructs { get; set; }
            public int StructCount { get; set; }
            public int OffsetToFields { get; set; }
            public int FieldCount { get; set; }
            public int OffsetToLabels { get; set; }
            public int LabelCount { get; set; }
            public int OffsetToFieldData { get; set; }
            public int FieldDataLength { get; set; }
            public int OffsetToFieldIndices { get; set; }
            public int FieldIndiciesLength { get; set; }
            public int OffsetToListIndicies { get; set; }
            public int ListIndiciesLength { get; set; }

            public FileHeader()
            {

            }

            public FileHeader(BinaryReader reader)
            {
                FileType = reader.ReadString(4);
                FileVersion = reader.ReadString(4);
                OffsetToStructs = reader.ReadInt32();
                StructCount = reader.ReadInt32();
                OffsetToFields = reader.ReadInt32();
                FieldCount = reader.ReadInt32();
                OffsetToLabels = reader.ReadInt32();
                LabelCount = reader.ReadInt32();
                OffsetToFieldData = reader.ReadInt32();
                FieldDataLength = reader.ReadInt32();
                OffsetToFieldIndices = reader.ReadInt32();
                FieldIndiciesLength = reader.ReadInt32();
                OffsetToListIndicies = reader.ReadInt32();
                ListIndiciesLength = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(FileType, 0);
                writer.Write(FileVersion, 0);
                writer.Write(OffsetToStructs);
                writer.Write(StructCount);
                writer.Write(OffsetToFields);
                writer.Write(FieldCount);
                writer.Write(OffsetToLabels);
                writer.Write(LabelCount);
                writer.Write(OffsetToFieldData);
                writer.Write(FieldDataLength);
                writer.Write(OffsetToFieldIndices);
                writer.Write(FieldIndiciesLength);
                writer.Write(OffsetToListIndicies);
                writer.Write(ListIndiciesLength);
            }
        }

        public class Struct
        {
            public uint ID { get; set; }
            public int DataOrDataOffset { get; set; }
            public uint FieldCount { get; set; }

            public Struct()
            {

            }

            public Struct(BinaryReader reader)
            {
                ID = reader.ReadUInt32();
                DataOrDataOffset = reader.ReadInt32();
                FieldCount = reader.ReadUInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(ID);
                writer.Write(DataOrDataOffset);
                writer.Write(FieldCount);
            }
        }

        public class Field
        {
            public int Type { get; set; }
            public uint LabelIndex { get; set; }
            public byte[] DataOrDataOffset { get; set; }

            public Field()
            {

            }

            public Field(BinaryReader reader)
            {
                Type = reader.ReadInt32();
                LabelIndex = reader.ReadUInt32();
                DataOrDataOffset = reader.ReadBytes(4);
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(Type);
                writer.Write(LabelIndex);
                writer.Write(DataOrDataOffset);
            }
        }
    }
}
