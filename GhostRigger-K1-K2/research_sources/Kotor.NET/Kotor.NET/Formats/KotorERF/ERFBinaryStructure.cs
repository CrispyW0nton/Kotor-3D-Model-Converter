using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Data;
using Kotor.NET.Extensions;

namespace Kotor.NET.Formats.KotorERF
{
    public class ERFBinaryStructure
    {
        public class FileRoot
        {
            public FileHeader FileHeader { get; set; } = new();
            public List<KeyEntry> KeyEntries { get; set; } = new();
            public List<ResourceEntry> ResourceEntries { get; set; } = new();
            public List<byte[]> ResourceData { get; set; } = new();

            public FileRoot()
            {

            }

            public FileRoot(BinaryReader reader)
            {
                FileHeader = new FileHeader(reader);

                reader.BaseStream.Position = FileHeader.OffsetToKeyList;
                for (int i = 0; i < FileHeader.EntryCount; i++)
                {
                    KeyEntries.Add(new KeyEntry(reader));
                }

                reader.BaseStream.Position = FileHeader.OffsetToResourceList;
                for (int i = 0; i < FileHeader.EntryCount; i++)
                {
                    ResourceEntries.Add(new ResourceEntry(reader));
                }

                foreach (var entry in ResourceEntries)
                {
                    reader.BaseStream.Position = entry.Offset;
                    ResourceData.Add(reader.ReadBytes(entry.Size));
                }
            }

            public void Write(BinaryWriter writer)
            {
                FileHeader.Write(writer);

                foreach (var entry in KeyEntries)
                {
                    entry.Write(writer);
                }

                foreach (var entry in ResourceEntries)
                {
                    entry.Write(writer);
                }

                foreach (var data in ResourceData)
                {
                    writer.Write(data);
                }
            }
        }

        public class FileHeader
        {
            public static readonly int SIZE = 40;

            public string FileType { get; set; } = "ERF ";
            public string FileVersion { get; set; } = "V1.0";
            public int EntryCount { get; set; }
            public int OffsetToKeyList { get; set; }
            public int OffsetToResourceList { get; set; }
            public int BuildYear { get; set; }
            public int BuildDay { get; set; }

            public FileHeader()
            {

            }

            public FileHeader(BinaryReader reader)
            {
                FileType = reader.ReadString(4);
                FileVersion = reader.ReadString(4);
                reader.BaseStream.Position += 4; // LanguageCount
                reader.BaseStream.Position += 4; // LocalizedStringSize
                EntryCount = reader.ReadInt32();
                reader.BaseStream.Position += 4; // OffsetToLocalizedString
                OffsetToKeyList = reader.ReadInt32();
                OffsetToResourceList = reader.ReadInt32();
                BuildYear = reader.ReadInt32();
                BuildDay = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(FileType, 0);
                writer.Write(FileVersion, 0);
                writer.Write(0);
                writer.Write(0);
                writer.Write(EntryCount);
                writer.Write(0);
                writer.Write(OffsetToKeyList);
                writer.Write(OffsetToResourceList);
                writer.Write(BuildYear);
                writer.Write(BuildDay);
            }
        }

        public class KeyEntry
        {
            public static readonly int SIZE = 24;

            public ResRef ResRef { get; set; } = "";
            public uint ResID { get; set; }
            public ushort ResType { get; set; }

            public KeyEntry()
            {

            }

            public KeyEntry(BinaryReader reader)
            {
                ResRef = reader.ReadResRef();
                ResID = reader.ReadUInt32();
                ResType = reader.ReadUInt16();
                reader.BaseStream.Position += 2;
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(ResRef, false);
                writer.Write(ResID);
                writer.Write(ResType);
                writer.Write((short)0);
            }
        }

        public class ResourceEntry
        {
            public static readonly int SIZE = 8;

            public int Offset { get; set; }
            public int Size { get; set; }

            public ResourceEntry()
            {

            }

            public ResourceEntry(BinaryReader reader)
            {
                Offset = reader.ReadInt32();
                Size = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(Offset);
                writer.Write(Size);
            }
        }
    }
}
