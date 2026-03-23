using Kotor.NET.Common;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Creature;
using Kotor.NET.Common.Data;
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
    public class GFFBinaryReader : IReader<GFF>
    {
        private BinaryReader _reader;
        private GFF? _gff;

        private readonly string[] _validFileTypes = new[] { "2DA ", };
        private readonly string _validFileVersion = "V1.0";

        public GFFBinaryReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public GFFBinaryReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public GFFBinaryReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public GFF Read()
        {
            _gff = new GFF();

            var file = new FileRoot(_reader);

            var structs = new List<GFFStruct>();
            var fields = new List<GFFField>();

            for (int i = 0; i < file.FileHeader.StructCount; i++)
            {
                structs.Add(new GFFStruct());
            }

            for (int i = 0; i < file.FileHeader.FieldCount; i++)
            {
                fields.Add(new GFFField("", ""));
            }

            for (int i = 0; i < file.FileHeader.StructCount; i++)
            {
                var rawStruct = file.Structs[i];
                var gffStruct = structs[i];

                gffStruct.ID = rawStruct.ID;

                for (int j = 0; j < rawStruct.FieldCount; j++)
                {
                    var dataOffset = rawStruct.DataOrDataOffset;
                    int fieldIndex;

                    if (rawStruct.FieldCount == 1)
                    {
                        fieldIndex = rawStruct.DataOrDataOffset;
                    }
                    else
                    {
                        fieldIndex = BitConverter.ToInt32(file.FieldIndices, dataOffset + j * 4);
                    }

                    gffStruct.Fields.Add(fields[fieldIndex]);
                }
            }

            for (int i = 0; i < file.FileHeader.FieldCount; i++)
            {
                var rawField = file.Fields[i];
                var gffField = fields[i];
                var dataOffset = BitConverter.ToInt32(rawField.DataOrDataOffset);

                gffField.Label = file.Labels[rawField.LabelIndex];

                if (rawField.Type == (int)GFFFieldType.UInt8)
                {
                    gffField.Value = rawField.DataOrDataOffset[0];
                }
                else if (rawField.Type == (int)GFFFieldType.Int8)
                {
                    gffField.Value = (sbyte)BitConverter.ToInt16(rawField.DataOrDataOffset);
                }
                else if (rawField.Type == (int)GFFFieldType.UInt16)
                {
                    gffField.Value = BitConverter.ToUInt16(rawField.DataOrDataOffset);
                }
                else if (rawField.Type == (int)GFFFieldType.Int16)
                {
                    gffField.Value = BitConverter.ToInt16(rawField.DataOrDataOffset);
                }
                else if (rawField.Type == (int)GFFFieldType.UInt32)
                {
                    gffField.Value = BitConverter.ToUInt32(rawField.DataOrDataOffset);
                }
                else if (rawField.Type == (int)GFFFieldType.Int32)
                {
                    gffField.Value = BitConverter.ToInt32(rawField.DataOrDataOffset);
                }
                else if (rawField.Type == (int)GFFFieldType.UInt64)
                {
                    gffField.Value = BitConverter.ToUInt64(file.FieldData, dataOffset);
                }
                else if (rawField.Type == (int)GFFFieldType.Int64)
                {
                    gffField.Value = BitConverter.ToInt64(file.FieldData, dataOffset);
                }
                else if (rawField.Type == (int)GFFFieldType.Single)
                {
                    gffField.Value = BitConverter.ToSingle(rawField.DataOrDataOffset);
                }
                else if (rawField.Type == (int)GFFFieldType.Double)
                {
                    gffField.Value = BitConverter.ToDouble(file.FieldData, dataOffset);
                }
                else if (rawField.Type == (int)GFFFieldType.String)
                {
                    var length = BitConverter.ToInt32(file.FieldData, dataOffset);
                    gffField.Value = Encoding.ASCII.GetString(file.FieldData, dataOffset + 4, length); // TODO
                }
                else if (rawField.Type == (int)GFFFieldType.ResRef)
                {
                    var length = file.FieldData[dataOffset];
                    gffField.Value = new ResRef(Encoding.ASCII.GetString(file.FieldData, dataOffset + 1, length));
                }
                else if (rawField.Type == (int)GFFFieldType.LocalizedString)
                {
                    var locstring = new LocalizedString();

                    var totalSize = BitConverter.ToInt32(file.FieldData, dataOffset);
                    locstring.StringRef = BitConverter.ToInt32(file.FieldData, dataOffset + 4);
                    var stringCount = BitConverter.ToInt32(file.FieldData, dataOffset + 8);

                    var substringOffset = dataOffset + 12;
                    for (int j = 0; j < stringCount; j++)
                    {
                        var stringId = BitConverter.ToInt32(file.FieldData, substringOffset);
                        var stringLength = BitConverter.ToInt32(file.FieldData, substringOffset + 4);
                        var text = Encoding.GetEncoding(1252).GetString(file.FieldData, substringOffset + 8, stringLength);

                        var language = (Language)(stringId / 2);
                        var gender = (Gender)(stringId % 2);
                        locstring.Substrings.Add(new LocalizedSubstring(language, gender, text));

                        substringOffset += stringLength + 8;
                    }

                    gffField.Value = locstring;
                }
                else if (rawField.Type == (int)GFFFieldType.Binary)
                {
                    var length = BitConverter.ToInt32(file.FieldData, dataOffset);
                    gffField.Value = file.FieldData.Skip(dataOffset + 4).Take(length).ToArray();
                }
                else if (rawField.Type == (int)GFFFieldType.Struct)
                {
                    var structIndex = dataOffset;
                    gffField.Value = structs[structIndex];
                }
                else if (rawField.Type == (int)GFFFieldType.List)
                {
                    var list = new GFFList();
                    var count = BitConverter.ToInt32(file.ListIndices, dataOffset);

                    for (int j = 0; j < count; j++)
                    {
                        var structIndex = BitConverter.ToInt32(file.ListIndices, dataOffset + 4 + j * 4);
                        list.Add(structs[structIndex]);
                    }

                    gffField.Value = list;
                }
                else if (rawField.Type == (int)GFFFieldType.Vector4)
                {
                    var x = BitConverter.ToSingle(file.FieldData, dataOffset + 0);
                    var y = BitConverter.ToSingle(file.FieldData, dataOffset + 4);
                    var z = BitConverter.ToSingle(file.FieldData, dataOffset + 8);
                    var w = BitConverter.ToSingle(file.FieldData, dataOffset + 12); // TODO - w first or last?
                    gffField.Value = new Vector4(x, y, z, w);

                }
                else if (rawField.Type == (int)GFFFieldType.Vector3)
                {
                    var x = BitConverter.ToSingle(file.FieldData, dataOffset + 0);
                    var y = BitConverter.ToSingle(file.FieldData, dataOffset + 4);
                    var z = BitConverter.ToSingle(file.FieldData, dataOffset + 8);
                    gffField.Value = new Vector3(x, y, z);
                }
                else
                {
                    // TODO
                }
            }

            foreach (var rawStruct in file.Structs)
            {

            }

            _gff.Root = structs.FirstOrDefault() ?? new();

            return _gff;
        }
    }
}
