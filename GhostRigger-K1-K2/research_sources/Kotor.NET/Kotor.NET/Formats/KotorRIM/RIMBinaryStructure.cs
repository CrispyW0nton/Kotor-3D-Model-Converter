using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Data;
using Kotor.NET.Extensions;

namespace Kotor.NET.Formats.KotorRIM
{
    public class RIMBinaryStructure
    {
        public class FileRoot
        {
            public FileHeader FileHeader { get; set; } = new();
            public List<ResourceEntry> ResourceEntries { get; set; } = new();
            public List<byte[]> ResourceData { get; set; } = new();

            public FileRoot()
            {

            }
            public FileRoot(BinaryReader reader)
            {
                FileHeader = new FileHeader(reader);

                reader.BaseStream.Position = FileHeader.OffsetToResources;
                for (int i = 0; i < FileHeader.ResourceCount; i++)
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
            public static readonly int SIZE = 20;

            public string FileType { get; set; } = "RIM ";
            public string FileVersion { get; set; } = "V1.0";
            public int ResourceCount { get; set; }
            public int OffsetToResources { get; set; }

            public FileHeader()
            {

            }
            public FileHeader(BinaryReader reader)
            {
                FileType = reader.ReadString(4);
                FileVersion = reader.ReadString(4);
                reader.BaseStream.Position += 4;
                ResourceCount = reader.ReadInt32();
                OffsetToResources = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(FileType, 0);
                writer.Write(FileVersion, 0);
                writer.Write((int)0);
                writer.Write(ResourceCount);
                writer.Write(OffsetToResources);
            }
        }

        public class ResourceEntry
        {
            public static readonly int SIZE = 32;

            public ResRef ResRef { get; set; } = new();
            public int ResourceID { get; set; }
            public int ResourceTypeID { get; set; }
            public int Offset { get; set; }
            public int Size { get; set; }

            public ResourceEntry()
            {

            }
            public ResourceEntry(BinaryReader reader)
            {
                ResRef = reader.ReadString(16);
                ResourceTypeID = reader.ReadInt32();
                ResourceID = reader.ReadInt32();
                Offset = reader.ReadInt32();
                Size = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(ResRef, false);
                writer.Write(ResourceTypeID);
                writer.Write(ResourceID);
                writer.Write(Offset);
                writer.Write(Size);
            }
        }
    }
}
