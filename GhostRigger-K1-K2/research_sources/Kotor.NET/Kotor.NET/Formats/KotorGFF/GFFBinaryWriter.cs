using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Extensions;
using Kotor.NET.Formats.Kotor2DA;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;
using static Kotor.NET.Formats.KotorGFF.GFFBinaryStructure;

namespace Kotor.NET.Formats.KotorGFF
{
    public class GFFBinaryWriter : IWriter<GFF>
    {
        public BinaryWriter? _writer;
        public GFF? _gff;

        public GFFBinaryWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public GFFBinaryWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(GFF gff)
        {
            _gff = gff;
            var file = Build();
            file.Write(_writer);
        }

        private FileRoot Build()
        {
            var gff = _gff;

            var binary = new FileRoot();
            var allStructs = gff.AllStructs().ToList();
            var allFields = gff.AllFields().ToList();
            var allLabels = allFields.Select(x => x.Label).Distinct().ToList();

            binary.Structs = new Struct[allStructs.Count()];
            binary.Fields = new Field[allFields.Count()];
            binary.Labels = new string[allLabels.Count()];
            var fieldIndices = new List<byte>();
            var fieldData = new List<byte>();
            var listIndices = new List<byte>();

            for (int i = 0; i < binary.Structs.Length; i++)
            {
                var bStruct = binary.Structs[i] = new Struct();
                var gStruct = allStructs.ElementAt(i);

                bStruct.ID = gStruct.ID;
                bStruct.FieldCount = (uint)gStruct.Fields.Count();

                if (bStruct.FieldCount == 1)
                {
                    // Index into field array
                    bStruct.DataOrDataOffset = allFields.IndexOf(gStruct.Fields[0]);
                }
                else if (bStruct.FieldCount > 1)
                {
                    // Byte offset into field indicies array
                    bStruct.DataOrDataOffset = fieldIndices.Count();

                    // Populate the field indicies data
                    foreach (var field in gStruct.Fields)
                    {
                        var fieldIndex = allFields.IndexOf(field);
                        fieldIndices.AddRange(BitConverter.GetBytes(fieldIndex));
                    }
                }
            }

            for (int i = 0; i < binary.Fields.Length; i++)
            {
                var bField = binary.Fields[i] = new Field();
                var gField = allFields.ElementAt(i);

                var fieldDataOffset = BitConverter.GetBytes(fieldData.Count);
                var listIndicesOffset = BitConverter.GetBytes(listIndices.Count);

                bField.Type = (int)gField.Type;
                bField.LabelIndex = (uint)allLabels.IndexOf(gField.Label);

                if (gField.Type == GFFFieldType.UInt8)
                {
                    bField.DataOrDataOffset = BitConverter.GetBytes((uint)(byte)gField.Value);
                }
                else if (gField.Type == GFFFieldType.Int8)
                {
                    bField.DataOrDataOffset = BitConverter.GetBytes((int)(sbyte)gField.Value);
                }
                else if (gField.Type == GFFFieldType.UInt16)
                {
                    bField.DataOrDataOffset = BitConverter.GetBytes((uint)(ushort)gField.Value);
                }
                else if (gField.Type == GFFFieldType.Int16)
                {
                    bField.DataOrDataOffset = BitConverter.GetBytes((int)(short)gField.Value);
                }
                else if (gField.Type == GFFFieldType.UInt32)
                {
                    bField.DataOrDataOffset = BitConverter.GetBytes((uint)gField.Value);
                }
                else if (gField.Type == GFFFieldType.Int32)
                {
                    bField.DataOrDataOffset = BitConverter.GetBytes((int)gField.Value);
                }
                else if (gField.Type == GFFFieldType.UInt64)
                {
                    bField.DataOrDataOffset = fieldDataOffset;
                    fieldData.AddRange(BitConverter.GetBytes((ulong)gField.Value));
                }
                else if (gField.Type == GFFFieldType.Int64)
                {
                    bField.DataOrDataOffset = fieldDataOffset;
                    fieldData.AddRange(BitConverter.GetBytes((long)gField.Value));
                }
                else if (gField.Type == GFFFieldType.Single)
                {
                    bField.DataOrDataOffset = BitConverter.GetBytes((float)gField.Value);
                }
                else if (gField.Type == GFFFieldType.Double)
                {
                    bField.DataOrDataOffset = fieldDataOffset;
                    fieldData.AddRange(BitConverter.GetBytes((double)gField.Value));
                }
                else if (gField.Type == GFFFieldType.String)
                {
                    var value = (string)gField.Value;
                    bField.DataOrDataOffset = fieldDataOffset;
                    fieldData.AddRange(BitConverter.GetBytes((int)value.Length));
                    fieldData.AddRange(Encoding.GetEncoding(1252).GetBytes(value));
                }
                else if (gField.Type == GFFFieldType.ResRef)
                {
                    string value = ((ResRef)gField.Value).Get();
                    bField.DataOrDataOffset = fieldDataOffset;
                    fieldData.Add((byte)value.Length);
                    fieldData.AddRange(Encoding.GetEncoding(1252).GetBytes(value));
                }
                else if (gField.Type == GFFFieldType.LocalizedString)
                {
                    var value = (LocalizedString)gField.Value;
                    bField.DataOrDataOffset = fieldDataOffset;

                    var bytes = new List<byte>();
                    bytes.AddRange(BitConverter.GetBytes((int)value.StringRef));
                    bytes.AddRange(BitConverter.GetBytes((int)value.Substrings.Count));
                    foreach (var substring in value.Substrings)
                    {
                        var substringID = (int)substring.Language * 2 + (int)substring.Gender;
                        bytes.AddRange(BitConverter.GetBytes((int)substringID));
                        bytes.AddRange(BitConverter.GetBytes((int)substring.Text.Length));
                        bytes.AddRange(Encoding.GetEncoding(1252).GetBytes(substring.Text));
                    }

                    fieldData.AddRange(BitConverter.GetBytes((int)bytes.Count));
                    fieldData.AddRange(bytes);
                }
                else if (gField.Type == GFFFieldType.Binary)
                {
                    bField.DataOrDataOffset = fieldDataOffset;
                    fieldData.AddRange((byte[])gField.Value);
                }
                else if (gField.Type == GFFFieldType.Struct)
                {
                    var value = (GFFStruct)gField.Value;
                    bField.DataOrDataOffset = BitConverter.GetBytes(allStructs.IndexOf(value));
                }
                else if (gField.Type == GFFFieldType.List)
                {
                    var value = (GFFList)gField.Value;
                    bField.DataOrDataOffset = listIndicesOffset;
                    listIndices.AddRange(BitConverter.GetBytes(value.Count));
                    foreach (var @struct in value)
                    {
                        listIndices.AddRange(BitConverter.GetBytes(allStructs.IndexOf(@struct)));
                    }
                }
                else if (gField.Type == GFFFieldType.Vector4)
                {
                    bField.DataOrDataOffset = fieldDataOffset;

                    var value = (Vector4)gField.Value;
                    fieldData.AddRange(BitConverter.GetBytes(value.X));
                    fieldData.AddRange(BitConverter.GetBytes(value.Y));
                    fieldData.AddRange(BitConverter.GetBytes(value.Z));
                    fieldData.AddRange(BitConverter.GetBytes(value.W));
                }
                else if (gField.Type == GFFFieldType.Vector3)
                {
                    bField.DataOrDataOffset = fieldDataOffset;

                    var value = (Vector3)gField.Value;
                    fieldData.AddRange(BitConverter.GetBytes(value.X));
                    fieldData.AddRange(BitConverter.GetBytes(value.Y));
                    fieldData.AddRange(BitConverter.GetBytes(value.Z));
                }
            }

            for (int i = 0; i < binary.Labels.Length; i++)
            {
                var x = binary.Labels[i] = allLabels[i].PadRight(16, '\0').Truncate(16);
            }

            binary.FileHeader = new FileHeader();
            binary.FileHeader.FileType = "GFF ";
            binary.FileHeader.FileVersion = "V3.2";
            binary.FileHeader.OffsetToStructs = FileHeader.SIZE;
            binary.FileHeader.StructCount = allStructs.Count();
            binary.FileHeader.OffsetToFields = binary.FileHeader.OffsetToStructs + binary.FileHeader.StructCount * 12;
            binary.FileHeader.FieldCount = allFields.Count();
            binary.FileHeader.OffsetToLabels = binary.FileHeader.OffsetToFields + binary.FileHeader.FieldCount * 12;
            binary.FileHeader.LabelCount = allLabels.Count();
            binary.FileHeader.OffsetToFieldData = binary.FileHeader.OffsetToLabels + binary.FileHeader.LabelCount * 16; ;
            binary.FileHeader.FieldDataLength = fieldData.Count();
            binary.FileHeader.OffsetToFieldIndices = binary.FileHeader.OffsetToFieldData + binary.FileHeader.FieldDataLength;
            binary.FileHeader.FieldIndiciesLength = fieldIndices.Count();
            binary.FileHeader.OffsetToListIndicies = binary.FileHeader.OffsetToFieldIndices + binary.FileHeader.FieldIndiciesLength;
            binary.FileHeader.ListIndiciesLength = listIndices.Count();
            binary.FieldData = fieldData.ToArray();
            binary.FieldIndices = fieldIndices.ToArray();
            binary.ListIndices = listIndices.ToArray();

            return binary;
        }
    }
}
