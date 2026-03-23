// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Extensions;

namespace Kotor.NET.Formats.KotorKEY
{
    public class KEYBinaryStructure
    {
        public class FileRoot
        {
            public FileHeader FileHeader { get; set; }
            public List<BIFInfo> BIFs { get; set; }
            public List<string> Filenames { get; set; }
            public List<Key> Keys { get; set; }

            public FileRoot(BinaryReader reader)
            {
                FileHeader = new FileHeader(reader);

                BIFs = new List<BIFInfo>();
                reader.BaseStream.Position = FileHeader.OffsetToBIFs;
                for (int i = 0; i < FileHeader.BIFCount; i++)
                {
                    BIFs.Add(new BIFInfo(reader));
                }

                Filenames = new List<string>();
                foreach (var bif in BIFs)
                {
                    reader.BaseStream.Position = bif.FilenameOffset;
                    var filename = reader.ReadString(bif.FilenameLength);
                    Filenames.Add(filename);
                }

                Keys = new List<Key>();
                reader.BaseStream.Position = FileHeader.OffsetToKeys;
                for (int i = 0; i < FileHeader.KeyCount; i++)
                {
                    Keys.Add(new Key(reader));
                }
            }
        }

        public class FileHeader
        {
            public string FileType { get; set; }
            public string FileVersion { get; set; }
            public int BIFCount { get; set; }
            public int KeyCount { get; set; }
            public int OffsetToBIFs { get; set; }
            public int OffsetToKeys { get; set; }

            public FileHeader(BinaryReader reader)
            {
                FileType = reader.ReadString(4);
                FileVersion = reader.ReadString(4);
                BIFCount = reader.ReadInt32();
                KeyCount = reader.ReadInt32();
                OffsetToBIFs = reader.ReadInt32();
                OffsetToKeys = reader.ReadInt32();
            }
        }

        public class BIFInfo
        {
            public int FilenameOffset { get; set; }
            public short FilenameLength { get; set; }

            public BIFInfo(BinaryReader reader)
            {
                reader.BaseStream.Position += 4;
                FilenameOffset = reader.ReadInt32();
                FilenameLength = reader.ReadInt16();
                reader.BaseStream.Position += 2;
            }
        }

        public class Key
        {
            public string ResRef { get; set; }
            public ushort ResourceType { get; set; }
            public uint ResourceID { get; set; }

            public Key(BinaryReader reader)
            {
                ResRef = reader.ReadString(16);
                ResourceType = reader.ReadUInt16();
                ResourceID = reader.ReadUInt32();
            }

            public uint IndexIntoFileTable
            {
                get
                {
                    return (ResourceID >> 20);
                }
            }

            public uint IndexIntoResourceTable
            {
                get
                {
                    return (ResourceID << 20) >> 20;
                }
            }
        }
    }
}
