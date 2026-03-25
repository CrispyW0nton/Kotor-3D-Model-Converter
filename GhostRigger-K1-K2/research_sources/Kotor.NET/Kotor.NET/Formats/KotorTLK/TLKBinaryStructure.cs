using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Data;
using Kotor.NET.Extensions;

namespace Kotor.NET.Formats.KotorTLK
{
    public class TLKBinaryStructure
    {
        public class FileRoot
        {
            public FileHeader FileHeader { get; set; } = new();
            public List<StringData> StringData { get; set; } = new();
            public List<string> StringEntries { get; set; } = new();

            public FileRoot()
            {

            }

            public FileRoot(BinaryReader reader)
            {
                FileHeader = new FileHeader(reader);

                for (int i = 0; i < FileHeader.StringCount; i++)
                {
                    StringData.Add(new StringData(reader));
                }

                foreach (var stringData in StringData)
                {
                    reader.BaseStream.Position = stringData.OffsetToString + FileHeader.StringEntriesOffset;
                    var entry = reader.ReadString(stringData.StringSize);
                    StringEntries.Add(entry);
                }
            }

            public void Write(BinaryWriter writer)
            {
                FileHeader.Write(writer);

                foreach (var stringData in StringData)
                {
                    stringData.Write(writer);
                }

                foreach (var entry in StringEntries)
                {
                    writer.Write(entry, 0);
                }
            }
        }

        public class FileHeader
        {
            public static readonly int SIZE = 20;

            public string FileType { get; set; }
            public string FileVersion { get; set; }
            public int LanguageID { get; set; }
            public int StringCount { get; set; }
            public int StringEntriesOffset { get; set; }

            public FileHeader()
            {
                FileType = "TLK ";
                FileVersion = "V3.0";
            }

            public FileHeader(BinaryReader reader)
            {
                FileType = reader.ReadString(4);
                FileVersion = reader.ReadString(4);
                LanguageID = reader.ReadInt32();
                StringCount = reader.ReadInt32();
                StringEntriesOffset = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(FileType, 0);
                writer.Write(FileVersion, 0);
                writer.Write(LanguageID);
                writer.Write(StringCount);
                writer.Write(StringEntriesOffset);
            }
        }

        public class StringData
        {
            public static readonly int SIZE = 40;

            public uint Flags { get; set; }
            public ResRef SoundResRef { get; set; }
            public uint VolumeVariance { get; set; }
            public uint PitchVariance { get; set; }
            public int OffsetToString { get; set; }
            public int StringSize { get; set; }
            public float Length { get; set; }

            public StringData()
            {
                SoundResRef = "";
            }

            public StringData(BinaryReader reader)
            {
                Flags = reader.ReadUInt32();
                SoundResRef = reader.ReadResRef();
                VolumeVariance = reader.ReadUInt32();
                PitchVariance = reader.ReadUInt32();
                OffsetToString = reader.ReadInt32();
                StringSize = reader.ReadInt32();
                Length = reader.ReadSingle();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(Flags);
                writer.Write(SoundResRef, false);
                writer.Write(VolumeVariance);
                writer.Write(PitchVariance);
                writer.Write(OffsetToString);
                writer.Write(StringSize);
                writer.Write(Length);
            }
        }
    }
}
